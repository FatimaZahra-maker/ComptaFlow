"""Schémas de sortie du registre comptable et de la TVA comptable."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.ecriture import EcritureOut


class RegistreOptionOut(BaseModel):
    """Combinaison de filtres contenant au moins une écriture validée."""

    entreprise_id: uuid.UUID
    categorie: str
    annee: int
    mois: int
    nombre: int


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


class TvaCompteDetailOut(BaseModel):
    compte: str
    nature: str
    debit: str
    credit: str
    montant_net: str


class TvaMensuelle(BaseModel):
    mois: int
    annee: int

    # Compatibilité avec l'ancienne interface.
    tva_collectee: str
    tva_deductible: str
    tva_nette: str
    nombre_ecritures: int

    # Détail comptable V2.
    tva_deductible_charges: str
    tva_deductible_immobilisations: str
    tva_a_payer: str
    credit_tva: str
    nombre_lignes_tva: int
    a_verifier: bool
    raisons_verification: list[str]
    comptes: list[TvaCompteDetailOut]


class TvaAnnuelleOut(BaseModel):
    entreprise_id: uuid.UUID
    annee: int
    mensualites: list[TvaMensuelle]

    total_tva_collectee: str
    total_tva_deductible_charges: str
    total_tva_deductible_immobilisations: str
    total_tva_deductible: str
    total_tva_nette: str

    # Ces deux totaux sont techniques : ils additionnent les positions
    # mensuelles sans appliquer un report fiscal entre périodes.
    total_tva_a_payer_technique: str
    total_credit_tva_technique: str

    nombre_mois_a_verifier: int
    source_calcul: str
    declaration_fiscale_prete: bool
    limites: list[str]
