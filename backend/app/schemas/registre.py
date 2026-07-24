"""
app/schemas/registre.py

Schéma de sortie d'un "registre" (Phase 5 du projet) : un registre ne
stocke rien en base, il CALCULE les totaux HT/TVA/TTC à partir des
écritures comptables déjà validées, pour une entreprise, une catégorie,
une année et un mois donnés.

Réutilise EcritureOut (déjà existant dans app/schemas/ecriture.py) pour
la liste des lignes, afin de ne pas dupliquer un schéma d'écriture.
"""
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.ecriture import EcritureOut


class RegistreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    categorie: str
    entreprise_id: uuid.UUID
    annee: int
    mois: int

    nombre: int
    total_ht: Decimal
    total_tva: Decimal
    total_ttc: Decimal

    lignes: list[EcritureOut]