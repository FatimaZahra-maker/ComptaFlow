from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import uuid

from app.models.ecriture import EcritureComptable
from app.models.enums import StatutValidationEnum, TypeEcritureEnum, TypeMouvementBancaireEnum
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.services import exchange_difference_service as fx2
from app.services.ligne_comptable_service import _construire_lignes_allocations
from app.services.plan_comptable_service import ResolutionCompte


def test_achat_devise_reglement_superieur_est_une_perte_debit():
    ecart, nature = fx2.classifier_ecart_change(
        type_ecriture=TypeEcritureEnum.ACHAT,
        valeur_comptable_mad=Decimal("10800.00"),
        montant_reglement_mad=Decimal("10950.00"),
    )
    assert (ecart, nature) == (Decimal("150.00"), "perte")


def test_achat_devise_reglement_inferieur_est_un_gain_credit():
    ecart, nature = fx2.classifier_ecart_change(
        type_ecriture=TypeEcritureEnum.ACHAT,
        valeur_comptable_mad=Decimal("10800.00"),
        montant_reglement_mad=Decimal("10700.00"),
    )
    assert (ecart, nature) == (Decimal("100.00"), "gain")


def test_vente_devise_reglement_inferieur_est_une_perte_debit():
    ecart, nature = fx2.classifier_ecart_change(
        type_ecriture=TypeEcritureEnum.VENTE,
        valeur_comptable_mad=Decimal("10800.00"),
        montant_reglement_mad=Decimal("10700.00"),
    )
    assert (ecart, nature) == (Decimal("100.00"), "perte")


def test_vente_devise_reglement_superieur_est_un_gain_credit():
    ecart, nature = fx2.classifier_ecart_change(
        type_ecriture=TypeEcritureEnum.VENTE,
        valeur_comptable_mad=Decimal("10800.00"),
        montant_reglement_mad=Decimal("10950.00"),
    )
    assert (ecart, nature) == (Decimal("150.00"), "gain")


def test_paiement_partiel_conserve_le_prorata_initial_sur_plusieurs_reglements():
    first = fx2.calculer_valeur_comptable_partielle(
        montant_total_devise=Decimal("1000"),
        valeur_totale_mad=Decimal("10800"),
        montant_devise_regle=Decimal("400"),
    )
    second = fx2.calculer_valeur_comptable_partielle(
        montant_total_devise=Decimal("1000"),
        valeur_totale_mad=Decimal("10800"),
        montant_devise_regle=Decimal("600"),
    )
    assert first == Decimal("4320.00")
    assert second == Decimal("6480.00")
    assert first + second == Decimal("10800.00")


def _entry(kind=TypeEcritureEnum.ACHAT, *, cabinet_id=None, entreprise_id=None):
    entry = EcritureComptable(
        id=uuid.uuid4(),
        cabinet_id=cabinet_id or uuid.uuid4(),
        entreprise_id=entreprise_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        type_ecriture=kind,
        montant_ttc=Decimal("10800.00"),
        devise_originale="EUR",
        montant_ttc_devise=Decimal("1000.000000"),
        montant_ttc_mad=Decimal("10800.00"),
        taux_change_initial=Decimal("10.8000000000"),
        unite_cotation_initiale=1,
        date_cours_initial=date(2026, 1, 10),
        source_cours_initial="bam_billets_etrangers",
        date_piece=date(2026, 1, 10),
        statut_validation=StatutValidationEnum.VALIDE,
        compte_tiers="441100000000" if kind == TypeEcritureEnum.ACHAT else "342100000000",
    )
    return entry


def _movement(entry, amount="10950.00"):
    return MouvementBancaire(
        id=uuid.uuid4(),
        cabinet_id=entry.cabinet_id,
        entreprise_id=entry.entreprise_id,
        document_id=uuid.uuid4(),
        date_operation=date(2026, 2, 10),
        libelle="RÈGLEMENT EUR",
        type_mouvement=(
            TypeMouvementBancaireEnum.DEBIT
            if entry.type_ecriture == TypeEcritureEnum.ACHAT
            else TypeMouvementBancaireEnum.CREDIT
        ),
        montant=Decimal(amount),
        montant_mad=Decimal(amount),
        montant_mad_theorique=Decimal(amount),
        montant_mad_source="bam",
        devise_originale="EUR",
        montant_devise=Decimal("1000.000000"),
        taux_change=Decimal("10.9500000000"),
        date_cours_change=date(2026, 2, 10),
        compte_banque="514100000000",
        nature_operation="reglement_facture",
        statut_rapprochement="confirme",
    )


