from datetime import date
from decimal import Decimal
import uuid

from app.models.ecriture import EcritureComptable
from app.models.enums import (
    StatutValidationEnum,
    TypeEcritureEnum,
    TypeMouvementBancaireEnum,
)
from app.models.mouvement_bancaire import MouvementBancaire
from app.services.ligne_comptable_service import (
    construire_lignes_banque,
    construire_lignes_facture,
)


def _entry(kind: TypeEcritureEnum) -> EcritureComptable:
    entry = EcritureComptable(
        cabinet_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        entreprise_id=uuid.uuid4(),
        type_ecriture=kind,
        montant_ht=Decimal("1000.00"),
        montant_tva=Decimal("200.00"),
        montant_ttc=Decimal("1200.00"),
        date_piece=date(2026, 5, 21),
        numero_piece="FAC-001",
        tiers="TIERS TEST",
        statut_validation=StatutValidationEnum.VALIDE,
    )
    entry.compte_tiers = "441100000000" if kind == TypeEcritureEnum.ACHAT else "342100000000"
    entry.compte_ht = "612100000000" if kind == TypeEcritureEnum.ACHAT else "712430000000"
    entry.compte_tva = "345520000000" if kind == TypeEcritureEnum.ACHAT else "445500000000"
    entry.libelle = "TIERS TEST FAC-001"
    return entry


def test_achat_genere_debit_ht_tva_credit_fournisseur():
    result = construire_lignes_facture(_entry(TypeEcritureEnum.ACHAT))
    assert result.complet is True
    assert len(result.lignes) == 3
    assert sum(x["debit"] for x in result.lignes) == Decimal("1200.00")
    assert sum(x["credit"] for x in result.lignes) == Decimal("1200.00")
    assert result.lignes[-1]["compte"] == "441100000000"
    assert result.lignes[-1]["credit"] == Decimal("1200.00")


def test_vente_genere_debit_client_credit_produit_tva():
    result = construire_lignes_facture(_entry(TypeEcritureEnum.VENTE))
    assert result.complet is True
    assert len(result.lignes) == 3
    assert result.lignes[0]["compte"] == "342100000000"
    assert result.lignes[0]["debit"] == Decimal("1200.00")
    assert sum(x["debit"] for x in result.lignes) == sum(x["credit"] for x in result.lignes)


def test_tva_positive_sans_compte_tva_refuse_generation():
    entry = _entry(TypeEcritureEnum.ACHAT)
    entry.compte_tva = None
    result = construire_lignes_facture(entry)
    assert result.complet is False
    assert any("Compte TVA absent" in reason for reason in result.raisons)


def test_montants_non_equilibres_refusent_generation():
    entry = _entry(TypeEcritureEnum.VENTE)
    entry.montant_ttc = Decimal("1200.10")
    result = construire_lignes_facture(entry)
    assert result.complet is False
    assert any("ne s'équilibrent pas" in reason for reason in result.raisons)


def test_debit_bancaire_regle_fournisseur_et_credite_banque():
    entry = _entry(TypeEcritureEnum.ACHAT)
    movement = MouvementBancaire(
        cabinet_id=entry.cabinet_id,
        document_id=uuid.uuid4(),
        entreprise_id=entry.entreprise_id,
        date_operation=date(2026, 5, 22),
        libelle="VIR FOURNISSEUR",
        reference="VIR-1",
        type_mouvement=TypeMouvementBancaireEnum.DEBIT,
        montant=Decimal("1200.00"),
        statut_rapprochement="confirme",
        compte_banque="514100000000",
    )
    result = construire_lignes_banque(movement, entry)
    assert result.complet is True
    assert result.lignes[0]["compte"] == entry.compte_tiers
    assert result.lignes[0]["debit"] == Decimal("1200.00")
    assert result.lignes[1]["compte"] == "514100000000"
    assert result.lignes[1]["credit"] == Decimal("1200.00")


def test_credit_bancaire_debite_banque_et_credite_client():
    entry = _entry(TypeEcritureEnum.VENTE)
    movement = MouvementBancaire(
        cabinet_id=entry.cabinet_id,
        document_id=uuid.uuid4(),
        entreprise_id=entry.entreprise_id,
        date_operation=date(2026, 5, 22),
        libelle="VIR CLIENT",
        reference="VIR-2",
        type_mouvement=TypeMouvementBancaireEnum.CREDIT,
        montant=Decimal("1200.00"),
        statut_rapprochement="automatique",
        compte_banque="514100000000",
    )
    result = construire_lignes_banque(movement, entry)
    assert result.complet is True
    assert result.lignes[0]["compte"] == "514100000000"
    assert result.lignes[0]["debit"] == Decimal("1200.00")
    assert result.lignes[1]["compte"] == entry.compte_tiers
    assert result.lignes[1]["credit"] == Decimal("1200.00")


def test_paiement_partiel_n_est_pas_automatise():
    entry = _entry(TypeEcritureEnum.ACHAT)
    movement = MouvementBancaire(
        cabinet_id=entry.cabinet_id,
        document_id=uuid.uuid4(),
        entreprise_id=entry.entreprise_id,
        date_operation=date(2026, 5, 22),
        libelle="VIR PARTIEL",
        type_mouvement=TypeMouvementBancaireEnum.DEBIT,
        montant=Decimal("600.00"),
        statut_rapprochement="confirme",
        compte_banque="514100000000",
    )
    result = construire_lignes_banque(movement, entry)
    assert result.complet is False
    assert any("partiel" in reason.lower() for reason in result.raisons)
