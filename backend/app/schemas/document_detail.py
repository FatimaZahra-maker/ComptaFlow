"""Schémas de sortie de la page de détail d'un document."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import StatutDocumentEnum
from app.schemas.mouvement_bancaire import MouvementBancaireOut


class EcritureResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type_ecriture: str
    numero_piece: str | None = None
    date_piece: date | None = None
    tiers: str | None = None
    montant_ht: Decimal | None = None
    taux_tva: str | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal
    statut_validation: str
    anomalie_detectee: bool = False
    anomalie_details: str | None = None


class DocumentDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom_fichier_original: str
    taille_octets: int | None = None
    mime_type: str | None = None
    statut: StatutDocumentEnum
    created_at: datetime

    entreprise_id: uuid.UUID | None = None
    annee: int | None = None
    mois: int | None = None
    categorie: str | None = None

    texte_ocr: str | None = None
    donnees_extraites: dict | None = None
    message_erreur: str | None = None
    type_erreur: str | None = None
    error_code: str | None = None
    saisie_topaze: bool = False

    ecriture: EcritureResumeOut | None = None
    mouvements_bancaires: list[MouvementBancaireOut] = Field(default_factory=list)
