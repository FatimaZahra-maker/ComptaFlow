"""
app/schemas/document_detail.py

Schéma de sortie pour la vue "Détail document". Agrège métadonnées,
texte OCR, données extraites, et l'écriture comptable liée.

SPRINT 1.1 : ajout de type_erreur et error_code, pour que le frontend
puisse afficher un message adapté (ex: bouton "relancer" visible
seulement si type_erreur == "definitive").
"""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatutDocumentEnum
from app.schemas.mouvement_bancaire import MouvementBancaireOut


class EcritureResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type_ecriture: str
    numero_piece: str | None
    date_piece: str | None
    tiers: str | None
    
    # --- MODIFICATIONS ICI : HT, Taux TVA et TVA optionnels ---
    montant_ht: Decimal | None = None
    taux_tva: str | None = None
    montant_tva: Decimal | None = None
    montant_ttc: Decimal
    
    statut_validation: str
    anomalie_detectee: bool
    anomalie_details: str | None


class DocumentDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nom_fichier_original: str
    taille_octets: Optional[int]
    mime_type: Optional[str]
    statut: StatutDocumentEnum
    created_at: datetime

    entreprise_id: Optional[uuid.UUID]
    annee: Optional[int]
    mois: Optional[int]
    categorie: Optional[str]

    texte_ocr: Optional[str]
    donnees_extraites: Optional[dict]
    message_erreur: Optional[str]
    type_erreur: Optional[str] = None
    error_code: Optional[str] = None

    ecriture: Optional[EcritureResumeOut] = None
    
    # --- NOUVEAU : Le document renvoie aussi ses mouvements bancaires s'il y en a ---
    mouvements_bancaires: list[MouvementBancaireOut] = []