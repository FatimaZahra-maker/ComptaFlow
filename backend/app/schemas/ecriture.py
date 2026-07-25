"""
app/schemas/ecriture.py

Schémas Pydantic pour les écritures comptables. EcritureOut est le
format de sortie de toutes les routes /accounting/* et /registers.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class EcritureOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    entreprise_id: uuid.UUID
    type_ecriture: str
    numero_piece: str | None
    date_piece: date | None
    tiers: str | None
    
    # --- MODIFICATIONS ICI : HT, Taux TVA et TVA deviennent optionnels ---
    montant_ht: Decimal | None = None
    taux_tva: str | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal
    
    statut_validation: str
    anomalie_detectee: bool
    anomalie_details: str | None
    doublon_potentiel_id: uuid.UUID | None
    validated_by: uuid.UUID | None
    created_at: datetime

    # --- Ajout : nom du fichier source, pour affichage/consultation ---
    nom_fichier_document: str | None = None

    # --- Ajout : suivi de saisie dans le logiciel externe (Topaze) ---
    saisie_topaze: bool = False

# --- Ajout : payload de correction manuelle d'une écriture ---
# Tous les champs sont optionnels (exclude_unset côté route) pour ne
# modifier que ce que le comptable a réellement changé dans le formulaire.
class EcritureUpdate(BaseModel):
    tiers: str | None = None
    numero_piece: str | None = None
    date_piece: date | None = None
    montant_ht: Decimal | None = None
    taux_tva: str | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal | None = None