from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from app.models.tva_periode import TvaCreditUtilisation, TvaPeriode
from app.services.tva_comptable_service import calculer_position_tva_v2, valider_periode_tva


CONFIG = {
    "periodicite": "mensuelle",
    "prorata_applicable": False,
    "retenue_applicable": False,
}


def test_collectee_superieure_a_recuperable_donne_tva_a_payer():
    result = calculer_position_tva_v2(
        tva_collectee=Decimal("500"),
        tva_recuperable_charges=Decimal("120"),
        tva_recuperable_immobilisations=Decimal("30"),
        **CONFIG,
    )
    assert result.tva_nette == Decimal("350.00")
    assert result.tva_a_payer == Decimal("350.00")
    assert result.credit_a_reporter == Decimal("0.00")


def test_recuperable_superieure_a_collectee_donne_credit():
    result = calculer_position_tva_v2(
        tva_collectee=Decimal("100"),
        tva_recuperable_charges=Decimal("220"),
        tva_recuperable_immobilisations=Decimal("30"),
        **CONFIG,
    )
    assert result.tva_nette == Decimal("-150.00")
    assert result.credit_a_reporter == Decimal("150.00")


def test_credit_valide_est_reporte_sur_periode_suivante():
    first = calculer_position_tva_v2(
        tva_collectee=Decimal("100"),
        tva_recuperable_charges=Decimal("250"),
        tva_recuperable_immobilisations=Decimal("0"),
        **CONFIG,
    )
    second = calculer_position_tva_v2(
        tva_collectee=Decimal("300"),
        tva_recuperable_charges=Decimal("50"),
        tva_recuperable_immobilisations=Decimal("0"),
        credit_anterieur=first.credit_a_reporter,
        **CONFIG,
    )
    assert first.credit_a_reporter == Decimal("150.00")
    assert second.credit_anterieur == Decimal("150.00")
    assert second.tva_a_payer == Decimal("100.00")


def test_tva_immobilisation_reste_distincte_des_charges():
    result = calculer_position_tva_v2(
        tva_collectee=Decimal("400"),
        tva_recuperable_charges=Decimal("100"),
        tva_recuperable_immobilisations=Decimal("75"),
        **CONFIG,
    )
    assert result.tva_recuperable_charges == Decimal("100.00")
    assert result.tva_recuperable_immobilisations == Decimal("75.00")
    assert result.tva_nette == Decimal("225.00")


def test_regularisation_positive_augmente_le_net():
    result = calculer_position_tva_v2(
        tva_collectee=Decimal("300"),
        tva_recuperable_charges=Decimal("100"),
        tva_recuperable_immobilisations=Decimal("0"),
        regularisations=[Decimal("25")],
        **CONFIG,
    )
    assert result.regularisations == Decimal("25.00")
    assert result.tva_a_payer == Decimal("225.00")


def test_regularisation_negative_diminue_le_net():
    result = calculer_position_tva_v2(
        tva_collectee=Decimal("300"),
        tva_recuperable_charges=Decimal("100"),
        tva_recuperable_immobilisations=Decimal("0"),
        regularisations=[Decimal("-40")],
        **CONFIG,
    )
    assert result.regularisations == Decimal("-40.00")
    assert result.tva_a_payer == Decimal("160.00")


def test_periode_sans_donnees_reste_a_zero():
    result = calculer_position_tva_v2(
        tva_collectee=Decimal("0"),
        tva_recuperable_charges=Decimal("0"),
        tva_recuperable_immobilisations=Decimal("0"),
        **CONFIG,
    )
    assert result.tva_nette == Decimal("0.00")
    assert result.tva_a_payer == Decimal("0.00")
    assert result.credit_a_reporter == Decimal("0.00")
    assert result.a_verifier is False


def test_regle_fiscale_non_configuree_reste_a_verifier():
    result = calculer_position_tva_v2(
        tva_collectee=Decimal("100"),
        tva_recuperable_charges=Decimal("20"),
        tva_recuperable_immobilisations=Decimal("0"),
    )
    assert result.a_verifier is True
    assert any("Périodicité" in reason for reason in result.anomalies)
    assert any("prorata" in reason for reason in result.anomalies)
    assert any("retenue" in reason for reason in result.anomalies)


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self):
        self.usage = None
        self.added = []

    def execute(self, statement):
        return _ScalarResult(self.usage)

    def add(self, value):
        self.added.append(value)
        if isinstance(value, TvaCreditUtilisation):
            self.usage = value

    def flush(self):
        pass


def _period(cabinet_id, entreprise_id, source_id):
    return TvaPeriode(
        id=uuid.uuid4(),
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        annee=2026,
        mois=2,
        statut="provisoire",
        credit_anterieur=Decimal("150.00"),
        credit_source_periode_id=source_id,
        a_verifier=False,
    )


def test_credit_ne_peut_pas_etre_utilise_deux_fois():
    cabinet_id = uuid.uuid4()
    entreprise_id = uuid.uuid4()
    source_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db = _Db()

    first = _period(cabinet_id, entreprise_id, source_id)
    valider_periode_tva(
        db,
        periode=first,
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        user_id=user_id,
    )
    assert db.usage is not None
    assert db.usage.periode_destination_id == first.id

    second = _period(cabinet_id, entreprise_id, source_id)
    with pytest.raises(ValueError, match="déjà été utilisé"):
        valider_periode_tva(
            db,
            periode=second,
            cabinet_id=cabinet_id,
            entreprise_id=entreprise_id,
            user_id=user_id,
        )


def test_validation_periode_est_isolee_par_tenant():
    period = _period(uuid.uuid4(), uuid.uuid4(), None)
    with pytest.raises(ValueError, match="hors du cabinet"):
        valider_periode_tva(
            _Db(),
            periode=period,
            cabinet_id=uuid.uuid4(),
            entreprise_id=period.entreprise_id,
            user_id=uuid.uuid4(),
        )
