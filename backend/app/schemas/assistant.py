"""Contrats structurés de l'Assistant ComptaFlow."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field


class AssistantQuery(BaseModel):
    question: str = Field(min_length=2, max_length=1500)
    conversation_id: uuid.UUID | None = None
    context_document_id: uuid.UUID | None = None
    entreprise_id: uuid.UUID | None = None
    page: int = Field(default=1, ge=1, le=100)


class AssistantAction(BaseModel):
    label: str
    kind: Literal["route", "secure_file"]
    route: str | None = None
    api_path: str | None = None
    filename: str | None = None


class AssistantSource(BaseModel):
    resource_type: str
    resource_id: uuid.UUID
    label: str
    route: str | None = None


class AssistantDocumentCard(BaseModel):
    document_id: uuid.UUID
    entreprise_id: uuid.UUID | None = None
    entreprise: str | None = None
    categorie: str | None = None
    tiers: str | None = None
    numero_facture: str | None = None
    date_facture: date | None = None
    date_importation: datetime
    montant_ht: Decimal | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal | None = None
    devise: str = "MAD"
    statut_document: str
    statut_ecriture: str | None = None
    statut_paiement: str | None = None
    montant_regle: Decimal | None = None
    restant_du: Decimal | None = None
    saisie_topaze: bool = False
    anomalies: list[str] = Field(default_factory=list)
    donnees_extraites: dict[str, Any] | None = None
    actions: list[AssistantAction] = Field(default_factory=list)


class AssistantPaymentCard(BaseModel):
    mouvement_id: uuid.UUID
    ecriture_id: uuid.UUID
    date_operation: date
    montant_mouvement: Decimal
    montant_affecte: Decimal
    restant_du: Decimal
    reference: str | None = None
    libelle: str
    statut: str
    actions: list[AssistantAction] = Field(default_factory=list)


class AssistantCompanyCard(BaseModel):
    entreprise_id: uuid.UUID
    nom: str
    ice: str | None = None
    identifiant_fiscal: str | None = None
    is_active: bool
    actions: list[AssistantAction] = Field(default_factory=list)


class AssistantDataCard(BaseModel):
    """Carte générique sûre pour les résultats non documentaires."""

    resource_type: str
    resource_id: uuid.UUID
    title: str
    subtitle: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    actions: list[AssistantAction] = Field(default_factory=list)


class AssistantResponse(BaseModel):
    conversation_id: uuid.UUID
    response_type: Literal[
        "single_document", "document_list", "aggregate", "accounting_detail",
        "company_list", "message", "clarification", "no_result", "error",
        "data_list",
    ]
    intent: str
    message: str
    filters: dict[str, Any] = Field(default_factory=dict)
    documents: list[AssistantDocumentCard] = Field(default_factory=list)
    companies: list[AssistantCompanyCard] = Field(default_factory=list)
    payments: list[AssistantPaymentCard] = Field(default_factory=list)
    data: list[AssistantDataCard] = Field(default_factory=list)
    total_count: int | None = None
    aggregate: dict[str, Any] | None = None
    sources: list[AssistantSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    context_document_id: uuid.UUID | None = None
    suggestions: list[str] = Field(default_factory=list)
    plan_summary: dict[str, Any] = Field(default_factory=dict)
    page: int = 1
    page_size: int = 10
    has_more: bool = False
