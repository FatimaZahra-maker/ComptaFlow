"""
app/schemas/rappel.py

Schémas Pydantic pour les alertes automatiques de la page Rappels &
Tâches. Contrairement à Tache (stockée en base, créée manuellement),
ces alertes sont calculées à la volée à chaque appel de l'API --
rien n'est stocké ici, exactement comme pour le Registre comptable.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel


class EcritureNonSaisieOut(BaseModel):
    """Une écriture validée mais pas encore ressaisie dans Topaze."""
    id: uuid.UUID
    entreprise_id: uuid.UUID
    entreprise_nom: str
    document_id: uuid.UUID
    nom_fichier_document: str
    tiers: str | None
    numero_piece: str | None
    date_piece: date | None
    montant_ttc: Decimal


class EntrepriseRetardOut(BaseModel):
    """
    Une entreprise dont le délai habituel entre 2 envois de documents
    est dépassé. Le "délai de référence" est calculé une seule fois par
    entreprise : l'écart entre son 1er et son 2e document jamais uploadé
    (règle métier demandée par l'utilisateur).
    """
    entreprise_id: uuid.UUID
    entreprise_nom: str
    dernier_upload: datetime
    delai_reference_jours: float
    jours_depuis_dernier_upload: float
    jours_de_retard: float


class AlertesRappelsOut(BaseModel):
    """Regroupe les 2 listes d'alertes automatiques en un seul appel API."""
    non_saisies: list[EcritureNonSaisieOut]
    entreprises_en_retard: list[EntrepriseRetardOut]