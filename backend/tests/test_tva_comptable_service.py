from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import uuid

from app.models.enums import TypeEcritureEnum
from app.services.tva_comptable_service import (
    NATURE_COLLECTEE,
    NATURE_DEDUCTIBLE_CHARGES,
    NATURE_DEDUCTIBLE_IMMOBILISATIONS,
    classifier_compte_tva,
    construire_synthese_tva,
)


def _line(
    *,
    month: int,
    compte: str,
    debit: str = "0.00",
    credit: str = "0.00",
    entry_id=None,
):
    return SimpleNamespace(
        date_ecriture=date(2026, month, 15),
        compte=compte,
        debit=Decimal(debit),
        credit=Decimal(credit),
        ecriture_id=entry_id,
    )


def _entry(
    *,
    month: int,
    kind: TypeEcritureEnum,
    tva: str,
    compte_tva: str | None,
    entry_id=None,
):
    return SimpleNamespace(
        id=entry_id or uuid.uuid4(),
        date_piece=date(2026, month, 10),
        type_ecriture=kind,
        montant_tva=Decimal(tva),
        compte_tva=compte_tva,
    )


def test_classifier_compte_tva_reconnait_les_trois_familles():
    assert classifier_compte_tva("445500000000") == NATURE_COLLECTEE
    assert classifier_compte_tva("345520000000") == NATURE_DEDUCTIBLE_CHARGES
    assert (
        classifier_compte_tva("345510000000")
        == NATURE_DEDUCTIBLE_IMMOBILISATIONS
    )


def test_classifier_refuse_un_compte_hors_familles_tva():
    assert classifier_compte_tva("612100000000") is None
    assert classifier_compte_tva(None) is None


def test_mai_calcule_collectee_charges_immo_et_solde():
    entreprise_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    buy_charge_id = uuid.uuid4()
    buy_asset_id = uuid.uuid4()

    result = construire_synthese_tva(
        entreprise_id=entreprise_id,
        annee=2026,
        lignes=[
            _line(
                month=5,
                compte="445500000000",
                credit="400.00",
                entry_id=sale_id,
            ),
            _line(
                month=5,
                compte="345520000000",
                debit="150.00",
                entry_id=buy_charge_id,
            ),
            _line(
                month=5,
                compte="345510000000",
                debit="50.00",
                entry_id=buy_asset_id,
            ),
        ],
        ecritures=[
            _entry(
                month=5,
                kind=TypeEcritureEnum.VENTE,
                tva="400.00",
                compte_tva="445500000000",
                entry_id=sale_id,
            ),
            _entry(
                month=5,
                kind=TypeEcritureEnum.ACHAT,
                tva="150.00",
                compte_tva="345520000000",
                entry_id=buy_charge_id,
            ),
            _entry(
                month=5,
                kind=TypeEcritureEnum.ACHAT,
                tva="50.00",
                compte_tva="345510000000",
                entry_id=buy_asset_id,
            ),
        ],
    )

    may = result.mensualites[4]
    assert may.tva_collectee == Decimal("400.00")
    assert may.tva_deductible_charges == Decimal("150.00")
    assert may.tva_deductible_immobilisations == Decimal("50.00")
    assert may.tva_deductible == Decimal("200.00")
    assert may.tva_nette == Decimal("200.00")
    assert may.tva_a_payer == Decimal("200.00")
    assert may.credit_tva == Decimal("0.00")
    assert may.a_verifier is False


def test_credit_tva_technique_si_deductible_superieure_a_collectee():
    entreprise_id = uuid.uuid4()
    sale_id = uuid.uuid4()
    buy_id = uuid.uuid4()

    result = construire_synthese_tva(
        entreprise_id=entreprise_id,
        annee=2026,
        lignes=[
            _line(month=6, compte="445500000000", credit="100.00", entry_id=sale_id),
            _line(month=6, compte="345520000000", debit="250.00", entry_id=buy_id),
        ],
        ecritures=[
            _entry(
                month=6,
                kind=TypeEcritureEnum.VENTE,
                tva="100.00",
                compte_tva="445500000000",
                entry_id=sale_id,
            ),
            _entry(
                month=6,
                kind=TypeEcritureEnum.ACHAT,
                tva="250.00",
                compte_tva="345520000000",
                entry_id=buy_id,
            ),
        ],
    )

    june = result.mensualites[5]
    assert june.tva_nette == Decimal("-150.00")
    assert june.tva_a_payer == Decimal("0.00")
    assert june.credit_tva == Decimal("150.00")


def test_facture_tva_positive_sans_ligne_grand_livre_est_a_verifier():
    entry = _entry(
        month=7,
        kind=TypeEcritureEnum.ACHAT,
        tva="200.00",
        compte_tva="345520000000",
    )

    result = construire_synthese_tva(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[],
        ecritures=[entry],
    )

    july = result.mensualites[6]
    assert july.a_verifier is True
    assert any("aucune ligne TVA" in reason for reason in july.raisons_verification)


def test_compte_tva_vente_incompatible_est_a_verifier():
    entry_id = uuid.uuid4()
    entry = _entry(
        month=8,
        kind=TypeEcritureEnum.VENTE,
        tva="200.00",
        compte_tva="345520000000",
        entry_id=entry_id,
    )

    result = construire_synthese_tva(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            _line(
                month=8,
                compte="345520000000",
                debit="200.00",
                entry_id=entry_id,
            )
        ],
        ecritures=[entry],
    )

    august = result.mensualites[7]
    assert august.a_verifier is True
    assert any("vente" in reason.lower() and "4455" in reason for reason in august.raisons_verification)


def test_ecart_entre_facture_et_ligne_tva_est_a_verifier():
    entry_id = uuid.uuid4()
    entry = _entry(
        month=9,
        kind=TypeEcritureEnum.ACHAT,
        tva="200.00",
        compte_tva="345520000000",
        entry_id=entry_id,
    )

    result = construire_synthese_tva(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            _line(
                month=9,
                compte="345520000000",
                debit="199.00",
                entry_id=entry_id,
            )
        ],
        ecritures=[entry],
    )

    september = result.mensualites[8]
    assert september.a_verifier is True
    assert any("écart" in reason.lower() for reason in september.raisons_verification)


def test_reprise_au_debit_du_compte_collecte_diminue_la_tva_collectee():
    result = construire_synthese_tva(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            _line(month=10, compte="445500000000", credit="300.00"),
            _line(month=10, compte="445500000000", debit="50.00"),
        ],
        ecritures=[],
    )

    october = result.mensualites[9]
    assert october.tva_collectee == Decimal("250.00")
