"""Schéma de la vue Chronos : document + écriture associée."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DocumentChronoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom_fichier_original: str
    statut: str
    categorie: str | None = None
    annee: int | None = None
    mois: int | None = None
    entreprise_id: uuid.UUID | None = None
    entreprise_nom: str | None = None
    created_at: datetime

    ecriture_id: uuid.UUID | None = None
    numero_piece: str | None = None
    date_piece: date | None = None
    tiers: str | None = None
    montant_ht: Decimal | None = None
    taux_tva: str | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal | None = None
    statut_validation: str | None = None
    anomalie_detectee: bool = False
    anomalie_details: str | None = None

    # Désormais porté par Document pour fonctionner aussi avec Banque.
    saisie_topaze: bool = False
