from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import uuid

from app.models.enums import TypeEcritureEnum, TypeMouvementBancaireEnum
from app.models.mouvement_bancaire import MouvementBancaire
from app.services.bank_account_service import normaliser_identifiant
from app.services.ligne_comptable_service import _construire_lignes_operation_speciale
from app.services.rapprochement_bancaire_service import (
    CandidatRapprochement,
    MODE_GROUPE,
    MODE_PARTIEL,
    _find_unique_group,
    _score_candidat,
)


def _movement(amount="600.00", movement_type=TypeMouvementBancaireEnum.DEBIT):
    return MouvementBancaire(
        cabinet_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        entreprise_id=uuid.uuid4(),
        date_operation=date(2026, 5, 22),
        libelle="VIR FOURNISSEUR ALPHA",
        type_mouvement=movement_type,
        montant=Decimal(amount),
        compte_banque="514100000000",
    )


def test_rib_iban_normalization_ignores_spaces_and_punctuation():
    assert normaliser_identifiant("MA64 0117-8000 0000") == "MA64011780000000"


def test_partial_candidate_is_identified_without_forcing_exact_match():
    movement = _movement("600.00")
    entry = SimpleNamespace(
        montant_ttc=Decimal("1000.00"),
        date_piece=date(2026, 5, 20),
        tiers="FOURNISSEUR ALPHA SARL",
    )
    result = _score_candidat(movement, entry, Decimal("1000.00"))
    assert result is not None
    score, reasons, mode = result
    assert mode == MODE_PARTIEL
    assert score >= Decimal("65.00")
    assert any("partiel" in reason.lower() for reason in reasons)


def test_unique_group_sum_is_detected():
    movement = _movement("1000.00")
    e1 = SimpleNamespace(date_piece=date(2026, 5, 10))
    e2 = SimpleNamespace(date_piece=date(2026, 5, 11))
    candidates = [
        CandidatRapprochement(e1, Decimal("0"), Decimal("400"), Decimal("400"), MODE_GROUPE, Decimal("70"), ("x",)),
        CandidatRapprochement(e2, Decimal("0"), Decimal("600"), Decimal("600"), MODE_GROUPE, Decimal("70"), ("x",)),
    ]
    group = _find_unique_group(movement, candidates)
    assert group is not None
    assert sum((item.montant_restant for item in group), Decimal("0")) == Decimal("1000")


def test_bank_fee_requires_exact_counterpart_account():
    movement = _movement("35.00")
    movement.nature_operation = "frais_bancaire"
    movement.compte_contrepartie = None
    result = _construire_lignes_operation_speciale(None, movement)  # type: ignore[arg-type]
    assert result.complet is False
    assert any("contrepartie" in reason.lower() for reason in result.raisons)


def test_bank_fee_generates_balanced_two_lines_when_account_is_configured():
    movement = _movement("35.00")
    movement.nature_operation = "frais_bancaire"
    movement.compte_contrepartie = "614700000000"
    result = _construire_lignes_operation_speciale(None, movement)  # type: ignore[arg-type]
    assert result.complet is True
    assert len(result.lignes) == 2
    assert sum((line["debit"] for line in result.lignes), Decimal("0")) == Decimal("35.00")
    assert sum((line["credit"] for line in result.lignes), Decimal("0")) == Decimal("35.00")


def test_credit_acompte_uses_bank_debit_and_counterpart_credit():
    movement = _movement("250.00", TypeMouvementBancaireEnum.CREDIT)
    movement.nature_operation = "acompte"
    movement.compte_contrepartie = "342100000000"
    result = _construire_lignes_operation_speciale(None, movement)  # type: ignore[arg-type]
    assert result.complet is True
    assert result.lignes[0]["compte"] == "514100000000"
    assert result.lignes[0]["debit"] == Decimal("250.00")
    assert result.lignes[1]["compte"] == "342100000000"
    assert result.lignes[1]["credit"] == Decimal("250.00")
