"""Schémas Pydantic des mouvements bancaires et rapprochements Banque V2."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.enums import TypeMouvementBancaireEnum

NatureOperation = Literal[
    "reglement_facture",
    "acompte",
    "frais_bancaire",
    "virement_interne",
    "autre",
]


class AllocationRapprochementOut(BaseModel):
    id: uuid.UUID
    ecriture_id: uuid.UUID
    numero_piece: str | None = None
    date_piece: date | None = None
    tiers: str | None = None
    type_ecriture: str | None = None
    montant_ttc: Decimal | None = None
    montant_affecte: Decimal
    montant_devise_affecte: Decimal | None = None
    valeur_comptable_mad: Decimal | None = None
    montant_reglement_mad: Decimal | None = None
    ecart_change_mad: Decimal | None = None
    nature_ecart_change: str | None = None
    compte_ecart_change: str | None = None
    statut_ecart_change: str = "non_requis"
    raison_ecart_change: str | None = None
    montant_restant_facture_apres: Decimal | None = None
    statut: str
    score: Decimal | None = None
    raison: str | None = None


class AllocationRapprochementInput(BaseModel):
    ecriture_id: uuid.UUID
    montant_affecte: Decimal = Field(gt=0)
    montant_devise_affecte: Decimal | None = Field(default=None, gt=0)


class AllocationRapprochementBatch(BaseModel):
    allocations: list[AllocationRapprochementInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_entries(self):
        ids = [item.ecriture_id for item in self.allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("Une facture ne peut apparaître qu'une fois dans le même rapprochement.")
        return self


class MouvementBancaireOut(BaseModel):
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

    devise_originale: str = "MAD"
    montant_devise: Decimal | None = None
    montant_mad: Decimal | None = None
    montant_mad_theorique: Decimal | None = None
    montant_mad_source: str = "mad"
    taux_change: Decimal | None = None
    type_cours_change: str | None = None
    date_cours_change: date | None = None
    unite_cotation: int | None = None
    source_cours_change: str | None = None

    compte_bancaire_entreprise_id: uuid.UUID | None = None
    nature_operation: str = "reglement_facture"
    compte_contrepartie: str | None = None
    mouvement_lie_id: uuid.UUID | None = None

    ecriture_rapprochee_id: uuid.UUID | None = None
    statut_rapprochement: str = "non_rapproche"
    mode_rapprochement: str = "simple"
    score_rapprochement: Decimal | None = None
    raison_rapprochement: str | None = None
    compte_banque: str | None = None
    rapprochement_confirme_par: uuid.UUID | None = None
    date_rapprochement: datetime | None = None

    created_at: datetime | None = None


class MouvementBancaireUpdate(BaseModel):
    date_operation: date | None = None
    libelle: str | None = Field(default=None, min_length=1, max_length=500)
    reference: str | None = Field(default=None, max_length=100)
    type_mouvement: TypeMouvementBancaireEnum | None = None
    montant: Decimal | None = Field(default=None, ge=0)
    solde_apres_operation: Decimal | None = None
    compte_bancaire_entreprise_id: uuid.UUID | None = None
    nature_operation: NatureOperation | None = None
    compte_contrepartie: str | None = Field(default=None, max_length=30)
    mouvement_lie_id: uuid.UUID | None = None


class MouvementBancaireListeOut(MouvementBancaireOut):
    entreprise_nom: str | None = None
    nom_fichier_document: str
    statut_document: str
    annee: int | None = None
    mois: int | None = None
    saisie_topaze: bool = False

    numero_piece_rapprochee: str | None = None
    date_piece_rapprochee: date | None = None
    tiers_rapproche: str | None = None
    type_ecriture_rapprochee: str | None = None
    montant_ttc_rapproche: Decimal | None = None

    montant_affecte_total: Decimal = Decimal("0.00")
    montant_non_affecte: Decimal = Decimal("0.00")
    nombre_allocations: int = 0
    allocations: list[AllocationRapprochementOut] = Field(default_factory=list)

    compte_bancaire_libelle: str | None = None
    compte_bancaire_rib: str | None = None
    compte_bancaire_iban: str | None = None


class RapprochementCandidatOut(BaseModel):
    ecriture_id: uuid.UUID
    numero_piece: str | None = None
    date_piece: date | None = None
    tiers: str | None = None
    type_ecriture: str
    montant_ttc: Decimal
    montant_deja_regle: Decimal = Decimal("0.00")
    montant_restant: Decimal
    montant_suggere: Decimal
    type_suggestion: str
    score: Decimal
    raisons: list[str]


class RapprochementResultOut(BaseModel):
    mouvement: MouvementBancaireOut
    candidats: list[RapprochementCandidatOut] = Field(default_factory=list)


class VirementInterneCandidatOut(BaseModel):
    mouvement_id: uuid.UUID
    date_operation: date
    libelle: str
    type_mouvement: str
    montant: Decimal
    compte_banque: str | None = None
    score: Decimal
    raisons: list[str]
