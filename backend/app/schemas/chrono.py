"""
app/schemas/chrono.py

Schéma de sortie pour la vue Chrono — un vrai tableau comptable :
document + écriture liée (si elle existe) dans une seule ligne, pour
que le comptable voie tout d'un coup d'œil sans naviguer.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class DocumentChronoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom_fichier_original: str
    statut: str
    categorie: str | None
    annee: int | None
    mois: int | None
    entreprise_id: uuid.UUID | None
    entreprise_nom: str | None = None
    created_at: datetime

    # --- Écriture comptable liée (None si pas encore traité) ---
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
    saisie_topaze: bool = False