"""
app/schemas/rapport.py

Schéma de sortie d'un rapport de synthèse : agrège, pour une
entreprise et une période données, les indicateurs déjà calculés
ailleurs dans l'application (documents traités, écritures validées,
TVA, anomalies) en une seule vue destinée à être imprimée/exportée.
"""
import uuid
from decimal import Decimal

from pydantic import BaseModel


class RapportOut(BaseModel):
    entreprise_id: uuid.UUID
    entreprise_nom: str
    annee: int
    mois: int | None  # None si le rapport couvre l'année entière

    nombre_documents: int
    nombre_documents_erreur: int
    nombre_ecritures_validees: int
    nombre_ecritures_a_verifier: int
    nombre_anomalies: int

    total_achats_ht: Decimal
    total_ventes_ht: Decimal
    tva_collectee: Decimal
    tva_deductible: Decimal
    tva_nette: Decimal