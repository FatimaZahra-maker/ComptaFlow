"""backend/app/schemas/document.py"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict

from app.models.enums import StatutDocumentEnum


class DocumentEntrepriseUpdate(BaseModel):
    entreprise_id: uuid.UUID


class DocumentOut(BaseModel):
    """Ce que l'API renvoie apres un upload ou une consultation."""
    id: uuid.UUID
    nom_fichier_original: str
    taille_octets: Optional[int]
    mime_type: Optional[str]
    statut: StatutDocumentEnum
    created_at: datetime

    # CORRECTIF : ces champs existaient déjà en base mais étaient
    # absents du schéma de sortie -- FastAPI les filtrait silencieusement
    # (response_model coupe tout champ non déclaré), d'où "—" partout
    # côté frontend malgré des données réelles en base.
    categorie: Optional[str] = None
    annee: Optional[int] = None
    mois: Optional[int] = None
    date_piece: Optional[str] = None

    implique_cabinet: bool = False
    traitement_cabinet_propre: bool = False
    role_cabinet: Optional[str] = None

    est_doublon: bool = False
    doublon_de_document_id: Optional[uuid.UUID] = None

    model_config = ConfigDict(from_attributes=True)
