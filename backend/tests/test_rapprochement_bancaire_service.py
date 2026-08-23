from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.enums import TypeEcritureEnum, TypeMouvementBancaireEnum
from app.services.rapprochement_bancaire_service import (
    evaluer_candidat,
    type_ecriture_attendu,
)


def mouvement(*, type_mouvement, montant, date_operation, libelle):
    return SimpleNamespace(
        type_mouvement=type_mouvement,
        montant=Decimal(montant),
        date_operation=date_operation,
        libelle=libelle,
    )


def ecriture(*, montant_ttc, date_piece, tiers):
    return SimpleNamespace(
        montant_ttc=Decimal(montant_ttc),
        date_piece=date_piece,
        tiers=tiers,
    )


def test_debit_attend_achat_et_credit_attend_vente():
    assert type_ecriture_attendu(TypeMouvementBancaireEnum.DEBIT) == TypeEcritureEnum.ACHAT
    assert type_ecriture_attendu(TypeMouvementBancaireEnum.CREDIT) == TypeEcritureEnum.VENTE


def test_montant_different_refuse_le_candidat():
    m = mouvement(
        type_mouvement=TypeMouvementBancaireEnum.DEBIT,
        montant="100.00",
        date_operation=date(2026, 5, 10),
        libelle="PAIEMENT FOURNISSEUR",
    )
    e = ecriture(montant_ttc="99.00", date_piece=date(2026, 5, 1), tiers="FOURNISSEUR TEST")
    assert evaluer_candidat(m, e) is None


def test_meme_montant_date_proche_et_tiers_donne_score_fort():
    m = mouvement(
        type_mouvement=TypeMouvementBancaireEnum.DEBIT,
        montant="11760.00",
        date_operation=date(2026, 5, 15),
        libelle="VIR VERS ELAZHAR",
    )
    e = ecriture(montant_ttc="11760.00", date_piece=date(2026, 5, 12), tiers="ELAZHAR SARL")
    result = evaluer_candidat(m, e)
    assert result is not None
    score, raisons = result
    assert score >= Decimal("90.00")
    assert any("Tiers" in raison for raison in raisons)


def test_facture_trop_lointaine_est_refusee():
    m = mouvement(
        type_mouvement=TypeMouvementBancaireEnum.CREDIT,
        montant="1000.00",
        date_operation=date(2026, 12, 31),
        libelle="VIREMENT RECU CLIENT",
    )
    e = ecriture(montant_ttc="1000.00", date_piece=date(2026, 1, 1), tiers="CLIENT TEST")
    assert evaluer_candidat(m, e) is None
