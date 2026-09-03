from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
import uuid

from app.services.precloture_service import (
    AnomalieControle,
    PreClotureSnapshot,
    calculer_precloture_snapshot,
    calculer_score,
    determiner_statut,
)


YEAR = 2026


def ns(**values):
    defaults = {"id": uuid.uuid4()}
    defaults.update(values)
    return SimpleNamespace(**defaults)


def snapshot(**values):
    data = {
        "cabinet_id": uuid.uuid4(),
        "entreprise_id": uuid.uuid4(),
        "exercice": YEAR,
    }
    data.update(values)
    return PreClotureSnapshot(**data)


def scoped(snap, **values):
    return ns(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, **values)


def line(snap, *, account="6131", debit="100", credit="0", source=None, validated=True, year=YEAR):
    source = source or ns(id=uuid.uuid4())
    return scoped(
        snap,
        date_ecriture=date(year, 6, 1), compte=account,
        debit=Decimal(debit), credit=Decimal(credit), est_validee=validated,
        ecriture_id=source.id, mouvement_bancaire_id=None,
        regularisation_cloture_id=None,
    )


def entry(snap, **values):
    base = dict(
        document_id=uuid.uuid4(), date_piece=date(YEAR, 6, 1),
        type_ecriture="achat", statut_validation="valide",
        compte_ht="6131", compte_tiers="4411", compte_tva=None,
        montant_tva=Decimal("0"), montant_ttc=Decimal("100"),
        devise_originale="MAD", doublon_potentiel_id=None,
    )
    base.update(values)
    return scoped(snap, **base)


def anomaly(level):
    return AnomalieControle(
        code=f"code_{level}", module="documents", niveau=level,
        titre="Test", description="Test", entreprise_id=uuid.uuid4(),
        exercice=YEAR, objet_type="test",
    )


def codes(result):
    return {item.code for item in result.anomalies}


def test_score_100_et_statut_pret_sans_anomalie():
    result = calculer_precloture_snapshot(snapshot())
    assert result.score == 100
    assert result.statut == "pret"
    assert result.anomalies == []


def test_score_pondere_est_deterministe_et_borne():
    items = [anomaly("bloquant"), anomaly("important"), anomaly("avertissement"), anomaly("information")]
    assert calculer_score(items) == 60
    assert calculer_score([anomaly("bloquant") for _ in range(5)]) == 0


def test_statut_global_respecte_les_niveaux_contractuels():
    assert determiner_statut([anomaly("bloquant")]) == "bloque"
    assert determiner_statut([anomaly("important")]) == "a_verifier"
    assert determiner_statut([anomaly("avertissement")]) == "pret"
    assert calculer_score([anomaly("avertissement")]) == 96


def test_document_a_verifier_est_signale():
    snap = snapshot()
    doc = scoped(snap, annee=YEAR, statut="traite", categorie="autre", donnees_extraites={"a_verifier": True})
    assert "document_a_verifier" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, documents=[doc])))


def test_document_erreur_et_traitement_incomplet_sont_distincts():
    snap = snapshot()
    documents = [
        scoped(snap, annee=YEAR, statut="erreur", categorie="autre", donnees_extraites={}),
        scoped(snap, annee=YEAR, statut="en_attente", categorie="autre", donnees_extraites={}),
    ]
    found = codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, documents=documents)))
    assert {"document_erreur", "document_traitement_incomplet"} <= found


def test_document_facture_sans_ecriture_est_signale():
    snap = snapshot()
    doc = scoped(snap, annee=YEAR, statut="traite", categorie="achats", donnees_extraites={"numero_piece": "F1", "date_piece": "2026-01-02", "montant_ttc": "100"})
    assert "document_ecriture_absente" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, documents=[doc])))


def test_ecriture_validee_desequilibree_est_bloquante():
    snap = snapshot()
    item = entry(snap)
    lines = [line(snap, source=item), line(snap, account="4411", debit="0", credit="80", source=item)]
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item], lignes=lines))
    assert "ecriture_desequilibree" in codes(result)
    assert result.statut == "bloque"


def test_ecriture_sans_compte_exact_est_bloquante():
    snap = snapshot()
    item = entry(snap, compte_ht=None, compte_tiers=None)
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item]))
    assert {"compte_ht_manquant", "compte_tiers_manquant"} <= codes(result)


def test_mouvement_bancaire_non_rapproche_est_signale():
    snap = snapshot()
    movement = scoped(snap, date_operation=date(YEAR, 2, 1), statut_rapprochement="non_rapproche", compte_bancaire_entreprise_id=uuid.uuid4(), compte_banque="5141", nature_operation="reglement_facture", devise_originale="MAD")
    assert "mouvement_non_rapproche" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, mouvements=[movement])))


