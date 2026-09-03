"""Assistant ComptaFlow : intentions validées et lectures SQLAlchemy contrôlées."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import CategorieDocumentEnum, RoleEnum, StatutValidationEnum
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.models.tache import Tache
from app.models.user import User
from app.schemas.assistant import (
    AssistantAction,
    AssistantCompanyCard,
    AssistantDocumentCard,
    AssistantPaymentCard,
    AssistantQuery,
    AssistantResponse,
    AssistantSource,
)
from app.services import groq_service, tva_comptable_service


MAX_RESULTS = 20
ADMIN_ROLES = {RoleEnum.ADMIN_CABINET, RoleEnum.SUPER_ADMIN}
SAFE_EXTRACTED_FIELDS = {
    "numero_piece", "date_piece", "nom_fournisseur", "nom_client", "tiers",
    "ice_fournisseur", "ice_client", "if_fournisseur", "if_client",
    "rc_fournisseur", "rc_client", "adresse", "devise", "devise_originale",
    "montant_ht", "montant_tva", "montant_ttc", "taux_tva",
    "nature_comptable", "categorie", "categorie_document", "source_extraction",
    "a_verifier", "raison_verification", "confiance_par_champ",
}


class AssistantForbidden(Exception):
    pass


class AssistantNotFound(Exception):
    pass


def _norm(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFKD", value.lower())
        if not unicodedata.combining(char)
    )


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _parse_date(question: str) -> date | None:
    match = re.search(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b", question)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            return None
    match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b", question)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    months = {
        "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
        "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
        "octobre": 10, "novembre": 11, "decembre": 12,
    }
    normalized = _norm(question)
    match = re.search(r"\b(\d{1,2})\s+([a-z]+)\s+(20\d{2})\b", normalized)
    if match and match.group(2) in months:
        try:
            return date(int(match.group(3)), months[match.group(2)], int(match.group(1)))
        except ValueError:
            return None
    return None


def _parse_year(question: str) -> int | None:
    match = re.search(r"\b(20\d{2})\b", question)
    return int(match.group(1)) if match else None


def _parse_invoice_number(question: str) -> str | None:
    tokens = re.findall(r"\b[A-Za-z]{1,12}[-_/]\w(?:[A-Za-z0-9._/-]*\d[A-Za-z0-9._/-]*)\b", question)
    if tokens:
        return tokens[0]
    match = re.search(r"(?:n[°o]|numero|référence|reference)\s*[:#-]?\s*([A-Za-z0-9._/-]+)", question, re.I)
    return match.group(1) if match else None


def _parse_amount(question: str) -> Decimal | None:
    patterns = (
        r"(?:ttc|montant)\s+(?:de\s+)?([0-9][0-9 .]*(?:[,.][0-9]{1,2})?)",
        r"([0-9][0-9 .]*(?:[,.][0-9]{1,2})?)\s*(?:mad|dh|dhs)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, question, re.I)
        if match:
            normalized = match.group(1).replace(" ", "").replace(",", ".")
            try:
                return Decimal(normalized)
            except Exception:
                pass
    return None


def _intent(question: str) -> str:
    normalized = _norm(question)
    forbidden = (
        "requete sql", "execute sql", "drop table", "select * from",
        "autres cabinets", "autre cabinet", "mots de passe", "mot de passe",
        "ignore les regles", "contourne les permissions",
    )
    if any(value in normalized for value in forbidden):
        return "forbidden_request"
    compact = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    if re.fullmatch(r"(?:bonjour|bonsoir|salut|hello|coucou)(?:\s+(?:comptaflow|assistant))?[! ]*", compact):
        return "greeting"
    company_words = ("entreprise", "entreprises", "societe", "societes")
    company_cues = (
        "quelle", "quelles", "liste", "donne moi", "montre moi", "montre",
        "disponible", "disponibles", "existe", "existent", "existante",
        "existantes", "mon cabinet", "notre cabinet", "avons nous", "combien",
    )
    document_words = ("facture", "factures", "document", "documents", "piece", "pieces")
    if (
        any(re.search(rf"\b{word}\b", compact) for word in company_words)
        and any(cue in compact for cue in company_cues)
        and not any(re.search(rf"\b{word}\b", compact) for word in document_words)
    ):
        return "count_entreprises" if "combien" in compact else "list_entreprises"
    if "qui a modifie" in normalized or "historique" in normalized or "journal d'audit" in normalized:
        return "audit_lookup"
    if "donnees extraites" in normalized or "informations extraites" in normalized:
        return "document_details"
    if any(value in normalized for value in ("reglement", "paiement", "mouvement bancaire correspond")):
        return "payment_lookup"
    if "tva" in normalized and any(value in normalized for value in ("total", "deductible", "collectee")):
        return "vat_aggregate"
    if any(value in normalized for value in ("non reglee", "non reglees", "impayee", "impayees")):
        return "unpaid_invoices"
    if "topaze" in normalized and any(value in normalized for value in ("non sais", "pas sais")):
        return "entries_not_topaze"
    if ("tache" in normalized or "rappel" in normalized) and any(value in normalized for value in ("retard", "echue")):
        return "overdue_tasks"
    if any(value in normalized for value in ("ouvre la facture", "document original", "facture originale")):
        return "document_original"
    if any(re.search(rf"\b{word}\b", compact) for word in document_words):
        return "search_document"
    return "unknown"


def _accessible_companies_query(user: User):
    """Portée réellement disponible dans le modèle RBAC actuel.

    ComptaFlow ne possède pas encore de table d'affectation utilisateur ↔
    entreprise. Les utilisateurs actifs d'un cabinet voient donc ses dossiers
    actifs et validés, conformément aux routes existantes.
    """
    return select(Entreprise).where(
        Entreprise.cabinet_id == user.cabinet_id,
        Entreprise.is_active.is_(True),
        Entreprise.creee_automatiquement.is_(False),
    )


def _company_card(company: Entreprise) -> AssistantCompanyCard:
    return AssistantCompanyCard(
        entreprise_id=company.id,
        nom=company.nom,
        ice=company.ice,
        # L'IF n'est pas exposé par la route de liste existante. L'Assistant
        # conserve la même politique et n'élargit pas les données visibles.
        identifiant_fiscal=None,
        is_active=bool(company.is_active),
        actions=[AssistantAction(
            label="Voir les documents",
            kind="route",
            route=f"/chronos?entreprise_id={company.id}",
        )],
    )


def _resolve_company(
    db: Session, user: User, question: str, requested_id: uuid.UUID | None,
    hinted_name: str | None = None,
) -> Entreprise | None:
    companies = db.execute(_accessible_companies_query(user)).scalars().all()
    if requested_id is not None:
        company = next((item for item in companies if item.id == requested_id), None)
        if company is None:
            raise AssistantNotFound("Entreprise introuvable dans les données autorisées.")
        return company
    target = _norm(hinted_name or question)
    matches = [item for item in companies if _norm(item.nom) in target]
    return max(matches, key=lambda item: len(item.nom)) if matches else None


def _load_context_document(db: Session, user: User, document_id: uuid.UUID) -> tuple[Document, EcritureComptable | None, Entreprise | None]:
    row = db.execute(
        select(Document, EcritureComptable, Entreprise)
        .outerjoin(EcritureComptable, EcritureComptable.document_id == Document.id)
        .outerjoin(Entreprise, Entreprise.id == Document.entreprise_id)
        .where(Document.id == document_id, Document.cabinet_id == user.cabinet_id)
    ).first()
    if row is None:
        raise AssistantNotFound("Document introuvable dans les données autorisées.")
    return row[0], row[1], row[2]


def _safe_extracted(document: Document) -> dict[str, Any]:
    data = document.donnees_extraites if isinstance(document.donnees_extraites, dict) else {}
    return {key: data.get(key) for key in SAFE_EXTRACTED_FIELDS if key in data}


def _document_card(
    document: Document, entry: EcritureComptable | None, company: Entreprise | None,
    *, include_extracted: bool = False,
) -> AssistantDocumentCard:
    extracted = _safe_extracted(document)
    anomalies: list[str] = []
    if entry and entry.anomalie_detectee and entry.anomalie_details:
        anomalies.append(entry.anomalie_details)
    if extracted.get("raison_verification"):
        anomalies.append(str(extracted["raison_verification"]))
    devise = str(
        extracted.get("devise_originale") or extracted.get("devise")
        or (entry.devise_originale if entry else None) or "MAD"
    )
    return AssistantDocumentCard(
        document_id=document.id, entreprise_id=document.entreprise_id,
        entreprise=company.nom if company else None,
        categorie=_enum_value(document.categorie),
        tiers=entry.tiers if entry else extracted.get("tiers"),
        numero_facture=entry.numero_piece if entry else extracted.get("numero_piece"),
        date_facture=entry.date_piece if entry else None,
        date_importation=document.created_at,
        montant_ht=entry.montant_ht if entry else extracted.get("montant_ht"),
        montant_tva=entry.montant_tva if entry else extracted.get("montant_tva"),
        montant_ttc=entry.montant_ttc if entry else extracted.get("montant_ttc"),
        devise=devise, statut_document=_enum_value(document.statut) or "inconnu",
        statut_ecriture=_enum_value(entry.statut_validation) if entry else None,
        saisie_topaze=bool(document.saisie_topaze), anomalies=list(dict.fromkeys(anomalies)),
        donnees_extraites=extracted if include_extracted else None,
        actions=[
            AssistantAction(label="Voir la fiche document", kind="route", route=f"/documents/{document.id}"),
            AssistantAction(
                label="Ouvrir la facture originale", kind="secure_file",
                api_path=f"/documents/{document.id}/fichier",
                filename=document.nom_fichier_original,
            ),
        ],
    )


def _search_documents(
    db: Session, user: User, company: Entreprise | None, invoice_number: str | None,
    target_date: date | None, date_type: str, amount: Decimal | None,
) -> list[tuple[Document, EcritureComptable | None, Entreprise | None]]:
    query = (
        select(Document, EcritureComptable, Entreprise)
        .outerjoin(EcritureComptable, EcritureComptable.document_id == Document.id)
        .outerjoin(Entreprise, Entreprise.id == Document.entreprise_id)
        .where(Document.cabinet_id == user.cabinet_id)
    )
    if company:
        query = query.where(Document.entreprise_id == company.id)
    if invoice_number:
        query = query.where(EcritureComptable.numero_piece.ilike(f"%{invoice_number}%"))
    if target_date:
        if date_type == "importation":
            query = query.where(func.date(Document.created_at) == target_date)
        else:
            query = query.where(EcritureComptable.date_piece == target_date)
    if amount is not None:
        query = query.where(EcritureComptable.montant_ttc == amount)
    query = query.order_by(Document.created_at.desc()).limit(MAX_RESULTS)
    rows = db.execute(query).all()
    seen: set[uuid.UUID] = set()
    result = []
    for row in rows:
        if row[0].id not in seen:
            result.append((row[0], row[1], row[2]))
            seen.add(row[0].id)
    return result


def _base_response(intent: str, conversation_id: uuid.UUID, **kwargs) -> AssistantResponse:
    return AssistantResponse(conversation_id=conversation_id, intent=intent, **kwargs)


def repondre(db: Session, user: User, payload: AssistantQuery) -> AssistantResponse:
    question = payload.question.strip()
    conversation_id = payload.conversation_id or uuid.uuid4()
    intent = _intent(question)
    if intent == "forbidden_request":
        return _base_response(
            intent, conversation_id, response_type="error",
            message="Cette demande est refusée. L'assistant n'exécute pas de SQL et ne peut pas contourner les permissions.",
            warnings=["Seules les lectures métier autorisées dans votre cabinet sont disponibles."],
        )

    invoice_number = _parse_invoice_number(question)
    target_date = _parse_date(question)
    amount = _parse_amount(question)
    normalized = _norm(question)
    date_type = "importation" if "import" in normalized else "facture"
    ai_hint = None
    if intent == "unknown":
        ai_hint = groq_service.interpreter_question_assistant(question)
        if ai_hint and ai_hint.get("intent") in {
            "search_document", "document_details", "document_original", "payment_lookup",
            "vat_aggregate", "unpaid_invoices", "entries_not_topaze", "overdue_tasks",
            "audit_lookup", "list_entreprises", "count_entreprises", "greeting",
            "clarification", "out_of_scope",
        }:
            intent = str(ai_hint["intent"])
            invoice_number = ai_hint.get("invoice_number") or invoice_number

    if intent == "greeting":
        return _base_response(
            intent, conversation_id, response_type="message",
            message=("Bonjour ! Je peux rechercher vos entreprises, factures, écritures, "
                     "paiements, informations de TVA, tâches et éléments non saisis dans Topaze."),
        )

    if intent in {"unknown", "clarification", "out_of_scope"}:
        return _base_response(
            intent, conversation_id, response_type="clarification",
            message=("Je n'ai pas encore identifié précisément votre demande. Je peux rechercher "
                     "des entreprises, des factures, des écritures, des paiements, la TVA, des "
                     "tâches ou des éléments non saisis dans Topaze. Pouvez-vous préciser votre recherche ?"),
        )

    if intent in {"list_entreprises", "count_entreprises"}:
        total = db.execute(
            select(func.count()).select_from(_accessible_companies_query(user).subquery())
        ).scalar_one()
        companies = db.execute(
            _accessible_companies_query(user).order_by(Entreprise.nom).limit(MAX_RESULTS)
        ).scalars().all()
        if total == 0:
            return _base_response(
                intent, conversation_id, response_type="no_result", total_count=0,
                message="Aucune entreprise n'est actuellement disponible pour votre compte.",
            )
        suffix = f" Les {MAX_RESULTS} premières sont affichées." if total > MAX_RESULTS else ""
        message = f"Vous avez accès à {total} entreprise{'s' if total > 1 else ''}.{suffix}"
        return _base_response(
            intent, conversation_id, response_type="company_list", message=message,
            companies=[_company_card(company) for company in companies], total_count=total,
        )

    company = _resolve_company(
        db, user, question, payload.entreprise_id,
        str(ai_hint.get("company_name")) if ai_hint and ai_hint.get("company_name") else None,
    )

    if target_date and any(value in normalized for value in ("date de validation", "marquage topaze", "date topaze")):
        return _base_response(
            intent, conversation_id, response_type="clarification",
            message="Le type de date demandé doit être précisé avec une donnée disponible.",
            clarification_question="Parlez-vous de la date de la facture ou de sa date d'importation ?",
        )

    if intent in {"document_details", "document_original", "payment_lookup", "audit_lookup"} and payload.context_document_id:
        document, entry, context_company = _load_context_document(db, user, payload.context_document_id)
    else:
        document = entry = context_company = None

    if intent == "document_details" and document is None:
        detail_rows = _search_documents(db, user, company, invoice_number, target_date, date_type, amount)
        if len(detail_rows) == 1:
            document, entry, context_company = detail_rows[0]
        else:
            return _base_response(
                intent, conversation_id,
                response_type="clarification" if detail_rows else "no_result",
                message="Sélectionnez une facture unique pour afficher ses données extraites.",
                documents=[_document_card(*row) for row in detail_rows],
                clarification_question="Quelle facture souhaitez-vous consulter ?" if detail_rows else None,
            )

    if intent == "document_details" and document is not None:
        card = _document_card(document, entry, context_company, include_extracted=True)
        return _base_response(
            intent, conversation_id, response_type="single_document",
            message="Voici les données extraites disponibles. Les champs absents ne sont pas supposés.",
            documents=[card], sources=[AssistantSource(
                resource_type="document", resource_id=document.id,
                label=document.nom_fichier_original, route=f"/documents/{document.id}",
            )], context_document_id=document.id,
        )

    if intent == "document_original" and document is not None:
        card = _document_card(document, entry, context_company)
        return _base_response(
            intent, conversation_id, response_type="single_document",
            message="Voici le document demandé. Utilisez le bouton sécurisé pour ouvrir le fichier original.",
            documents=[card], context_document_id=document.id,
            sources=[AssistantSource(
                resource_type="document", resource_id=document.id,
                label=document.nom_fichier_original, route=f"/documents/{document.id}",
            )],
        )

    if intent == "payment_lookup":
        if entry is None:
            rows = _search_documents(db, user, company, invoice_number, target_date, date_type, amount)
            if len(rows) != 1 or rows[0][1] is None:
                return _base_response(
                    intent, conversation_id, response_type="clarification" if len(rows) > 1 else "no_result",
                    message="Sélectionnez d'abord une facture unique pour rechercher ses règlements.",
                    documents=[_document_card(*row) for row in rows],
                    clarification_question="Quelle facture souhaitez-vous utiliser ?" if len(rows) > 1 else None,
                )
            document, entry, context_company = rows[0]
        allocations = db.execute(
            select(RapprochementBancaireAllocation, MouvementBancaire)
            .join(MouvementBancaire, MouvementBancaire.id == RapprochementBancaireAllocation.mouvement_bancaire_id)
            .where(
                RapprochementBancaireAllocation.cabinet_id == user.cabinet_id,
                RapprochementBancaireAllocation.entreprise_id == entry.entreprise_id,
                RapprochementBancaireAllocation.ecriture_id == entry.id,
            ).order_by(MouvementBancaire.date_operation)
        ).all()
        paid = sum((Decimal(str(item.montant_affecte)) for item, _ in allocations), Decimal("0"))
        remaining = max(Decimal("0"), Decimal(str(entry.montant_ttc)) - paid)
        payments = [AssistantPaymentCard(
            mouvement_id=movement.id, ecriture_id=entry.id,
            date_operation=movement.date_operation,
            montant_mouvement=movement.montant, montant_affecte=allocation.montant_affecte,
            restant_du=remaining, reference=movement.reference, libelle=movement.libelle,
            statut=allocation.statut,
            actions=[AssistantAction(label="Voir le mouvement", kind="route", route=f"/banque?movement_id={movement.id}")],
        ) for allocation, movement in allocations]
        return _base_response(
            intent, conversation_id,
            response_type="accounting_detail" if payments else "no_result",
            message=(f"{len(payments)} règlement(s) associé(s). Restant dû : {remaining} MAD."
                     if payments else "Aucun règlement associé n'a été trouvé."),
            payments=payments, context_document_id=document.id if document else None,
            sources=[AssistantSource(resource_type="ecriture", resource_id=entry.id, label=entry.numero_piece or "Écriture")],
        )

    if intent == "vat_aggregate":
        year = _parse_year(question)
        if company is None or year is None:
            return _base_response(
                intent, conversation_id, response_type="clarification",
                message="Une entreprise et un exercice sont nécessaires pour calculer la TVA.",
                clarification_question="Pour quelle entreprise et quelle année souhaitez-vous le total de TVA ?",
            )
        result = tva_comptable_service.calculer_tva_annuelle(
            db, cabinet_id=user.cabinet_id, entreprise_id=company.id, annee=year,
        )
        aggregate = {
            "entreprise": company.nom, "annee": year, "devise": "MAD",
            "tva_collectee": result.total_tva_collectee,
            "tva_deductible_charges": result.total_tva_deductible_charges,
            "tva_deductible_immobilisations": result.total_tva_deductible_immobilisations,
            "tva_deductible": result.total_tva_deductible,
            "source": result.source_calcul,
        }
        return _base_response(
            intent, conversation_id, response_type="aggregate",
            message=f"Le total de TVA déductible de {company.nom} pour {year} est de {result.total_tva_deductible} MAD.",
            filters={"entreprise": company.nom, "annee": year}, aggregate=aggregate,
            warnings=list(result.limites),
        )

    if intent in {"unpaid_invoices", "entries_not_topaze"}:
        paid_sq = (
            select(
                RapprochementBancaireAllocation.ecriture_id.label("entry_id"),
                func.sum(RapprochementBancaireAllocation.montant_affecte).label("paid"),
            )
            .where(
                RapprochementBancaireAllocation.cabinet_id == user.cabinet_id,
                RapprochementBancaireAllocation.statut.in_(["confirme", "automatique"]),
            ).group_by(RapprochementBancaireAllocation.ecriture_id).subquery()
        )
        query = (
            select(Document, EcritureComptable, Entreprise)
            .join(EcritureComptable, EcritureComptable.document_id == Document.id)
            .outerjoin(Entreprise, Entreprise.id == EcritureComptable.entreprise_id)
            .outerjoin(paid_sq, paid_sq.c.entry_id == EcritureComptable.id)
            .where(
                EcritureComptable.cabinet_id == user.cabinet_id,
                EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            )
        )
        if company:
            query = query.where(EcritureComptable.entreprise_id == company.id)
        if intent == "unpaid_invoices":
            query = query.where(func.coalesce(paid_sq.c.paid, 0) < EcritureComptable.montant_ttc)
        else:
            query = query.where(EcritureComptable.saisie_topaze.is_(False))
        rows = db.execute(query.order_by(EcritureComptable.date_piece.desc()).limit(MAX_RESULTS)).all()
        cards = [_document_card(*row) for row in rows]
        label = "factures non réglées" if intent == "unpaid_invoices" else "écritures validées non saisies dans Topaze"
        return _base_response(
            intent, conversation_id, response_type="document_list" if cards else "no_result",
            message=f"{len(cards)} {label} trouvée(s) dans les données autorisées.",
            documents=cards, filters={"entreprise": company.nom if company else "Toutes"},
        )

    if intent == "overdue_tasks":
        today = datetime.now(timezone.utc).date()
        query = select(Tache).where(
            Tache.cabinet_id == user.cabinet_id,
            Tache.date_echeance < today,
            Tache.statut != "terminee",
        )
        if company:
            query = query.where(Tache.entreprise_id == company.id)
        tasks = db.execute(query.order_by(Tache.date_echeance).limit(MAX_RESULTS)).scalars().all()
        return _base_response(
            intent, conversation_id, response_type="accounting_detail" if tasks else "no_result",
            message=f"{len(tasks)} tâche(s) en retard trouvée(s).",
            aggregate={"nombre": len(tasks), "taches": [
                {"id": str(task.id), "titre": task.titre, "date_echeance": task.date_echeance,
                 "priorite": _enum_value(task.priorite), "route": f"/rappels?task_id={task.id}"}
                for task in tasks
            ]},
            sources=[AssistantSource(resource_type="tache", resource_id=task.id, label=task.titre, route="/rappels") for task in tasks],
        )

    if intent == "audit_lookup":
        if user.role not in ADMIN_ROLES:
            raise AssistantForbidden("La consultation de l'historique est réservée aux administrateurs.")
        if document is None:
            rows = _search_documents(db, user, company, invoice_number, target_date, date_type, amount)
            if len(rows) != 1:
                return _base_response(
                    intent, conversation_id, response_type="clarification" if rows else "no_result",
                    message="Identifiez une facture unique avant de consulter son historique.",
                    documents=[_document_card(*row) for row in rows],
                    clarification_question="Quelle facture souhaitez-vous vérifier ?" if rows else None,
                )
            document, entry, context_company = rows[0]
        logs = db.execute(select(AuditLog).where(
            AuditLog.cabinet_id == user.cabinet_id,
            AuditLog.resource_type == "document", AuditLog.resource_id == document.id,
        ).order_by(AuditLog.event_at.desc()).limit(20)).scalars().all()
        return _base_response(
            intent, conversation_id, response_type="accounting_detail" if logs else "no_result",
            message=(f"{len(logs)} événement(s) trouvé(s) pour cette facture."
                     if logs else "Aucun événement détaillé n'a été trouvé pour cette facture."),
            aggregate={"evenements": [
                {"action": log.action, "acteur": log.actor_name or log.actor_email or "Système",
                 "role": log.actor_role, "date": log.event_at, "description": log.description}
                for log in logs
            ]}, context_document_id=document.id,
        )

    # Recherche documentaire et ouverture du document original.
    if not any((company, invoice_number, target_date, amount)):
        return _base_response(
            intent, conversation_id, response_type="clarification",
            message="Précisez au moins l'entreprise, le numéro, la date ou le montant de la facture.",
            clarification_question="Quelle facture recherchez-vous ?",
        )
    rows = _search_documents(db, user, company, invoice_number, target_date, date_type, amount)
    filters = {
        "entreprise": company.nom if company else None,
        "numero_facture": invoice_number,
        "date": target_date.isoformat() if target_date else None,
        "type_date": date_type if target_date else None,
        "montant_ttc": format(amount, "f") if amount is not None else None,
    }
    filters = {key: value for key, value in filters.items() if value is not None}
    if not rows:
        target = company.nom if company else "les critères demandés"
        return _base_response(
            intent, conversation_id, response_type="no_result",
            message=f"Aucune facture correspondant à {target} n'a été trouvée dans les données auxquelles vous avez accès.",
            filters=filters,
        )
    cards = [_document_card(*row) for row in rows]
    response_type = "single_document" if len(cards) == 1 else "document_list"
    message = ("J'ai trouvé la facture correspondante."
               if len(cards) == 1 else f"J'ai trouvé {len(cards)} factures correspondant à ces critères.")
    return _base_response(
        intent, conversation_id, response_type=response_type, message=message,
        filters=filters, documents=cards,
        sources=[AssistantSource(
            resource_type="document", resource_id=row[0].id,
            label=row[0].nom_fichier_original, route=f"/documents/{row[0].id}",
        ) for row in rows], context_document_id=rows[0][0].id if len(rows) == 1 else None,
    )


# ---------------------------------------------------------------------------
# Assistant V2 : cette définition remplace l'orchestrateur historique ci-dessus
# sans supprimer ses helpers, conservés temporairement pour compatibilité.
# ---------------------------------------------------------------------------
_legacy_repondre = repondre


def _suggestions_for_response(response: AssistantResponse) -> list[str]:
    if response.response_type == "clarification":
        return []
    domain = response.intent
    suggestions = {
        "entreprises": ["Afficher les documents de cette entreprise", "Combien de factures sont à vérifier ?"],
        "documents": ["Afficher uniquement les données extraites", "Quelles pièces ne sont pas saisies dans Topaze ?"],
        "factures_achat": ["Quel est le montant total ?", "Afficher les factures impayées"],
        "factures_vente": ["Quel est le montant total ?", "Afficher les factures payées"],
        "paiements": ["Calculer le total restant dû", "Regrouper par fournisseur", "Afficher les paiements partiels"],
        "tva": ["Afficher la Balance de la même période", "Quels éléments sont à vérifier ?"],
    }.get(domain, ["Afficher les éléments à vérifier", "Afficher les tâches en retard"])
    if response.has_more:
        suggestions.insert(0, "Voir plus de résultats")
    return suggestions[:3]


def _new_repondre(db: Session, user: User, payload: AssistantQuery) -> AssistantResponse:
    from app.services import assistant_memory_service, assistant_planner_service
    from app.services import assistant_query_engine
    from app.services.assistant_semantic_registry import normalize_text

    question = payload.question.strip()
    # Les anciens tests unitaires injectent db=None et substituent les helpers
    # historiques. En production FastAPI fournit toujours une Session réelle.
    if db is None:
        return _legacy_repondre(db, user, payload)
    conversation_id = payload.conversation_id or uuid.uuid4()
    normalized = normalize_text(question)
    if assistant_planner_service.is_unsafe(question):
        return AssistantResponse(
            conversation_id=conversation_id, response_type="error", intent="forbidden_request",
            message="Cette demande est refusée. L'assistant n'exécute pas de SQL et ne contourne jamais les permissions.",
            warnings=["Seules les lectures métier autorisées dans votre cabinet sont disponibles."],
        )
    if normalized in {"bonjour", "bonsoir", "salut", "hello", "coucou", "bonjour comptaflow"}:
        return AssistantResponse(
            conversation_id=conversation_id, response_type="message", intent="greeting",
            message="Bonjour ! Interrogez naturellement vos entreprises, pièces, pré-écritures, paiements, tâches et états comptables.",
            suggestions=["Quelles entreprises sont disponibles ?", "Afficher les éléments à vérifier", "Quelles tâches sont en retard ?"],
        )
    context = assistant_memory_service.load(user.cabinet_id, user.id, conversation_id)
    if payload.entreprise_id:
        context["entreprise_id"] = str(payload.entreprise_id)
    if payload.context_document_id:
        context["context_document_id"] = str(payload.context_document_id)
    planner = assistant_planner_service.plan_question(question, context, page=payload.page)
    if not planner.plan.filters.entreprise_id and not planner.plan.filters.entreprise and context.get("entreprise_id"):
        planner.plan.filters.entreprise_id = uuid.UUID(str(context["entreprise_id"]))
    try:
        if planner.plan.needs_clarification:
            response = AssistantResponse(
                conversation_id=conversation_id, response_type="clarification",
                intent=planner.plan.domain.value,
                message=planner.plan.clarification_question or "La demande nécessite une précision.",
                clarification_question=planner.plan.clarification_question,
                plan_summary={"domain": planner.plan.domain.value, "operation": planner.plan.operation.value},
            )
        else:
            response = assistant_query_engine.execute(db, user, planner.plan, conversation_id)
    except assistant_query_engine.QueryEngineForbidden as exc:
        raise AssistantForbidden(str(exc)) from exc
    except assistant_query_engine.QueryEngineNotFound as exc:
        # Un nom ambigu est une clarification, pas une fuite d'existence inter-cabinet.
        response = AssistantResponse(
            conversation_id=conversation_id, response_type="clarification",
            intent=planner.plan.domain.value, message=str(exc),
            clarification_question="Pouvez-vous préciser le dossier concerné ?",
            plan_summary={"domain": planner.plan.domain.value, "operation": planner.plan.operation.value},
        )
    response.plan_summary["provider"] = planner.provider
    if planner.ai_unavailable and planner.plan.domain.value == "unknown":
        response.response_type = "error"
        response.message = "Les services d'interprétation sont indisponibles et le repli local n'a pas reconnu cette demande. Réessayez ou précisez le domaine comptable."
        response.warnings.append("Aucune donnée n'a été consultée pour cette question.")
    if planner.plan.domain.value == "entreprises":
        response.intent = "count_entreprises" if planner.plan.operation.value == "count" else "list_entreprises"
    response.suggestions = _suggestions_for_response(response)
    result_ids = [source.resource_id for source in response.sources]
    result_ids.extend(company.entreprise_id for company in response.companies)
    selected_company = planner.plan.filters.entreprise_id
    if len(response.companies) == 1:
        selected_company = response.companies[0].entreprise_id
    elif len(response.documents) == 1 and response.documents[0].entreprise_id:
        selected_company = response.documents[0].entreprise_id
    assistant_memory_service.save(
        user.cabinet_id, user.id, conversation_id,
        {
            "domain": planner.plan.domain.value,
            "operation": planner.plan.operation.value,
            "entreprise_id": str(selected_company) if selected_company else context.get("entreprise_id"),
            "annee": planner.plan.filters.annee or context.get("annee"),
            "mois": planner.plan.filters.mois or context.get("mois"),
            "context_document_id": str(response.context_document_id) if response.context_document_id else context.get("context_document_id"),
            "result_ids": result_ids,
        },
    )
    return response


repondre = _new_repondre
