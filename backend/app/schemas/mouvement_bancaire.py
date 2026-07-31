"""Schémas Pydantic des mouvements bancaires."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TypeMouvementBancaireEnum


class MouvementBancaireOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    entreprise_id: uuid.UUID
    date_operation: date
    libelle: str
    reference: str | None = None
    type_mouvement: str
    montant: Decimal
    solde_apres_operation: Decimal | None = None
    created_at: datetime | None = None


class MouvementBancaireUpdate(BaseModel):
    date_operation: date | None = None
    libelle: str | None = Field(default=None, min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=100)
    type_mouvement: TypeMouvementBancaireEnum | None = None
    montant: Decimal | None = Field(default=None, ge=0)
    solde_apres_operation: Decimal | None = None


class MouvementBancaireListeOut(MouvementBancaireOut):
    # Métadonnées du relevé source, nécessaires aux filtres et à l'affichage
    # de la page Banque sans refaire plusieurs appels HTTP.
    entreprise_nom: str | None = None
    nom_fichier_document: str
    statut_document: str
    annee: int | None = None
    mois: int | None = None
    saisie_topaze: bool = False