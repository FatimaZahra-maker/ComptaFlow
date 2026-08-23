"""Schémas API du Compte de Produits et Charges (CPC)."""

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.ledger import ControleGrandLivreBalanceOut


class CpcCompteDetailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    compte: str
    libelle_compte: str | None = None
    rubrique: str
    debit: Decimal
    credit: Decimal
    montant: Decimal


class CpcOut(BaseModel):
    entreprise_id: uuid.UUID
    annee: int
    date_debut: date
    date_fin: date

    produits_exploitation: Decimal
    charges_exploitation: Decimal
    resultat_exploitation: Decimal

    produits_financiers: Decimal
    charges_financieres: Decimal
    resultat_financier: Decimal

    resultat_courant: Decimal

    produits_non_courants: Decimal
    charges_non_courantes: Decimal
    resultat_non_courant: Decimal

    resultat_avant_impots: Decimal
    impots_sur_resultats: Decimal
    resultat_net: Decimal

    nombre_lignes: int
    nombre_comptes: int
    a_verifier: bool
    raisons_verification: list[str]
    comptes: list[CpcCompteDetailOut]
    source_calcul: str


class CpcComparaisonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    libelle: str
    montant_n: Decimal
    montant_n_1: Decimal | None
    variation_mad: Decimal | None
    variation_pct: Decimal | None


class CpcV2Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entreprise_id: uuid.UUID
    exercice: int
    exercice_precedent: int
    donnees_n_1_disponibles: bool
    rubriques: list[CpcComparaisonOut]
    resultats: list[CpcComparaisonOut]
    comptes: list[CpcCompteDetailOut]
    comptes_non_classes: list[CpcCompteDetailOut]
    anomalies: list[str]
    statut: str
    controle_grand_livre_balance: ControleGrandLivreBalanceOut
    nombre_lignes: int
    nombre_comptes: int
    source_calcul: str
