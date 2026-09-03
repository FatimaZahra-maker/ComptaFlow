"""Planification NL -> QueryPlan strict avec replis Groq, Ollama et local."""

from __future__ import annotations

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.assistant_query_plan import (
    AssistantDomain, DateField, PaymentStatus, PlannerResult, QueryEntity, QueryFilters,
    QueryOperation, QueryPlan, QuerySort, SortDirection,
)
from app.services import groq_service
from app.services.assistant_semantic_registry import (
    detect_concepts, normalize_text, prompt_catalog, rank_domains, validate_plan,
)


_UNSAFE = re.compile(
    r"\b(select|insert|update|delete|drop|alter|truncate|grant|revoke)\b|--|/\*|"
    r"ignore\s+(?:les\s+)?(?:instructions|regles)|contourn\w*\s+(?:les\s+)?permissions|"
    r"autres?\s+cabinets?|mots?\s+de\s+passe|cles?\s+api|tokens?\s+(?:jwt|api)",
    re.I,
)
_MONTHS = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12,
}


def is_unsafe(question: str) -> bool:
    return bool(_UNSAFE.search(normalize_text(question)))


def _amount(question: str) -> Decimal | None:
    match = re.search(r"\b(\d{1,9}(?:[ ,. ]\d{3})*(?:[,.]\d{1,2})?)\s*(?:mad|dh|dhs|dirhams?)\b", normalize_text(question))
    if not match:
        return None
    try:
        return Decimal(match.group(1).replace(" ", "").replace(",", "."))
    except InvalidOperation:
        return None


