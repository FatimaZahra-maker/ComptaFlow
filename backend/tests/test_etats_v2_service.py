from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from app.services.bilan_service import calculer_bilan_v2_depuis_lignes
from app.services.cpc_service import calculer_cpc_v2_depuis_lignes


CABINET = uuid.uuid4()
ENTREPRISE = uuid.uuid4()


def ligne(compte, debit="0", credit="0", *, annee=2026, cabinet=CABINET, entreprise=ENTREPRISE, source=None, cloture=None):
    values = dict(
        compte=compte,
        debit=debit,
        credit=credit,
        date_ecriture=date(annee, 12, 31),
        cabinet_id=cabinet,
        entreprise_id=entreprise,
    )
    if source is not None or cloture is not None:
        values.update(
            ecriture_id=source,
            mouvement_bancaire_id=None,
            regularisation_cloture_id=cloture,
        )
    return SimpleNamespace(**values)


def cpc(lines, previous=()):
    return calculer_cpc_v2_depuis_lignes(
        cabinet_id=CABINET,
        entreprise_id=ENTREPRISE,
        exercice=2026,
        lignes_n=lines,
        lignes_n_1=previous,
    )


def bilan(lines, resultat="0", comptes_resultat=None):
    return calculer_bilan_v2_depuis_lignes(
        cabinet_id=CABINET,
        entreprise_id=ENTREPRISE,
        exercice=2026,
        lignes=lines,
        resultat_net_cpc=resultat,
        comptes_resultat_configures=comptes_resultat or set(),
    )


def valeur(result, code):
    return next(item for item in result.rubriques + result.resultats if item.code == code)


def test_cpc_v2_exploitation_financier_non_courant_impot_et_resultat_net():
    result = cpc([
        ligne("711100", credit="1000"), ligne("611100", debit="400"),
        ligne("731100", credit="80"), ligne("631100", debit="30"),
        ligne("751100", credit="40"), ligne("651100", debit="10"),
        ligne("670100", debit="100"),
    ])
    assert valeur(result, "resultat_exploitation").montant_n == Decimal("600.00")
    assert valeur(result, "resultat_financier").montant_n == Decimal("50.00")
    assert valeur(result, "resultat_non_courant").montant_n == Decimal("30.00")
    assert valeur(result, "impots_sur_resultats").montant_n == Decimal("100.00")
    assert valeur(result, "resultat_net").montant_n == Decimal("580.00")


def test_cpc_v2_comptes_classes_6_et_7_inconnus_restent_visibles():
    result = cpc([ligne("691100", debit="25"), ligne("791100", credit="35")])
    assert result.statut == "a_verifier"
    assert {item.compte for item in result.comptes_non_classes} == {"691100", "791100"}
    assert sum((item.debit + item.credit for item in result.comptes_non_classes), Decimal("0")) == Decimal("60.00")


def test_cpc_v2_compare_n_et_n_1_sans_fabriquer_la_variation():
    result = cpc(
        [ligne("711100", credit="2450")],
        [ligne("711100", credit="2100", annee=2025)],
    )
    row = valeur(result, "produits_exploitation")
    assert row.montant_n_1 == Decimal("2100.00")
    assert row.variation_mad == Decimal("350.00")
    assert row.variation_pct == Decimal("16.67")


def test_cpc_v2_absence_n_1_reste_explicitement_absente():
    result = cpc([ligne("711100", credit="100")])
    row = valeur(result, "produits_exploitation")
    assert result.donnees_n_1_disponibles is False
    assert row.montant_n_1 is None and row.variation_mad is None and row.variation_pct is None


def test_cpc_v2_detecte_exercice_montant_et_source_desequilibree():
    source = uuid.uuid4()
    result = cpc([
        ligne("611100", debit="100", source=source),
        ligne("441100", credit="90", source=source),
        ligne("711100", credit="invalide"),
        ligne("711100", credit="10", annee=2024),
    ])
    assert any("non equilibrees" in anomaly for anomaly in result.anomalies)
    assert any("non exploitable" in anomaly for anomaly in result.anomalies)
    assert any("exercice incoherent" in anomaly for anomaly in result.anomalies)


def test_bilan_v2_toutes_les_grandes_rubriques_et_equilibre():
    result = bilan([
        ligne("233200", debit="100"), ligne("342100", debit="80"), ligne("514100", debit="20"),
        ligne("111100", credit="90"), ligne("441100", credit="70"), ligne("554100", credit="40"),
    ])
    assert result.bilan_equilibre is True
    assert result.total_actif == result.total_passif == Decimal("200.00")
    values = {item.code: item.montant for item in result.actif + result.passif}
    assert values["actif_immobilise_brut"] == Decimal("100.00")
    assert values["actif_circulant_brut"] == Decimal("80.00")
    assert values["tresorerie_actif"] == Decimal("20.00")
    assert values["financement_permanent"] == Decimal("90.00")
    assert values["passif_circulant"] == Decimal("70.00")
    assert values["tresorerie_passif"] == Decimal("40.00")


def test_bilan_v2_desequilibre_ne_cree_aucune_correction():
    result = bilan([ligne("342100", debit="99")])
    assert result.bilan_equilibre is False
    assert result.ecart == Decimal("99.00")
    assert any("Bilan non equilibre" in anomaly for anomaly in result.anomalies)


