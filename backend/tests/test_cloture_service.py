from datetime import date
from decimal import Decimal
import uuid

import pytest

from app.models.regularisation_cloture import RegularisationCloture
from app.models.ligne_comptable import LigneComptable
from app.services.cloture_service import (
    construire_lignes_equilibrees,
    verifier_comptes_dans_plan,
    verifier_configuration,
    verifier_report_source,
    verifier_scope,
)
from app.services.ligne_comptable_service import obtenir_balance, obtenir_grand_livre


def _item(kind="ajustement_manuel", **changes):
    values = dict(
        id=uuid.uuid4(), cabinet_id=uuid.uuid4(), entreprise_id=uuid.uuid4(),
        exercice=2026, date_ecriture=date(2026, 12, 31), type_regularisation=kind,
        libelle="Regularisation test", montant=Decimal("125.50"),
        compte_debit="619100", compte_credit="281100", donnees_calcul={},
        a_extourner=False, statut="brouillon", source="manuel",
    )
    values.update(changes)
    return RegularisationCloture(**values)


@pytest.mark.parametrize("kind", [
    "stock", "charge_constatee_avance", "produit_constate_avance",
    "charge_a_payer", "produit_a_recevoir", "ajustement_manuel",
])
def test_tous_les_types_generent_une_ecriture_equilibree(kind):
    lines = construire_lignes_equilibrees(_item(kind))
    assert sum(line["debit"] for line in lines) == Decimal("125.50")
    assert sum(line["credit"] for line in lines) == Decimal("125.50")
    assert all(line["est_validee"] for line in lines)


def test_provision_constitution_et_reprise_exigent_un_sens_explicite():
    for operation in ("constitution", "augmentation", "reprise"):
        item = _item("provision", donnees_calcul={"operation": operation})
        assert verifier_configuration(item).valide
        assert sum(x["debit"] for x in construire_lignes_equilibrees(item)) == sum(
            x["credit"] for x in construire_lignes_equilibrees(item)
        )
    assert not verifier_configuration(_item("provision")).valide


def test_amortissement_configuration_complete_utilise_la_dotation_explicite():
    item = _item("amortissement", donnees_calcul={
        "valeur_amortissable": "1000", "date_mise_service": "2025-01-01",
        "methode": "lineaire", "duree_mois": 60, "cumul_anterieur": "200",
        "dotation_exercice": "125.50",
    })
    assert verifier_configuration(item).valide
    assert construire_lignes_equilibrees(item)[0]["debit"] == Decimal("125.50")


def test_amortissement_configuration_incomplete_reste_a_verifier():
    result = verifier_configuration(_item("amortissement", donnees_calcul={"methode": "lineaire"}))
    assert not result.valide
    assert "incomplete" in result.anomalies[0]


def test_compte_absent_du_plan_refuse_la_generation_sure():
    item = _item()
    result = verifier_comptes_dans_plan(item, {"619100"})
    assert not result.valide
    assert "281100" in result.anomalies[0]


def test_comptes_identiques_refusent_une_fausse_ecriture():
    with pytest.raises(ValueError, match="distincts"):
        construire_lignes_equilibrees(_item(compte_credit="619100"))


def test_extourne_est_marquee_sans_generation_automatique():
    item = _item(a_extourner=True, date_extourne=date(2027, 1, 1))
    assert verifier_configuration(item).valide
    lines = construire_lignes_equilibrees(item)
    assert len(lines) == 2
    assert all(line["date_ecriture"] == date(2026, 12, 31) for line in lines)


def test_report_a_nouveau_ne_peut_pas_etre_duplique():
    report = _item("report_a_nouveau")
    source = _item(
        "resultat_cloture", cabinet_id=report.cabinet_id, entreprise_id=report.entreprise_id,
        exercice=2025, date_ecriture=date(2025, 12, 31), statut="comptabilisee",
    )
    report.report_source_id = source.id
    assert verifier_report_source(report, source, False).valide
    assert not verifier_report_source(report, source, True).valide


def test_isolation_multi_tenant_refuse_un_objet_hors_scope():
    item = _item()
    verifier_scope(item, item.cabinet_id, item.entreprise_id)
    with pytest.raises(ValueError, match="hors du cabinet"):
        verifier_scope(item, uuid.uuid4(), item.entreprise_id)


def test_lignes_cloture_sont_visibles_aux_lectures_grand_livre_balance():
    item = _item()
    lines = [LigneComptable(
        id=uuid.uuid4(), cabinet_id=item.cabinet_id, entreprise_id=item.entreprise_id,
        regularisation_cloture_id=item.id, ecriture_id=None, mouvement_bancaire_id=None, **values,
    ) for values in construire_lignes_equilibrees(item)]

    class Result:
        def __init__(self, values): self.values = values
        def scalars(self): return self
        def all(self): return self.values

    class Db:
        def __init__(self): self.calls = 0
        def execute(self, statement):
            self.calls += 1
            return Result([] if self.calls == 1 else lines)

    grand_livre = obtenir_grand_livre(
        Db(), cabinet_id=item.cabinet_id, entreprise_id=item.entreprise_id
    )
    balance = obtenir_balance(
        Db(), cabinet_id=item.cabinet_id, entreprise_id=item.entreprise_id
    )
    assert grand_livre["nombre_lignes"] == 2
    assert balance["total_debit"] == balance["total_credit"] == Decimal("125.50")
    assert grand_livre["comptes"][0]["lignes"][0]["regularisation_cloture_id"] == item.id