def test_cours_reglement_manquant_met_allocation_a_verifier():
    entry = _entry()
    movement = _movement(entry)
    movement.taux_change = None
    result = fx2.preparer_ecart_allocation(
        SimpleNamespace(),  # aucun accès DB avant le contrôle du cours
        mouvement=movement,
        ecriture=entry,
        montant_reglement_mad=Decimal("10950.00"),
    )
    assert result.complet is False
    assert result.nature == "a_verifier"
    assert "cours bam" in (result.raison or "").lower()


def test_compte_perte_manquant_ne_genere_aucun_numero(monkeypatch):
    entry = _entry()
    movement = _movement(entry)
    monkeypatch.setattr(
        fx2.plan_comptable_service,
        "chercher_compte_usage_unique",
        lambda *args, **kwargs: ResolutionCompte(None, "introuvable"),
    )
    result = fx2.preparer_ecart_allocation(
        SimpleNamespace(),
        mouvement=movement,
        ecriture=entry,
        montant_reglement_mad=Decimal("10950.00"),
    )
    assert result.complet is False
    assert result.compte is None
    assert "aucun compte ne sera inventé" in (result.raison or "")


def test_resolution_compte_est_strictement_multi_tenant(monkeypatch):
    cabinet_id = uuid.uuid4()
    entreprise_id = uuid.uuid4()
    entry = _entry(cabinet_id=cabinet_id, entreprise_id=entreprise_id)
    movement = _movement(entry)
    captured = {}

    def resolver(_db, **kwargs):
        captured.update(kwargs)
        return ResolutionCompte("633100000000", "trouve")

    monkeypatch.setattr(
        fx2.plan_comptable_service,
        "chercher_compte_usage_unique",
        resolver,
    )
    result = fx2.preparer_ecart_allocation(
        SimpleNamespace(),
        mouvement=movement,
        ecriture=entry,
        montant_reglement_mad=Decimal("10950.00"),
    )
    assert result.complet is True
    assert captured["cabinet_id"] == cabinet_id
    assert captured["entreprise_id"] == entreprise_id
    assert captured["type_usage"] == "perte_change"

    foreign_entry = _entry(cabinet_id=uuid.uuid4(), entreprise_id=entreprise_id)
    rejected = fx2.preparer_ecart_allocation(
        SimpleNamespace(),
        mouvement=movement,
        ecriture=foreign_entry,
        montant_reglement_mad=Decimal("10950.00"),
    )
    assert rejected.complet is False
    assert "tenant" in (rejected.raison or "")


class _Query:
    def __init__(self, allocations):
        self.allocations = allocations

    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self.allocations


class _Db:
    def __init__(self, entry, allocation):
        self.entry = entry
        self.allocation = allocation

    def query(self, model):
        return _Query([self.allocation])

    def get(self, model, object_id):
        return self.entry if object_id == self.entry.id else None


def test_lignes_achat_perte_sont_deduites_du_desequilibre_reel():
    entry = _entry()
    movement = _movement(entry)
    allocation = RapprochementBancaireAllocation(
        cabinet_id=entry.cabinet_id,
        entreprise_id=entry.entreprise_id,
        mouvement_bancaire_id=movement.id,
        ecriture_id=entry.id,
        montant_affecte=Decimal("10950.00"),
        montant_reglement_mad=Decimal("10950.00"),
        valeur_comptable_mad=Decimal("10800.00"),
        ecart_change_mad=Decimal("150.00"),
        nature_ecart_change="perte",
        compte_ecart_change="633100000000",
        statut_ecart_change="comptabilise",
        statut="confirme",
    )
    result = _construire_lignes_allocations(_Db(entry, allocation), movement)
    assert result.complet is True
    assert sum(line["debit"] for line in result.lignes) == Decimal("10950.00")
    assert sum(line["credit"] for line in result.lignes) == Decimal("10950.00")
    loss = next(line for line in result.lignes if line["compte"] == "633100000000")
    assert loss["debit"] == Decimal("150.00")


def test_lignes_vente_gain_sont_creditees():
    entry = _entry(TypeEcritureEnum.VENTE)
    movement = _movement(entry)
    allocation = RapprochementBancaireAllocation(
        cabinet_id=entry.cabinet_id,
        entreprise_id=entry.entreprise_id,
        mouvement_bancaire_id=movement.id,
        ecriture_id=entry.id,
        montant_affecte=Decimal("10950.00"),
        montant_reglement_mad=Decimal("10950.00"),
        valeur_comptable_mad=Decimal("10800.00"),
        ecart_change_mad=Decimal("150.00"),
        nature_ecart_change="gain",
        compte_ecart_change="733100000000",
        statut_ecart_change="comptabilise",
        statut="confirme",
    )
    result = _construire_lignes_allocations(_Db(entry, allocation), movement)
    assert result.complet is True
    gain = next(line for line in result.lignes if line["compte"] == "733100000000")
    assert gain["credit"] == Decimal("150.00")