def test_rapprochement_ambigu_est_signale():
    snap = snapshot()
    movement = scoped(snap, date_operation=date(YEAR, 2, 1), statut_rapprochement="ambigu", compte_bancaire_entreprise_id=uuid.uuid4(), compte_banque="5141", nature_operation="reglement_facture", devise_originale="MAD")
    assert "rapprochement_ambigu" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, mouvements=[movement])))


def test_facture_partiellement_reglee_reste_visible():
    snap = snapshot()
    item = entry(snap)
    movement = scoped(snap, date_operation=date(YEAR, 7, 1), statut_rapprochement="confirme", compte_bancaire_entreprise_id=uuid.uuid4(), compte_banque="5141", nature_operation="reglement_facture", devise_originale="MAD", montant=Decimal("40"))
    allocation = scoped(snap, mouvement_bancaire_id=movement.id, ecriture_id=item.id, statut="confirme", montant_affecte=Decimal("40"), montant_reglement_mad=None, valeur_comptable_mad=None, nature_ecart_change=None, statut_ecart_change="non_requis")
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item], mouvements=[movement], allocations=[allocation]))
    assert "facture_partiellement_reglee" in codes(result)


def test_devise_sans_cours_ni_valeur_mad_est_signalee():
    snap = snapshot()
    item = entry(snap, devise_originale="EUR", montant_ttc_devise=Decimal("100"), montant_ttc_mad=None, taux_change_initial=None, source_cours_initial=None)
    found = codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item])))
    assert {"montant_mad_manquant", "cours_change_manquant"} <= found


def test_ecart_change_non_resolu_est_signale():
    snap = snapshot()
    allocation = scoped(snap, nature_ecart_change="a_verifier", statut_ecart_change="a_verifier", raison_ecart_change="cours absent")
    assert "ecart_change_a_verifier" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, allocations=[allocation])))


def test_compte_gain_change_absent_du_plan_est_bloquant():
    snap = snapshot()
    allocation = scoped(snap, nature_ecart_change="gain", statut_ecart_change="calcule", compte_ecart_change=None)
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, allocations=[allocation]))
    assert {"compte_gain_change_manquant", "plan_gain_change_manquant"} <= codes(result)


def test_periode_tva_a_verifier_est_signalee():
    snap = snapshot()
    period = scoped(snap, annee=YEAR, mois=3, statut="provisoire", a_verifier=True)
    assert "periode_tva_non_validable" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, tva_periodes=[period])))


def test_double_utilisation_credit_tva_est_bloquante():
    snap = snapshot()
    source = uuid.uuid4()
    credits = [scoped(snap, periode_source_id=source, periode_destination_id=uuid.uuid4()), scoped(snap, periode_source_id=source, periode_destination_id=uuid.uuid4())]
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, tva_credits=credits))
    assert "credit_tva_double_utilisation" in codes(result)
    assert result.statut == "bloque"


def test_regularisation_cloture_validee_non_comptabilisee_est_signalee():
    snap = snapshot()
    closure = scoped(snap, exercice=YEAR, statut="validee", compte_debit="6131", compte_credit="4411", report_source_id=None, a_extourner=False)
    assert "cloture_non_comptabilisee" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, clotures=[closure])))


def test_regularisation_comptabilisee_sans_lignes_est_bloquante():
    snap = snapshot()
    closure = scoped(snap, exercice=YEAR, statut="comptabilisee", compte_debit="6131", compte_credit="4411", report_source_id=None, a_extourner=False, type_regularisation="charge_a_payer")
    assert "cloture_sans_lignes" in codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, clotures=[closure])))


def test_grand_livre_balance_detecte_source_desequilibree():
    snap = snapshot()
    item = entry(snap)
    lines = [line(snap, source=item)]
    found = codes(calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item], lignes=lines)))
    assert "grand_livre_balance_anomalie" in found


def test_cpc_compte_classe_6_non_classe_est_visible():
    snap = snapshot()
    item = entry(snap)
    lines = [line(snap, account="6999", source=item), line(snap, account="4411", debit="0", credit="100", source=item)]
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item], lignes=lines))
    assert "cpc_compte_non_classe" in codes(result)


def test_bilan_desequilibre_est_bloquant_sans_correction():
    snap = snapshot()
    item = entry(snap)
    lines = [line(snap, account="2111", debit="100", source=item), line(snap, account="4411", debit="0", credit="80", source=item)]
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item], lignes=lines))
    assert "bilan_desequilibre" in codes(result)
    assert result.statut == "bloque"


