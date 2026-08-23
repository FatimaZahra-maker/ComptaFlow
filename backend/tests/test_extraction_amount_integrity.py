from app.services.extraction_mapping_service import construire_donnees_extraites
from app.services.groq_service import _valider_et_corriger_montants


def test_groq_ne_reconstruit_pas_une_tva_absente():
    resultat = _valider_et_corriger_montants(
        {
            "categorie_document": "facture",
            "montant_ht": 100.0,
            "montant_tva": None,
            "montant_ttc": 120.0,
            "taux_tva": 20.0,
        }
    )

    assert resultat["montant_ht"] == 100.0
    assert resultat["montant_tva"] is None
    assert resultat["montant_ttc"] == 120.0


def test_groq_signale_incoherence_sans_remplacer_tva_extraite():
    resultat = _valider_et_corriger_montants(
        {
            "categorie_document": "facture",
            "montant_ht": 100.0,
            "montant_tva": 18.0,
            "montant_ttc": 120.0,
            "taux_tva": 20.0,
        }
    )

    assert resultat["montant_tva"] == 18.0
    assert resultat["a_verifier"] is True


def test_mapping_ne_deduit_pas_ht_meme_pour_tva_zero():
    resultat = construire_donnees_extraites(
        {
            "categorie_document": "facture",
            "montant_ht": None,
            "montant_tva": 0,
            "montant_ttc": 250.0,
            "taux_tva": 0,
        }
    )

    assert resultat["montant_ht"] is None
    assert resultat["montant_tva"] == 0
    assert resultat["montant_ttc"] == 250.0
