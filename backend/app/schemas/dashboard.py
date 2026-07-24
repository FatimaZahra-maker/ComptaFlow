"""
app/schemas/dashboard.py

Schéma de sortie du tableau de bord (Phase 6). Comme les registres
(Phase 5), rien n'est stocké : tout est calculé à la volée à partir des
documents et écritures existants, filtré sur le cabinet de l'utilisateur
connecté.
"""
from decimal import Decimal

from pydantic import BaseModel


class DocumentsParStatut(BaseModel):
    en_attente: int
    en_traitement: int
    traite: int
    valide: int
    erreur: int


class EcrituresParStatutValidation(BaseModel):
    brouillon: int
    a_verifier: int
    valide: int
    rejete: int


class DashboardOut(BaseModel):
    # --- Documents (Phase 6, bloc "Documents") ---
    total_documents: int
    documents_par_statut: DocumentsParStatut

    # --- Écritures (bloc validation) ---
    total_ecritures: int
    ecritures_par_statut: EcrituresParStatutValidation

    # --- TVA (bloc "TVA collectée / déductible / nette") ---
    # Calculée uniquement sur les écritures VALIDEES :
    # - TVA collectée = TVA des écritures de type "vente"
    # - TVA déductible = TVA des écritures de type "achat"
    tva_collectee: Decimal
    tva_deductible: Decimal
    tva_nette: Decimal

    # --- Autres compteurs (bloc "Clients / Fournisseurs / ...") ---
    total_entreprises: int