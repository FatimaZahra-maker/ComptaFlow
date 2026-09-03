"""Plan de requête fermé produit par le planificateur de l'assistant.

Le modèle ne contient volontairement aucun nom de table, colonne ou fragment SQL.
Toute valeur issue d'un LLM reste une entrée non fiable jusqu'à sa validation par
le registre sémantique et par le moteur multi-tenant.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AssistantDomain(StrEnum):
    ENTREPRISES = "entreprises"
    DOCUMENTS = "documents"
    FACTURES_ACHAT = "factures_achat"
    FACTURES_VENTE = "factures_vente"
    RELEVES_BANCAIRES = "releves_bancaires"
    DONNEES_EXTRAITES = "donnees_extraites"
    CHRONOS = "chronos"
    ECRITURES = "ecritures"
    LIGNES_ECRITURE = "lignes_ecriture"
    FOURNISSEURS = "fournisseurs"
    CLIENTS = "clients"
    MOUVEMENTS_BANCAIRES = "mouvements_bancaires"
    RAPPROCHEMENTS = "rapprochements"
    ALLOCATIONS = "allocations"
    PAIEMENTS = "paiements"
    COMPTES_BANCAIRES = "comptes_bancaires"
    PLAN_COMPTABLE = "plan_comptable"
    TVA = "tva"
    TACHES = "taches"
    ALERTES = "alertes"
    A_VERIFIER = "a_verifier"
    TOPAZE = "topaze"
    GRAND_LIVRE = "grand_livre"
    BALANCE = "balance"
    CPC = "cpc"
    BILAN = "bilan"
    PRE_CLOTURE = "pre_cloture"
    CLOTURE = "cloture"
    AUDIT = "audit"
    UNKNOWN = "unknown"


class QueryOperation(StrEnum):
    FIND_ONE = "find_one"
    LIST = "list"
    COUNT = "count"
    SUM = "sum"
    GROUP = "group"
    COMPARE = "compare"
    EXPLAIN = "explain"
    OPEN = "open"
    FOLLOW_UP = "follow_up"


class QueryEntity(StrEnum):
    ENTREPRISE = "entreprise"
    DOCUMENT = "document"
    FACTURE = "facture"
    ECRITURE = "ecriture"
    LIGNE = "ligne"
    TIERS = "tiers"
    MOUVEMENT = "mouvement"
    ALLOCATION = "allocation"
    COMPTE = "compte"
    TACHE = "tache"
    ETAT = "etat"
    EVENEMENT_AUDIT = "evenement_audit"
    GENERIC = "generic"


class PaymentStatus(StrEnum):
    PAYE = "paye"
    PARTIEL = "partiel"
    IMPAYE = "impaye"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class DateField(StrEnum):
    PIECE = "piece"
    IMPORTATION = "importation"
    OPERATION = "operation"
    ECHEANCE = "echeance"
    ECRITURE = "ecriture"


class QueryFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entreprise: str | None = Field(default=None, max_length=255)
    entreprise_id: uuid.UUID | None = None
    fournisseur: str | None = Field(default=None, max_length=255)
    client: str | None = Field(default=None, max_length=255)
    tiers: str | None = Field(default=None, max_length=255)
    numero_facture: str | None = Field(default=None, max_length=100)
    texte: str | None = Field(default=None, max_length=300)
    date_exacte: date | None = None
    date_type: DateField | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    annee: int | None = Field(default=None, ge=2000, le=2100)
    mois: int | None = Field(default=None, ge=1, le=12)
    mois_comparaison: list[int] = Field(default_factory=list, max_length=12)
    montant_exact: Decimal | None = Field(default=None, ge=0)
    montant_min: Decimal | None = Field(default=None, ge=0)
    montant_max: Decimal | None = Field(default=None, ge=0)
    statut: str | None = Field(default=None, max_length=50)
    statut_paiement: PaymentStatus | None = None
    statut_topaze: bool | None = None
    compte_prefixe: str | None = Field(default=None, max_length=30)
    resource_id: uuid.UUID | None = None
    resource_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)


class QuerySort(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    direction: SortDirection = SortDirection.DESC


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: AssistantDomain
    operation: QueryOperation
    entity: QueryEntity = QueryEntity.GENERIC
    filters: QueryFilters = Field(default_factory=QueryFilters)
    group_by: str | None = None
    sort: QuerySort | None = None
    limit: int = Field(default=10, ge=1, le=50)
    page: int = Field(default=1, ge=1, le=100)
    needs_clarification: bool = False
    clarification_question: str | None = Field(default=None, max_length=300)


class PlannerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan: QueryPlan
    provider: str = Field(pattern="^(groq|ollama|deterministic)$")
    ai_unavailable: bool = False
    normalized_question: str
