"""Schémas Pydantic des écritures comptables."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TauxTVAEnum


class EcritureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    entreprise_id: uuid.UUID
    type_ecriture: str
    numero_piece: str | None = None
    date_piece: date | None = None
    tiers: str | None = None
    compte_tiers: str | None = None
    compte_tva: str | None = None
    compte_ht: str | None = None
    libelle: str | None = None
    montant_ht: Decimal | None = None
    taux_tva: str | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal
    statut_validation: str
    anomalie_detectee: bool = False
    anomalie_details: str | None = None
    doublon_potentiel_id: uuid.UUID | None = None
    validated_by: uuid.UUID | None = None
    created_at: datetime
    saisie_topaze: bool = False
    ready_for_topaze_at: datetime | None = None
    topaze_entered_at: datetime | None = None
    topaze_entered_by: uuid.UUID | None = None
    topaze_batch_reference: str | None = None

    # Métadonnées utiles aux tableaux frontend. Elles proviennent des jointures
    # avec Document et Entreprise et ne sont pas stockées deux fois.
    nom_fichier_document: str | None = None
    entreprise_nom: str | None = None
    categorie_document: str | None = None
    statut_document: str | None = None

    # Métadonnées devise venant de Document.donnees_extraites.
    devise_originale: str | None = None
    montant_ht_devise: Decimal | None = None
    montant_tva_devise: Decimal | None = None
    montant_ttc_devise: Decimal | None = None
    montant_ht_mad: Decimal | None = None
    montant_tva_mad: Decimal | None = None
    montant_ttc_mad: Decimal | None = None
    date_cours_change: date | None = None
    type_cours_change: str | None = None
    taux_change: Decimal | None = None
    unite_cotation: int | None = None
    source_cours_change: str | None = None
    conversion_devise_statut: str | None = None


class EcritureUpdate(BaseModel):
    tiers: str | None = Field(default=None, max_length=255)
    numero_piece: str | None = Field(default=None, max_length=100)
    date_piece: date | None = None
    montant_ht: Decimal | None = Field(default=None, ge=0)
    taux_tva: TauxTVAEnum | None = None
    montant_tva: Decimal | None = Field(default=None, ge=0)
    montant_ttc: Decimal | None = Field(default=None, ge=0)
    compte_tiers: str | None = Field(default=None, max_length=30)
    compte_tva: str | None = Field(default=None, max_length=30)
    compte_ht: str | None = Field(default=None, max_length=30)
    libelle: str | None = Field(default=None, max_length=500)


class TopazeMarkRequest(BaseModel):
    saisie: bool = True
    reference_lot: str | None = Field(default=None, max_length=100)
