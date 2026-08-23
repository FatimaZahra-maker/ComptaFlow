from app.services.accounting_rules_service import (
    FAMILLE_TVA_FACTUREE,
    FAMILLE_TVA_RECUPERABLE_CHARGES,
    FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS,
    compte_correspond_a_famille,
    normaliser_nature_comptable,
    normaliser_nature_vente,
    obtenir_famille_tva_achat,
    obtenir_famille_tva_vente,
    obtenir_regle_achat,
    obtenir_regle_vente,
)


def test_normalisation_et_regle_location():
    assert normaliser_nature_comptable("Location") == "location"

    regle = obtenir_regle_achat("location")

    assert regle is not None
    assert regle.famille_cgnc == "6131"
    assert regle.traitement == "charge"


def test_materiel_informatique_est_immobilisation_candidate():
    regle = obtenir_regle_achat("matériel informatique")

    assert regle is not None
    assert regle.famille_cgnc == "2355"
    assert regle.traitement == "immobilisation_candidate"


def test_nature_inconnue_ne_produit_pas_de_compte():
    assert normaliser_nature_comptable("achat bizarre inconnu") is None
    assert obtenir_regle_achat("achat bizarre inconnu") is None


def test_validation_famille_compte():
    assert compte_correspond_a_famille("613100000000", "6131")
    assert not compte_correspond_a_famille("612100000000", "6131")


def test_tva_charge_utilise_famille_charges():
    assert obtenir_famille_tva_achat("charge") == FAMILLE_TVA_RECUPERABLE_CHARGES


def test_tva_immobilisation_candidate_attend_confirmation():
    assert obtenir_famille_tva_achat("immobilisation_candidate") is None


def test_tva_immobilisation_confirmee_utilise_famille_immobilisations():
    assert (
        obtenir_famille_tva_achat(
            "immobilisation_candidate",
            "immobilisation",
        )
        == FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS
    )


def test_tva_candidate_confirmee_charge_utilise_famille_charges():
    assert (
        obtenir_famille_tva_achat(
            "immobilisation_candidate",
            "charge",
        )
        == FAMILLE_TVA_RECUPERABLE_CHARGES
    )


# ============================================================
# VENTES
# ============================================================


def test_vente_marchandises_utilise_7111():
    regle = obtenir_regle_vente("marchandises")
    assert regle is not None
    assert regle.famille_cgnc == "7111"


def test_vente_travaux_utilise_71241():
    assert normaliser_nature_vente("travaux sous-traitance") == "travaux"
    regle = obtenir_regle_vente("travaux")
    assert regle is not None
    assert regle.famille_cgnc == "71241"


def test_vente_etudes_utilise_71242():
    regle = obtenir_regle_vente("études")
    assert regle is not None
    assert regle.famille_cgnc == "71242"


def test_vente_prestations_utilise_71243():
    regle = obtenir_regle_vente("prestations service")
    assert regle is not None
    assert regle.famille_cgnc == "71243"


def test_vente_produits_finis_utilise_71211():
    regle = obtenir_regle_vente("produits finis")
    assert regle is not None
    assert regle.famille_cgnc == "71211"


def test_tva_vente_utilise_4455():
    assert obtenir_famille_tva_vente() == FAMILLE_TVA_FACTUREE
    assert FAMILLE_TVA_FACTUREE == "4455"


def test_nature_vente_inconnue_refusee():
    assert normaliser_nature_vente("revenu mystérieux") is None
    assert obtenir_regle_vente("revenu mystérieux") is None
