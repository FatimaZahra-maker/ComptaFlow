"""Schémas API du Bilan technique ComptaFlow."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.ledger import ControleGrandLivreBalanceOut


class BilanCompteDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compte: str
    libelle_compte: str | None = None
    rubrique: str
    cote: str
    debit: Decimal
    credit: Decimal
    solde_debiteur: Decimal
    solde_crediteur: Decimal
    montant_bilan: Decimal
    est_compte_correcteur: bool


class BilanOut(BaseModel):
    entreprise_id: uuid.UUID
    annee: int
    date_cloture: date

    actif_immobilise_brut: Decimal
    amortissements_provisions_immobilisations: Decimal
    actif_immobilise_net: Decimal

    actif_circulant_brut: Decimal
    provisions_actif_circulant: Decimal
    actif_circulant_net: Decimal

    tresorerie_actif: Decimal
    total_actif: Decimal

    financement_permanent_comptabilise: Decimal
    passif_circulant: Decimal
    tresorerie_passif: Decimal
    total_passif_comptable: Decimal

    resultat_net_cpc: Decimal
    resultat_cpc_integre: bool
    total_passif_technique: Decimal

    ecart_avant_resultat_cpc: Decimal
    ecart_bilan: Decimal
    equilibre: bool

    nombre_lignes: int
    nombre_comptes: int
    a_verifier: bool
    raisons_verification: list[str]
    comptes: list[BilanCompteDetailOut]
    source_calcul: str


class BilanRubriqueV2Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    libelle: str
    montant: Decimal


class ControleResultatBilanV2Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    resultat_cpc: Decimal
    resultat_comptabilise: Decimal
    resultat_non_affecte: Decimal
    deja_comptabilise: bool
    coherent: bool
    statut: str


class BilanV2Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entreprise_id: uuid.UUID
    exercice: int
    date_cloture: date
    actif: list[BilanRubriqueV2Out]
    passif: list[BilanRubriqueV2Out]
    total_actif: Decimal
    total_passif: Decimal
    ecart: Decimal
    resultat_cpc: Decimal
    resultat_non_affecte: Decimal
    resultat_deja_comptabilise: bool
    bilan_equilibre: bool
    controle_resultat: ControleResultatBilanV2Out
    controle_grand_livre_balance: ControleGrandLivreBalanceOut
    comptes: list[BilanCompteDetailOut]
    comptes_non_classes: list[BilanCompteDetailOut]
    anomalies: list[str]
    statut: str
    nombre_lignes: int
    nombre_comptes: int
    source_calcul: str
    nature_etat: str = "bilan_provisoire_de_controle"
    completude: str = "potentiellement_incomplet"
    raisons_incompletude: list[str] = []
    avertissement_limite: str = (
        "Bilan provisoire calculé uniquement à partir des données présentes dans ComptaFlow. "
        "Il ne remplace pas le bilan officiel produit dans Topaze."
    )