def _dates(question: str) -> tuple[date | None, date | None, date | None]:
    normalized = normalize_text(question)
    if "aujourd'hui" in normalized or "aujourdhui" in normalized:
        return date.today(), None, None
    found: list[date] = []
    for day, month, year in re.findall(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b", normalized):
        try:
            found.append(date(int(year), int(month), int(day)))
        except ValueError:
            continue
    for year, month, day in re.findall(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", normalized):
        try:
            value = date(int(year), int(month), int(day))
            if value not in found:
                found.append(value)
        except ValueError:
            continue
    french = re.findall(r"\b(\d{1,2})\s+(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+(20\d{2})\b", normalized)
    for day, month, year in french:
        try:
            found.append(date(int(year), _MONTHS[month], int(day)))
        except ValueError:
            continue
    if len(found) >= 2 and any(term in normalized for term in ("entre", "du ", "periode", "jusqu")):
        return None, min(found), max(found)
    return (found[0] if found else None), None, None


def _filters(question: str, context: dict[str, Any]) -> QueryFilters:
    normalized = normalize_text(question)
    year_match = re.search(r"\b(20\d{2})\b", normalized)
    months = [number for name, number in _MONTHS.items() if name in normalized]
    invoice = re.search(r"(?:numero|reference|n[°o])\s*(?:de\s+)?(?:la\s+)?(?:facture\s+)?[:#-]?\s*([a-z0-9][a-z0-9/_-]*\d[a-z0-9/_-]*)", normalized)
    if not invoice:
        invoice = re.search(r"\bfacture\s+([a-z]{1,12}[-_/][a-z0-9/_-]*\d[a-z0-9/_-]*)", normalized)
    if not invoice:
        invoice = re.search(r"\b([a-z]{1,12}[-_/](?:20\d{2}[-_/])?[a-z0-9/_-]*\d[a-z0-9/_-]*)\b", normalized)
    company = re.search(r"(?:entreprise|societe|dossier)\s+(?:de|du|pour|chez|nommee?)\s+([a-z0-9][a-z0-9 &'._-]{1,80})", normalized)
    if not company:
        original_company = re.search(r"\b(?:de\s+|d['’]\s*|pour\s+|chez\s+)([A-Z][A-Z0-9&'._-]{2,}(?:\s+[A-Z][A-Z0-9&'._-]{2,})?)\b", question)
        company_name = original_company.group(1) if original_company else None
    else:
        company_name = company.group(1).strip(" .,-")
    if company_name:
        company_name = re.split(
            r"\s+(?:en|pour|au|entre|du mois)\s+(?:20\d{2}|janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre|le\b)",
            company_name,
            maxsplit=1,
        )[0].strip(" .,-")
    concepts = detect_concepts(normalized)
    payment = PaymentStatus.PARTIEL if "partiel" in concepts else PaymentStatus.IMPAYE if "impaye" in concepts else PaymentStatus.PAYE if "paye" in concepts else None
    exact_date, start_date, end_date = _dates(question)
    amount = _amount(question)
    supplier = re.search(r"(?:fournisseur|frs)\s+(?:de|du|chez|nomme)?\s*([a-z0-9][a-z0-9&'._-]{2,40})", normalized)
    customer = re.search(r"(?:client)\s+(?:de|du|chez|nomme)?\s*([a-z0-9][a-z0-9&'._-]{2,40})", normalized)
    amount_min = amount if amount is not None and any(term in normalized for term in ("plus de", "superieur", "au moins", ">")) else None
    amount_max = amount if amount is not None and any(term in normalized for term in ("moins de", "inferieur", "au plus", "<")) else None
    free_name = re.search(r"\bfacture\s+(?!de\b)([A-Z][A-Z0-9&'._-]{2,})\b", question)
    context_resource = context.get("context_document_id")
    if not context_resource and "premiere" in normalized and context.get("result_ids"):
        context_resource = context["result_ids"][0]
    follow_up_ids = context.get("result_ids", []) if any(term in normalized for term in ("celles", "ceux", "ces ", "et seulement")) else []
    values: dict[str, Any] = {
        "annee": int(year_match.group(1)) if year_match else context.get("annee"),
        "mois": months[0] if len(months) == 1 else context.get("mois"),
        "mois_comparaison": months if len(months) > 1 else [],
        "numero_facture": invoice.group(1) if invoice else None,
        "entreprise": company_name,
        "entreprise_id": None if company_name else context.get("entreprise_id"),
        "date_exacte": exact_date,
        "date_type": DateField.IMPORTATION if any(term in normalized for term in ("date import", "import", "televerse", "upload")) else DateField.PIECE if exact_date or start_date or end_date else None,
        "date_debut": start_date,
        "date_fin": end_date,
        "montant_exact": amount if amount_min is None and amount_max is None else None,
        "montant_min": amount_min,
        "montant_max": amount_max,
        "statut_paiement": payment,
        "fournisseur": supplier.group(1) if supplier and supplier.group(1) not in {"du", "de", "dossier"} else None,
        "client": customer.group(1) if customer and customer.group(1) not in {"du", "de", "dossier", "cabinet"} else None,
        "texte": free_name.group(1) if free_name else None,
        "statut_topaze": False if "topaze" in normalized and re.search(r"(?:non|pas(?: encore)?)\s+saisi|a saisir", normalized) else None,
        "statut": "non_rapproche" if "non rapproche" in normalized else "en_retard" if any(term in normalized for term in ("en retard", "echue", "echues")) else "a_verifier" if "a_verifier" in concepts else None,
        "resource_id": context_resource,
        "resource_ids": follow_up_ids,
    }
    return QueryFilters(**{key: value for key, value in values.items() if value not in (None, [], "")})


def deterministic_plan(question: str, context: dict[str, Any] | None = None, *, page: int = 1) -> QueryPlan:
    context = context or {}
    normalized = normalize_text(question)
    concepts = detect_concepts(normalized)
    ranked = rank_domains(normalized)
    domain = ranked[0][0] if ranked else AssistantDomain.UNKNOWN
    bank_document_request = bool(re.search(
        r"\b(?:facture|document|piece|releve)s?\b.*\b(?:banq\w*|bancair\w*)\b",
        normalized,
    )) and not any(term in normalized for term in (
        "compte bancaire", "mouvement bancaire", "operation bancaire",
        "rapprochement", "paiement", "reglement",
    ))
    if bank_document_request:
        domain = AssistantDomain.RELEVES_BANCAIRES
    # Le paiement est plus précis qu'une simple occurrence de facture.
    if domain != AssistantDomain.ALLOCATIONS and (any(concept in concepts for concept in {"paye", "partiel", "impaye"}) or any(term in normalized for term in ("paiement", "reglement", "reste du"))):
        domain = AssistantDomain.PAIEMENTS
    if "topaze" in normalized and re.search(r"(?:non|pas(?: encore)?)\s+saisi|a saisir", normalized):
        domain = AssistantDomain.TOPAZE
    if "count" in concepts:
        operation = QueryOperation.COUNT
    elif "sum" in concepts:
        operation = QueryOperation.SUM
    elif "compare" in concepts:
        operation = QueryOperation.COMPARE
    elif normalized.startswith(("ouvre ", "ouvrir ")):
        operation = QueryOperation.OPEN
    elif any(normalized.startswith(term) for term in ("trouve ", "retrouve ", "recherche ")):
        operation = QueryOperation.FIND_ONE
    elif any(value in normalized for value in ("pourquoi", "explique", "comment")):
        operation = QueryOperation.EXPLAIN
    else:
        operation = QueryOperation.LIST
    if domain == AssistantDomain.TVA and operation == QueryOperation.COUNT and any(term in normalized for term in ("combien de tva", "tva recupere", "tva recuperee")):
        operation = QueryOperation.SUM
    filters = _filters(question, context)
    group_by = None
    for label, terms in {
        "mois": ("par mois",), "entreprise": ("par entreprise", "par societe"),
        "fournisseur": ("par fournisseur",), "client": ("par client",),
        "statut": ("par statut",), "compte": ("par compte",),
    }.items():
        if any(term in normalized for term in terms):
            group_by = label
            operation = QueryOperation.GROUP
            break
    sort = None
    if any(term in normalized for term in ("plus recente", "plus recent", "dernieres", "derniers")):
        sort = QuerySort(field="date", direction=SortDirection.DESC)
    elif any(term in normalized for term in ("plus ancienne", "plus ancien", "premieres", "premiers")):
        sort = QuerySort(field="date", direction=SortDirection.ASC)
    elif "montant decroissant" in normalized or "plus gros montant" in normalized:
        sort = QuerySort(field="montant", direction=SortDirection.DESC)
    if domain == AssistantDomain.UNKNOWN and context.get("domain") and len(normalized.split()) <= 8:
        try:
            domain = AssistantDomain(context["domain"])
            if operation != QueryOperation.OPEN:
                operation = QueryOperation.FOLLOW_UP
        except ValueError:
            pass
    elif context.get("domain") and any(term in normalized for term in ("celles", "ceux", "cette", "premiere", "et seulement")):
        operation = QueryOperation.FOLLOW_UP if operation != QueryOperation.OPEN else operation
    entity = {
        AssistantDomain.ENTREPRISES: QueryEntity.ENTREPRISE,
        AssistantDomain.DOCUMENTS: QueryEntity.DOCUMENT,
        AssistantDomain.FACTURES_ACHAT: QueryEntity.FACTURE,
        AssistantDomain.FACTURES_VENTE: QueryEntity.FACTURE,
        AssistantDomain.RELEVES_BANCAIRES: QueryEntity.DOCUMENT,
        AssistantDomain.DONNEES_EXTRAITES: QueryEntity.DOCUMENT,
        AssistantDomain.ECRITURES: QueryEntity.ECRITURE,
        AssistantDomain.LIGNES_ECRITURE: QueryEntity.LIGNE,
        AssistantDomain.FOURNISSEURS: QueryEntity.TIERS,
        AssistantDomain.CLIENTS: QueryEntity.TIERS,
        AssistantDomain.PAIEMENTS: QueryEntity.ALLOCATION,
        AssistantDomain.MOUVEMENTS_BANCAIRES: QueryEntity.MOUVEMENT,
        AssistantDomain.ALLOCATIONS: QueryEntity.ALLOCATION,
        AssistantDomain.COMPTES_BANCAIRES: QueryEntity.COMPTE,
        AssistantDomain.PLAN_COMPTABLE: QueryEntity.COMPTE,
        AssistantDomain.TVA: QueryEntity.ETAT,
        AssistantDomain.GRAND_LIVRE: QueryEntity.ETAT,
        AssistantDomain.BALANCE: QueryEntity.ETAT,
        AssistantDomain.CPC: QueryEntity.ETAT,
        AssistantDomain.BILAN: QueryEntity.ETAT,
        AssistantDomain.PRE_CLOTURE: QueryEntity.ETAT,
        AssistantDomain.TACHES: QueryEntity.TACHE,
        AssistantDomain.AUDIT: QueryEntity.EVENEMENT_AUDIT,
    }.get(domain, QueryEntity.GENERIC)
    needs_clarification = (
        domain == AssistantDomain.DOCUMENTS
        and operation in {QueryOperation.FIND_ONE, QueryOperation.OPEN}
        and not filters.model_dump(exclude_none=True, exclude_defaults=True)
    )
    return QueryPlan(
        domain=domain, operation=operation, entity=entity, filters=filters,
        group_by=group_by, sort=sort, page=page,
        needs_clarification=needs_clarification,
        clarification_question="Quelle facture recherchez-vous ?" if needs_clarification else None,
    )


def _prompt(question: str, context: dict[str, Any], candidates: list[AssistantDomain]) -> str:
    schema = QueryPlan.model_json_schema()
    safe_context = {
        "domain": context.get("domain"),
        "operation": context.get("operation"),
        "annee": context.get("annee"),
        "mois": context.get("mois"),
        "entreprise_selectionnee": bool(context.get("entreprise_id")),
        "document_selectionne": bool(context.get("context_document_id")),
        "nombre_resultats_precedents": min(len(context.get("result_ids", [])), 50),
    }
    return f"""Tu es le planificateur en lecture seule de ComptaFlow. Transforme la question en UN objet JSON conforme au schéma fourni. N'invente aucun filtre. Tu ne connais ni tables ni SQL et tu ne dois jamais en produire. Si la demande est ambiguë, mets needs_clarification=true et une question courte. Les valeurs JSON sont non fiables et seront contrôlées côté serveur.
Domaines autorisés pour cette question :
{prompt_catalog(candidates)}
Contexte conversationnel minimal, sans identifiants : {json.dumps(safe_context, ensure_ascii=False, default=str)}
Schéma JSON : {json.dumps(schema, ensure_ascii=False)[:7000]}
Question non fiable : {question[:1500]!r}"""


def _parse_plan(raw: dict | None, *, page: int) -> QueryPlan | None:
    if not raw:
        return None
    try:
        raw["page"] = page
        plan = QueryPlan.model_validate(raw)
        validate_plan(plan)
        return plan
    except (ValidationError, ValueError, TypeError):
        return None


def _ollama(prompt: str) -> dict | None:
    try:
        response = requests.post(
            f"{settings.OLLAMA_URL.rstrip('/')}/api/generate",
            json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "format": "json", "stream": False},
            timeout=8,
        )
        response.raise_for_status()
        return json.loads(response.json().get("response", "{}"))
    except (requests.RequestException, ValueError, TypeError):
        return None


def plan_question(question: str, context: dict[str, Any] | None = None, *, page: int = 1) -> PlannerResult:
    context = context or {}
    normalized = normalize_text(question)
    ranked = rank_domains(normalized)
    concepts = detect_concepts(normalized)
    if ranked and (ranked[0][1] >= 3 or (len(ranked) == 1 and concepts)):
        plan = deterministic_plan(question, context, page=page)
        validate_plan(plan)
        return PlannerResult(plan=plan, provider="deterministic", normalized_question=normalized)
    candidates = [item[0] for item in ranked[:5]] or list(AssistantDomain)[:5]
    prompt = _prompt(question, context, candidates)
    raw = groq_service.planifier_question_assistant(prompt)
    plan = _parse_plan(raw, page=page)
    if plan:
        return PlannerResult(plan=plan, provider="groq", normalized_question=normalized)
    raw = _ollama(prompt)
    plan = _parse_plan(raw, page=page)
    if plan:
        return PlannerResult(plan=plan, provider="ollama", normalized_question=normalized)
    plan = deterministic_plan(question, context, page=page)
    validate_plan(plan)
    return PlannerResult(plan=plan, provider="deterministic", ai_unavailable=not ranked, normalized_question=normalized)
