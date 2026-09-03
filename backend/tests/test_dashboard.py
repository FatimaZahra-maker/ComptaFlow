from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from app.api import dashboard as dashboard_api
from app.models.enums import StatutValidationEnum


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


def test_compteurs_dashboard_incluent_tout_le_workflow_precomptable():
    rows = [
        (StatutValidationEnum.CALCUL_EN_COURS, 1),
        (StatutValidationEnum.BROUILLON, 2),
        (StatutValidationEnum.A_VERIFIER, 3),
        (StatutValidationEnum.PRETE_TOPAZE, 4),
        (StatutValidationEnum.SAISIE_TOPAZE, 5),
        (StatutValidationEnum.VALIDE, 6),
        (StatutValidationEnum.REJETE, 7),
    ]

    class FakeDb:
        def execute(self, _query):
            return _RowsResult(rows)

    counters = dashboard_api._count_entries(FakeDb(), "cabinet", None)

    assert counters.model_dump() == {
        "calcul_en_cours": 1,
        "brouillon": 2,
        "a_verifier": 3,
        "prete_topaze": 4,
        "saisie_topaze": 5,
        "valide": 6,
        "rejete": 7,
    }


def test_tva_dashboard_utilise_les_statuts_comptablement_exploitables():
    class FakeDb:
        def __init__(self):
            self.queries = []
            self.values = iter((Decimal("120.00"), Decimal("45.00")))

        def execute(self, query):
            self.queries.append(query)
            return _ScalarResult(next(self.values))

    db = FakeDb()
    collected, deductible, net = dashboard_api._calculate_tax(db, "cabinet", None)

    assert (collected, deductible, net) == (
        Decimal("120.00"),
        Decimal("45.00"),
        Decimal("75.00"),
    )
    for query in db.queries:
        params = query.compile().params
        accepted = next(
            value for value in params.values() if isinstance(value, list)
        )
        assert accepted == [
            StatutValidationEnum.PRETE_TOPAZE,
            StatutValidationEnum.SAISIE_TOPAZE,
            StatutValidationEnum.VALIDE,
        ]


def test_dashboard_refuse_entreprise_hors_cabinet():
    class Result:
        def scalar_one_or_none(self):
            return None

    class FakeDb:
        def execute(self, _query):
            return Result()

    with pytest.raises(HTTPException) as error:
        dashboard_api.get_dashboard(
            period=None,
            entreprise_id=uuid.uuid4(),
            db=FakeDb(),
            current_user=SimpleNamespace(cabinet_id=uuid.uuid4()),
        )

    assert error.value.status_code == 404
