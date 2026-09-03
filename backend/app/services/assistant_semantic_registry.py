"""Registre sémantique fermé de l'Assistant ComptaFlow."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.schemas.assistant_query_plan import AssistantDomain, QueryOperation, QueryPlan


@dataclass(frozen=True)
class DomainDefinition:
    description: str
    terms: tuple[str, ...]
    operations: frozenset[QueryOperation]
    filters: frozenset[str]
    groups: frozenset[str] = frozenset()
    sorts: frozenset[str] = frozenset({"date", "montant", "nom", "created_at"})


COMMON_FILTERS = frozenset({
    "entreprise", "entreprise_id", "date_exacte", "date_debut", "date_fin",
    "annee", "mois", "texte", "resource_id", "resource_ids", "date_type",
})
READ_OPERATIONS = frozenset({
    QueryOperation.FIND_ONE, QueryOperation.LIST, QueryOperation.COUNT,
    QueryOperation.SUM, QueryOperation.GROUP, QueryOperation.COMPARE,
    QueryOperation.EXPLAIN, QueryOperation.OPEN, QueryOperation.FOLLOW_UP,
})


def _definition(description: str, terms: str, *, filters: set[str] | None = None,
                operations: frozenset[QueryOperation] = READ_OPERATIONS,
                groups: set[str] | None = None) -> DomainDefinition:
    return DomainDefinition(
        description=description,
        terms=tuple(terms.split("|")),
        operations=operations,
        filters=COMMON_FILTERS | frozenset(filters or set()),
        groups=frozenset(groups or set()),
    )


REGISTRY: dict[AssistantDomain, DomainDefinition] = {
    AssistantDomain.ENTREPRISES: _definition("Dossiers des entreprises clientes", "entreprise|societe|dossier|client du cabinet", filters={"statut"}, groups={"statut"}),
    AssistantDomain.DOCUMENTS: _definition("Pièces et documents importés", "facture|document|piece|fichier|pdf|scan|import", filters={"numero_facture", "tiers", "statut", "statut_topaze"}, groups={"categorie", "statut", "entreprise", "mois"}),
    AssistantDomain.FACTURES_ACHAT: _definition("Factures d'achat et fournisseurs", "facture achat|achat|fournisseur|charge", filters={"fournisseur", "tiers", "numero_facture", "montant_exact", "montant_min", "montant_max", "statut_paiement", "statut_topaze"}, groups={"fournisseur", "mois", "statut_paiement"}),
    AssistantDomain.FACTURES_VENTE: _definition("Factures de vente et clients", "facture vente|vente|client|produit", filters={"client", "tiers", "numero_facture", "montant_exact", "montant_min", "montant_max", "statut_paiement", "statut_topaze"}, groups={"client", "mois", "statut_paiement"}),
    AssistantDomain.RELEVES_BANCAIRES: _definition(
        "Documents de la catégorie Banque et relevés bancaires importés",
        "releve bancaire|releve|document banque|document bancaire|facture banque|facture bancaire|piece banque|piece bancaire|piece de la banque|banq",
        filters={"statut"},
    ),
    AssistantDomain.DONNEES_EXTRAITES: _definition("Champs extraits des documents", "donnees extraites|information extraite|champ extrait|extraction|ocr|ice|if|rc", filters={"numero_facture", "statut"}),
    AssistantDomain.CHRONOS: _definition("Classement numérique des documents", "chrono|classeur|classement", filters={"statut"}, groups={"annee", "mois", "categorie"}),
    AssistantDomain.ECRITURES: _definition("Pré-écritures comptables", "pre ecriture|ecriture comptable|ecriture|journal", filters={"tiers", "numero_facture", "montant_exact", "statut", "statut_topaze"}, groups={"type", "statut", "mois"}),
    AssistantDomain.LIGNES_ECRITURE: _definition("Lignes débit et crédit validées", "ligne ecriture|ligne d ecriture|ligne comptable|debit|credit", filters={"compte_prefixe", "numero_facture"}, groups={"compte", "journal", "mois"}),
    AssistantDomain.FOURNISSEURS: _definition("Tiers fournisseurs issus des achats", "fournisseur du dossier|fournisseur|frs|tiers achat", filters={"tiers"}, groups={"tiers", "fournisseur"}),
    AssistantDomain.CLIENTS: _definition("Tiers clients issus des ventes", "client|tiers vente", filters={"tiers"}, groups={"tiers", "client"}),
    AssistantDomain.MOUVEMENTS_BANCAIRES: _definition("Mouvements des relevés bancaires", "mouvement bancaire|operation bancaire|debit banque|credit banque", filters={"montant_exact", "montant_min", "montant_max", "statut"}, groups={"nature", "statut", "mois"}),
    AssistantDomain.RAPPROCHEMENTS: _definition("Rapprochements bancaires", "rapprochement|rapproche|lettrage bancaire", filters={"statut"}, groups={"statut", "mode"}),
    AssistantDomain.ALLOCATIONS: _definition("Affectations paiements-factures", "allocation|affectation|montant affecte", filters={"statut", "montant_min", "montant_max"}),
    AssistantDomain.PAIEMENTS: _definition("Paiements et restes à régler", "paiement|reglement|paye|impaye|reste du|solde facture", filters={"tiers", "statut_paiement", "montant_min", "montant_max"}, groups={"statut_paiement", "tiers"}),
    AssistantDomain.COMPTES_BANCAIRES: _definition("Comptes bancaires configurés", "compte bancaire|iban|rib|banque", filters={"statut"}),
    AssistantDomain.PLAN_COMPTABLE: _definition("Plan comptable propre à l'entreprise", "plan comptable|compte comptable|numero compte|cgnc", filters={"compte_prefixe", "tiers", "statut"}, groups={"type_usage", "famille"}),
    AssistantDomain.TVA: _definition("TVA comptable et positions périodiques", "tva|taxe valeur ajoutee|tva collectee|tva recuperable|credit tva", filters={"statut"}, groups={"mois", "nature"}),
    AssistantDomain.TACHES: _definition("Tâches et échéances", "tache|rappel|echeance|a faire|retard", filters={"statut"}, groups={"statut", "priorite"}),
    AssistantDomain.ALERTES: _definition("Alertes opérationnelles", "alerte|notification|anomalie", filters={"statut"}, groups={"type"}),
    AssistantDomain.A_VERIFIER: _definition("Éléments nécessitant une validation humaine", "a verifier|verification humaine|ambigu|anomalie", filters={"statut"}, groups={"type"}),
    AssistantDomain.TOPAZE: _definition("Statut de préparation/export Topaze", "topaze|saisie topaze|export topaze", filters={"statut_topaze"}, groups={"statut_topaze"}),
    AssistantDomain.GRAND_LIVRE: _definition("Grand Livre des lignes validées", "grand livre|ledger", filters={"compte_prefixe"}, groups={"compte"}),
    AssistantDomain.BALANCE: _definition("Balance comptable", "balance comptable|balance", filters={"compte_prefixe"}, groups={"compte"}),
    AssistantDomain.CPC: _definition("Compte de produits et charges", "cpc|compte produits charges|resultat", groups={"rubrique"}),
    AssistantDomain.BILAN: _definition("Bilan comptable", "bilan|actif|passif", groups={"rubrique"}),
    AssistantDomain.PRE_CLOTURE: _definition("Contrôles de pré-clôture", "pre cloture|precloture|controle cloture", groups={"module", "severite"}),
    AssistantDomain.CLOTURE: _definition("État de clôture", "cloture|clore exercice", filters={"statut"}),
    AssistantDomain.AUDIT: _definition("Journal d'audit réservé aux administrateurs", "audit|historique|journal activite|journal d activite|trace|qui a modifie|qui a change|modification|changement", filters={"statut", "numero_facture"}, groups={"action", "utilisateur"}),
}


CONCEPTS: dict[str, tuple[str, ...]] = {
    "paye": ("paye", "payee", "reglee", "soldee"),
    "partiel": ("partiel", "partiellement", "acompte"),
    "impaye": ("impaye", "non paye", "non regle", "reste a payer"),
    "valide": ("valide", "confirme", "approuve"),
    "a_verifier": ("a verifier", "ambigu", "anomalie", "en erreur"),
    "compare": ("compare", "comparaison", "evolution", "versus", "vs"),
    "count": ("combien", "nombre", "compte les"),
    "sum": ("total", "somme", "montant total", "chiffre"),
    "list": ("liste", "affiche", "montre", "quels", "quelles", "disponible", "disponibles"),
}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.lower().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9%.,/' -]", " ", value)).strip()


def detect_concepts(question: str) -> set[str]:
    normalized = normalize_text(question)
    return {name for name, terms in CONCEPTS.items() if any(term in normalized for term in terms)}


def _semantic_words(value: str) -> list[str]:
    value = normalize_text(value).replace("-", " ").replace("'", " ")
    words = re.findall(r"[a-z0-9]+", value)
    normalized = []
    for word in words:
        if len(word) > 4 and word.endswith("s"):
            word = word[:-1]
        normalized.append(word)
    return normalized


def rank_domains(question: str) -> list[tuple[AssistantDomain, int]]:
    question_words = _semantic_words(question)
    ranked: list[tuple[AssistantDomain, int]] = []
    for domain, definition in REGISTRY.items():
        score = 0
        for term in definition.terms:
            term_words = _semantic_words(term)
            if not term_words:
                continue
            size = len(term_words)
            if any(question_words[index:index + size] == term_words for index in range(len(question_words) - size + 1)):
                score += 3 if size > 1 else 1
        if score:
            ranked.append((domain, score))
    ranked = sorted(ranked, key=lambda item: (-item[1], item[0].value))
    if ranked and ranked[0][0] == AssistantDomain.A_VERIFIER and len(ranked) > 1:
        concrete = next((item for item in ranked[1:] if item[0] != AssistantDomain.ALERTES), None)
        if concrete:
            ranked.remove(concrete)
            ranked.insert(0, concrete)
    return ranked


def validate_plan(plan: QueryPlan) -> None:
    if plan.domain == AssistantDomain.UNKNOWN:
        return
    definition = REGISTRY.get(plan.domain)
    if not definition or plan.operation not in definition.operations:
        raise ValueError("Combinaison domaine/opération non autorisée.")
    used = set(plan.filters.model_dump(exclude_none=True, exclude_defaults=True))
    disallowed = used - definition.filters
    if disallowed:
        raise ValueError(f"Filtres non autorisés pour ce domaine: {', '.join(sorted(disallowed))}")
    if plan.group_by and plan.group_by not in definition.groups:
        raise ValueError("Regroupement non autorisé pour ce domaine.")
    if plan.sort and plan.sort.field not in definition.sorts:
        raise ValueError("Tri non autorisé pour ce domaine.")


def prompt_catalog(domains: list[AssistantDomain]) -> str:
    lines = []
    for domain in domains:
        definition = REGISTRY[domain]
        lines.append(
            f"- {domain.value}: {definition.description}; opérations="
            f"{','.join(sorted(value.value for value in definition.operations))}; "
            f"filtres={','.join(sorted(definition.filters))}; groupes={','.join(sorted(definition.groups)) or 'aucun'}"
        )
    return "\n".join(lines)
