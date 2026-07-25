"""app/schemas/mouvement_bancaire.py"""
import uuid
from datetime import date
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class MouvementBancaireOut(BaseModel):
    """Schéma de sortie pour une ligne de relevé bancaire."""
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