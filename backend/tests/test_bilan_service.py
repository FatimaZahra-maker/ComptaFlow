from dataclasses import dataclass
from decimal import Decimal
import uuid

from app.services.bilan_service import (
    RUBRIQUE_ACTIF_CIRCULANT,
    RUBRIQUE_ACTIF_IMMOBILISE,
    RUBRIQUE_AMORT_PROV_IMMOBILISATIONS,
    RUBRIQUE_FINANCEMENT_PERMANENT,
    RUBRIQUE_PASSIF_CIRCULANT,
    RUBRIQUE_PROV_ACTIF_CIRCULANT,
    RUBRIQUE_TRESORERIE_ACTIF,
    RUBRIQUE_TRESORERIE_PASSIF,
    calculer_bilan_depuis_lignes,
    determiner_rubrique_bilan,
)


@dataclass
class Ligne:
    compte: str
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")


def test_classification_bilan_principale():
    assert determiner_rubrique_bilan("233200000000") == (
        RUBRIQUE_ACTIF_IMMOBILISE, "actif", False
    )
    assert determiner_rubrique_bilan("283320000000") == (
        RUBRIQUE_AMORT_PROV_IMMOBILISATIONS, "actif", True
    )
    assert determiner_rubrique_bilan("342100000000") == (
        RUBRIQUE_ACTIF_CIRCULANT, "actif", False
    )
    assert determiner_rubrique_bilan("394200000000") == (
        RUBRIQUE_PROV_ACTIF_CIRCULANT, "actif", True
    )
    assert determiner_rubrique_bilan("514100000000") == (
        RUBRIQUE_TRESORERIE_ACTIF, "actif", False
    )
    assert determiner_rubrique_bilan("111100000000") == (
        RUBRIQUE_FINANCEMENT_PERMANENT, "passif", False
    )
    assert determiner_rubrique_bilan("441100000000") == (
        RUBRIQUE_PASSIF_CIRCULANT, "passif", False
    )
    assert determiner_rubrique_bilan("554100000000") == (
        RUBRIQUE_TRESORERIE_PASSIF, "passif", False
    )


def test_classes_6_et_7_ne_sont_pas_dupliquees_dans_le_bilan():
    assert determiner_rubrique_bilan("611100000000") == (None, None, False)
    assert determiner_rubrique_bilan("711100000000") == (None, None, False)


def test_amortissements_et_provisions_diminuent_l_actif():
    result = calculer_bilan_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            Ligne("233200000000", debit=Decimal("100000.00")),
            Ligne("283320000000", credit=Decimal("20000.00")),
            Ligne("342100000000", debit=Decimal("50000.00")),
            Ligne("394200000000", credit=Decimal("5000.00")),
        ],
    )
    assert result.actif_immobilise_brut == Decimal("100000.00")
    assert result.amortissements_provisions_immobilisations == Decimal("20000.00")
    assert result.actif_immobilise_net == Decimal("80000.00")
    assert result.actif_circulant_brut == Decimal("50000.00")
    assert result.provisions_actif_circulant == Decimal("5000.00")
    assert result.actif_circulant_net == Decimal("45000.00")


def test_resultat_cpc_est_integre_uniquement_s_il_ferme_l_ecart():
    result = calculer_bilan_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            Ligne("514100000000", debit=Decimal("15000.00")),
            Ligne("111100000000", credit=Decimal("10000.00")),
        ],
        resultat_net_cpc=Decimal("5000.00"),
    )
    assert result.ecart_avant_resultat_cpc == Decimal("5000.00")
    assert result.resultat_cpc_integre is True
    assert result.total_passif_technique == Decimal("15000.00")
    assert result.ecart_bilan == Decimal("0.00")
    assert result.equilibre is True


def test_resultat_cpc_n_est_pas_double_si_le_passif_est_deja_equilibre():
    result = calculer_bilan_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[
            Ligne("514100000000", debit=Decimal("15000.00")),
            Ligne("111100000000", credit=Decimal("15000.00")),
        ],
        resultat_net_cpc=Decimal("5000.00"),
    )
    assert result.resultat_cpc_integre is False
    assert result.total_passif_technique == Decimal("15000.00")
    assert result.equilibre is True


def test_compte_inconnu_ne_provoque_pas_un_classement_arbitraire():
    result = calculer_bilan_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[Ligne("521100000000", debit=Decimal("1000.00"))],
    )
    assert result.a_verifier is True
    assert any("521100000000" in reason for reason in result.raisons_verification)


def test_bilan_non_equilibre_est_signale():
    result = calculer_bilan_depuis_lignes(
        entreprise_id=uuid.uuid4(),
        annee=2026,
        lignes=[Ligne("342100000000", debit=Decimal("999.00"))],
    )
    assert result.equilibre is False
    assert result.ecart_bilan == Decimal("999.00")
    assert result.a_verifier is True