def test_resultat_cpc_bilan_incoherent_est_signale():
    snap = snapshot()
    item = entry(snap)
    plan = [scoped(snap, numero_compte="1199", libelle="Resultat", nature_comptable="resultat_exercice", is_active=True)]
    lines = [line(snap, account="7111", debit="0", credit="100", source=item), line(snap, account="1199", debit="100", credit="0", source=item)]
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, ecritures=[item], lignes=lines, comptes_plan=plan))
    assert "resultat_cpc_bilan_incoherent" in codes(result)


def test_anomalies_sont_triees_par_priorite():
    snap = snapshot()
    movement = scoped(snap, date_operation=date(YEAR, 2, 1), statut_rapprochement="non_rapproche", compte_bancaire_entreprise_id=None, compte_banque=None, nature_operation="reglement_facture", devise_originale="MAD")
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, mouvements=[movement]))
    levels = [item.niveau for item in result.anomalies]
    assert levels == sorted(levels, key={"bloquant": 0, "important": 1, "avertissement": 2, "information": 3}.get)


def test_isolation_entreprise_ignore_les_objets_etrangers():
    snap = snapshot()
    foreign = ns(cabinet_id=snap.cabinet_id, entreprise_id=uuid.uuid4(), date_operation=date(YEAR, 1, 1), statut_rapprochement="non_rapproche", compte_bancaire_entreprise_id=None, compte_banque=None, nature_operation="autre", devise_originale="MAD")
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, mouvements=[foreign]))
    assert result.anomalies == []


def test_isolation_cabinet_ignore_les_objets_etrangers():
    snap = snapshot()
    foreign = ns(cabinet_id=uuid.uuid4(), entreprise_id=snap.entreprise_id, date_operation=date(YEAR, 1, 1), statut_rapprochement="non_rapproche", compte_bancaire_entreprise_id=None, compte_banque=None, nature_operation="autre", devise_originale="MAD")
    result = calculer_precloture_snapshot(snapshot(cabinet_id=snap.cabinet_id, entreprise_id=snap.entreprise_id, mouvements=[foreign]))
    assert result.anomalies == []


def test_resume_couvre_tous_les_modules_meme_exercice_vide():
    result = calculer_precloture_snapshot(snapshot())
    assert set(result.resume) == {"documents", "ecritures", "banque", "devises", "tva", "cloture", "grand_livre_balance", "cpc", "bilan"}
    assert all(item.statut == "ok" for item in result.resume.values())


def test_document_attendu_non_recu_apres_echeance_est_en_retard():
    snap = snapshot()
    expected = scoped(
        snap,
        type_document="achats",
        periode_debut=date(YEAR, 1, 1),
        periode_fin=date(YEAR, 12, 31),
        date_limite_reception=date.today().replace(year=YEAR) - timedelta(days=1),
        nombre_attendu=1,
        complete_manuellement=False,
    )
    result = calculer_precloture_snapshot(snapshot(
        cabinet_id=snap.cabinet_id,
        entreprise_id=snap.entreprise_id,
        documents_attendus=[expected],
    ))
    assert "documents_attendus_en_retard" in codes(result)


def test_pre_ecriture_prete_non_saisie_apres_echeance_topaze_est_en_retard():
    snap = snapshot()
    item = entry(
        snap,
        statut_validation="prete_topaze",
        topaze_entered_at=None,
    )
    work_period = scoped(
        snap,
        periode_debut=date(YEAR, 1, 1),
        periode_fin=date(YEAR, 12, 31),
        date_limite_saisie_topaze=date.today().replace(year=YEAR) - timedelta(days=1),
    )
    result = calculer_precloture_snapshot(snapshot(
        cabinet_id=snap.cabinet_id,
        entreprise_id=snap.entreprise_id,
        ecritures=[item],
        periodes_travail=[work_period],
    ))
    assert "saisie_topaze_en_retard" in codes(result)


def test_declaration_tva_non_declaree_apres_echeance_est_en_retard():
    snap = snapshot()
    period = scoped(
        snap,
        annee=YEAR,
        mois=6,
        statut="provisoire",
        a_verifier=False,
        statut_declaration="prete_a_declarer",
        date_limite_declaration=date.today().replace(year=YEAR) - timedelta(days=1),
        tva_a_payer=Decimal("120.00"),
    )
    result = calculer_precloture_snapshot(snapshot(
        cabinet_id=snap.cabinet_id,
        entreprise_id=snap.entreprise_id,
        tva_periodes=[period],
    ))
    assert "declaration_tva_en_retard" in codes(result)
