"""Schémas API du Grand Livre et de la Balance."""
import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LigneGrandLivreOut(BaseModel):
    id: uuid.UUID
    date_ecriture: date
    journal: str
    numero_piece: str | None = None
    compte: str
    libelle: str
    debit: Decimal
    credit: Decimal
    solde_cumule: Decimal
    origine: str
    ecriture_id: uuid.UUID | None = None
    mouvement_bancaire_id: uuid.UUID | None = None
    regularisation_cloture_id: uuid.UUID | None = None


class CompteGrandLivreOut(BaseModel):
    compte: str
    libelle_compte: str | None = None
    solde_initial: Decimal
    total_debit: Decimal
    total_credit: Decimal
    solde_final: Decimal
    lignes: list[LigneGrandLivreOut]


class GrandLivreOut(BaseModel):
    entreprise_id: uuid.UUID
    date_debut: date | None = None
    date_fin: date | None = None
    nombre_comptes: int
    nombre_lignes: int
    total_debit: Decimal
    total_credit: Decimal
    equilibre: bool
    comptes: list[CompteGrandLivreOut]


class LigneBalanceOut(BaseModel):
    compte: str
    libelle_compte: str | None = None
    total_debit: Decimal
    total_credit: Decimal
    solde_debiteur: Decimal
    solde_crediteur: Decimal


class BalanceOut(BaseModel):
    entreprise_id: uuid.UUID
    date_debut: date | None = None
    date_fin: date | None = None
    nombre_comptes: int
    total_debit: Decimal
    total_credit: Decimal
    total_solde_debiteur: Decimal
    total_solde_crediteur: Decimal
    equilibree: bool
    lignes: list[LigneBalanceOut]


class ReconstructionLedgerOut(BaseModel):
    entreprise_id: uuid.UUID
    ecritures_total: int
    ecritures_completes: int
    ecritures_incompletes: int
    mouvements_total: int
    mouvements_complets: int
    mouvements_incomplets: int
    lignes_total: int


class ControleGrandLivreBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    total_debit_grand_livre: Decimal
    total_credit_grand_livre: Decimal
    total_debit_balance: Decimal
    total_credit_balance: Decimal
    coherent: bool
    groupes_sources_desequilibres: int
