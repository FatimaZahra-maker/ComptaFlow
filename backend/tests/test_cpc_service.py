from types import SimpleNamespace
import uuid

from app.services.cpc_service import (
    RUBRIQUE_CHARGES_EXPLOITATION,
    RUBRIQUE_CHARGES_FINANCIERES,
    RUBRIQUE_CHARGES_NON_COURANTES,
    RUBRIQUE_IMPOTS_RESULTATS,
    RUBRIQUE_PRODUITS_EXPLOITATION,
    RUBRIQUE_PRODUITS_FINANCIERS,
    RUBRIQUE_PRODUITS_NON_COURANTS,
    calculer_cpc_depuis_lignes,
    determiner_rubrique_cpc,
)


def line(compte, debit=0, credit=0):
    return SimpleNamespace(compte=compte, debit=debit, credit=credit)


def test_prefixes_cgnc_cpc():
    assert determiner_rubrique_cpc("611100000000") == RUBRIQUE_CHARGES_EXPLOITATION
    assert determiner_rubrique_cpc("631100000000") == RUBRIQUE_CHARGES_FINANCIERES
    assert determiner_rubrique_cpc("651100000000") == RUBRIQUE_CHARGES_NON_COURANTES
    assert determiner_rubrique_cpc("670100000000") == RUBRIQUE_IMPOTS_RESULTATS
    assert determiner_rubrique_cpc("711100000000") == RUBRIQUE_PRODUITS_EXPLOITATION
    assert determiner_rubrique_cpc("731100000000") == RUBRIQUE_PRODUITS_FINANCIERS
    assert determiner_rubrique_cpc("751100000000") == RUBRIQUE_PRODUITS_NON_COURANTS


def test_resultat_exploitation():
    result = calculer_cpc_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            line("711100000000", credit="10000"),
            line("613100000000", debit="6500"),
        ],
    )
    assert str(result.produits_exploitation) == "10000.00"
    assert str(result.charges_exploitation) == "6500.00"
    assert str(result.resultat_exploitation) == "3500.00"


def test_resultat_financier_et_courant():
    result = calculer_cpc_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            line("711100000000", credit="10000"),
            line("611100000000", debit="6000"),
            line("731100000000", credit="500"),
            line("631100000000", debit="200"),
        ],
    )
    assert str(result.resultat_exploitation) == "4000.00"
    assert str(result.resultat_financier) == "300.00"
    assert str(result.resultat_courant) == "4300.00"


def test_resultat_non_courant():
    result = calculer_cpc_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            line("751100000000", credit="900"),
            line("651100000000", debit="250"),
        ],
    )
    assert str(result.resultat_non_courant) == "650.00"


def test_resultat_net_apres_impot():
    result = calculer_cpc_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            line("711100000000", credit="10000"),
            line("611100000000", debit="6000"),
            line("670100000000", debit="1000"),
        ],
    )
    assert str(result.resultat_avant_impots) == "4000.00"
    assert str(result.impots_sur_resultats) == "1000.00"
    assert str(result.resultat_net) == "3000.00"


def test_contrepassation_est_pris_en_compte():
    result = calculer_cpc_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            line("711100000000", credit="1000"),
            line("711100000000", debit="100"),
            line("611100000000", debit="500"),
            line("611100000000", credit="50"),
        ],
    )
    assert str(result.produits_exploitation) == "900.00"
    assert str(result.charges_exploitation) == "450.00"
    assert str(result.resultat_exploitation) == "450.00"


def test_compte_classe_6_inconnu_est_signale_sans_etre_classe():
    result = calculer_cpc_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[line("691100000000", debit="300")],
    )
    assert result.a_verifier is True
    assert str(result.resultat_net) == "0.00"
    assert result.comptes[0].rubrique == "non_classee"


def test_classes_hors_cpc_sont_ignorees():
    result = calculer_cpc_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            line("342100000000", debit="1200"),
            line("514100000000", credit="1200"),
        ],
    )
    assert result.nombre_comptes == 0
    assert result.a_verifier is False
    assert str(result.resultat_net) == "0.00"
