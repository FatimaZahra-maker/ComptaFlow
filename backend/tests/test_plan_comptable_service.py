from app.services.plan_comptable_service import (
    normaliser_famille_cgnc,
    normaliser_numero_compte,
    normaliser_texte,
    normaliser_tiers,
    valider_coherence_compte,
)


def test_normaliser_numero_compte():
    assert normaliser_numero_compte("4411 0300 0000") == "441103000000"


def test_normaliser_tiers_accents_et_espaces():
    assert normaliser_tiers("  Société   Éxemple  ") == "SOCIETE EXEMPLE"


def test_normaliser_nature():
    assert normaliser_texte("Matériel informatique") == "materiel_informatique"


def test_famille_coherente():
    numero, famille = valider_coherence_compte("613100000000", "6131")
    assert numero == "613100000000"
    assert famille == "6131"


def test_famille_incoherente_refusee():
    try:
        valider_coherence_compte("613100000000", "34552")
    except ValueError as exc:
        assert "n'appartient pas" in str(exc)
    else:
        raise AssertionError("Une famille incompatible doit être refusée")


def test_famille_normalisee():
    assert normaliser_famille_cgnc(" 34552 ") == "34552"


def test_usage_banque_est_autorise():
    from app.services.plan_comptable_service import _usage_propre
    assert _usage_propre("banque") == "banque"