def test_amortissement_et_provision_de_cloture_alimentent_cpc_et_bilan():
    closure = uuid.uuid4()
    provision = uuid.uuid4()
    lines = [
        ligne("233200", debit="100"), ligne("111100", credit="100"),
        ligne("619100", debit="20", cloture=closure), ligne("283200", credit="20", cloture=closure),
        ligne("619200", debit="5", cloture=provision), ligne("392000", credit="5", cloture=provision),
    ]
    cpc_result = cpc(lines)
    bilan_result = bilan(lines, resultat="-25")
    assert valeur(cpc_result, "charges_exploitation").montant_n == Decimal("25.00")
    assert bilan_result.actif[1].montant == Decimal("-20.00")
    assert next(item for item in bilan_result.actif if item.code == "provisions_actif_circulant").montant == Decimal("-5.00")
    assert bilan_result.bilan_equilibre is True


@pytest.mark.parametrize(("type_cloture", "compte_debit", "compte_credit", "resultat_attendu"), [
    ("stock", "311100", "611100", "100.00"),
    ("charge_constatee_avance", "349100", "611100", "100.00"),
    ("produit_constate_avance", "711100", "449100", "-100.00"),
    ("charge_a_payer", "611100", "441700", "-100.00"),
    ("produit_a_recevoir", "342700", "711100", "100.00"),
    ("ajustement_manuel", "342800", "711100", "100.00"),
])
def test_autres_regularisations_de_cloture_passent_par_les_lignes_normales(
    type_cloture, compte_debit, compte_credit, resultat_attendu,
):
    closure = uuid.uuid4()
    lines = [
        ligne(compte_debit, debit="100", cloture=closure),
        ligne(compte_credit, credit="100", cloture=closure),
    ]
    cpc_result = cpc(lines)
    bilan_result = bilan(lines, resultat=resultat_attendu)
    assert valeur(cpc_result, "resultat_net").montant_n == Decimal(resultat_attendu)
    assert any(item.regularisation_cloture_id == closure for item in lines)
    assert bilan_result.controle_grand_livre_balance.coherent is True


def test_resultat_cpc_non_comptabilise_est_presente_separement():
    result = bilan([
        ligne("514100", debit="150"), ligne("111100", credit="100"), ligne("711100", credit="50"),
    ], resultat="50")
    assert result.resultat_deja_comptabilise is False
    assert result.resultat_non_affecte == Decimal("50.00")
    assert result.total_passif == Decimal("150.00")
    assert result.bilan_equilibre is True
    assert result.statut == "a_verifier"


def test_resultat_deja_comptabilise_n_est_jamais_ajoute_deux_fois():
    result = bilan([
        ligne("514100", debit="150"), ligne("111100", credit="100"),
        ligne("711100", credit="50"), ligne("711100", debit="50"),
        ligne("119900", credit="50"),
    ], resultat="50", comptes_resultat={"119900"})
    assert result.resultat_deja_comptabilise is True
    assert result.resultat_non_affecte == Decimal("0.00")
    assert result.total_passif == Decimal("150.00")
    assert result.controle_resultat.coherent is True


def test_resultat_cpc_incoherent_avec_compte_resultat_est_signale():
    result = bilan([
        ligne("514100", debit="140"), ligne("111100", credit="100"), ligne("119900", credit="40"),
    ], resultat="50", comptes_resultat={"119900"})
    assert result.controle_resultat.coherent is False
    assert any("Resultat CPC incoherent" in anomaly for anomaly in result.anomalies)


def test_compte_bilan_non_classe_et_sens_inattendu_sont_visibles():
    result = bilan([ligne("521100", debit="30"), ligne("233200", credit="10")])
    assert {item.compte for item in result.comptes_non_classes} == {"521100"}
    assert any("sens inattendu" in anomaly for anomaly in result.anomalies)


def test_coherence_grand_livre_balance_est_exposee():
    result = bilan([ligne("514100", debit="100"), ligne("111100", credit="100")])
    control = result.controle_grand_livre_balance
    assert control.coherent is True
    assert control.total_debit_grand_livre == control.total_debit_balance == Decimal("100.00")
    assert control.total_credit_grand_livre == control.total_credit_balance == Decimal("100.00")


def test_isolation_entreprise_id_exclut_la_ligne_etrangere():
    result = cpc([
        ligne("711100", credit="100"),
        ligne("711100", credit="999", entreprise=uuid.uuid4()),
    ])
    assert valeur(result, "produits_exploitation").montant_n == Decimal("100.00")
    assert any("hors cabinet ou entreprise" in anomaly for anomaly in result.anomalies)


def test_isolation_cabinet_id_exclut_la_ligne_etrangere():
    result = bilan([
        ligne("514100", debit="100"), ligne("111100", credit="100"),
        ligne("514100", debit="999", cabinet=uuid.uuid4()),
    ])
    assert result.total_actif == Decimal("100.00")
    assert any("hors cabinet ou entreprise" in anomaly for anomaly in result.anomalies)


def test_exercice_vide_produit_des_etats_a_zero_sans_donnee_fictive():
    cpc_result = cpc([])
    bilan_result = bilan([])
    assert valeur(cpc_result, "resultat_net").montant_n == Decimal("0.00")
    assert cpc_result.comptes == [] and cpc_result.statut == "ok"
    assert bilan_result.total_actif == bilan_result.total_passif == Decimal("0.00")
    assert bilan_result.bilan_equilibre is True and bilan_result.statut == "ok"


def test_ligne_sans_compte_est_signalee_et_jamais_classee():
    result = cpc([ligne("", debit="10")])
    assert result.comptes == []
    assert result.statut == "a_verifier"
    assert any("aucun numero de compte" in anomaly for anomaly in result.anomalies)
