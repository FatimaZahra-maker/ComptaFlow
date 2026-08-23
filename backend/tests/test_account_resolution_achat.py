from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.enums import StatutValidationEnum, TypeEcritureEnum
from app.services import (
    accounting_service,
    ai_service,
    groq_service,
    plan_comptable_service,
)
from app.services.accounting_rules_service import (
    FAMILLE_TVA_RECUPERABLE_CHARGES,
    FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    CompteComptableEntreprise.__table__.create(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def scope():
    return SimpleNamespace(
        cabinet_id=uuid.uuid4(),
        entreprise_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
    )


def add_account(
    db: Session,
    scope,
    numero: str,
    *,
    famille: str,
    usage: str,
    nature: str | None = None,
    tiers: str | None = None,
    divers: bool = False,
    source: str = "test",
):
    account = CompteComptableEntreprise(
        cabinet_id=scope.cabinet_id,
        entreprise_id=scope.entreprise_id,
        numero_compte=numero,
        libelle=f"Compte {numero}",
        famille_cgnc=famille,
        type_usage=usage,
        nature_comptable=nature,
        tiers_nom=tiers,
        tiers_normalise=plan_comptable_service.normaliser_tiers(tiers),
        est_divers=divers,
        is_active=True,
        source=source,
    )
    db.add(account)
    db.commit()
    return account


def document(scope):
    return SimpleNamespace(
        id=scope.document_id,
        cabinet_id=scope.cabinet_id,
        entreprise_id=scope.entreprise_id,
    )


def entry():
    return SimpleNamespace(compte_ht=None, compte_tva=None)


def test_achat_nature_et_compte_ht_unique_remplit_compte(db, scope):
    add_account(
        db,
        scope,
        "612100000001",
        famille="6121",
        usage="ht",
        nature="matieres_premieres",
    )
    data = {"nature_comptable": "matieres_premieres"}

    account, reasons = accounting_service._resoudre_compte_ht_achat(
        db, document(scope), entry(), data
    )

    assert account == "612100000001"
    assert reasons == []
    assert data["famille_compte_ht_suggeree"] == "6121"
    assert data["compte_ht_resolution"] == "plan_comptable_entreprise"


def test_achat_tva_charge_unique_remplit_compte_tva(db, scope):
    add_account(
        db,
        scope,
        "345520000001",
        famille=FAMILLE_TVA_RECUPERABLE_CHARGES,
        usage="tva",
    )
    data = {"traitement_comptable_suggere": "charge"}

    account, reasons = accounting_service._resoudre_compte_tva_achat(
        db, document(scope), entry(), data, Decimal("20.00")
    )

    assert account == "345520000001"
    assert reasons == []
    assert data["famille_compte_tva_suggeree"] == "34552"


def test_immobilisation_utilise_famille_tva_immobilisations(db, scope):
    add_account(
        db,
        scope,
        "345510000001",
        famille=FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS,
        usage="tva",
    )
    data = {
        "traitement_comptable_suggere": "immobilisation_candidate",
        "traitement_comptable_confirme": "immobilisation",
    }

    account, reasons = accounting_service._resoudre_compte_tva_achat(
        db, document(scope), entry(), data, Decimal("100.00")
    )

    assert account == "345510000001"
    assert reasons == []
    assert data["famille_compte_tva_suggeree"] == "34551"


def test_compte_ht_absent_ne_cree_rien_et_impose_verification(
    db, scope, monkeypatch
):
    monkeypatch.setattr(
        accounting_service,
        "_chercher_compte_ht_connu",
        lambda *_args, **_kwargs: None,
    )
    data = {"nature_comptable": "matieres_premieres"}

    account, reasons = accounting_service._resoudre_compte_ht_achat(
        db, document(scope), entry(), data
    )
    resulting_status = (
        StatutValidationEnum.A_VERIFIER
        if reasons
        else StatutValidationEnum.BROUILLON
    )

    assert account is None
    assert resulting_status == StatutValidationEnum.A_VERIFIER
    assert data["compte_ht_resolution"] == "compte_exact_a_configurer"
    assert "6121" in reasons[0]


def test_plusieurs_comptes_ht_possibles_ne_choisit_pas(db, scope):
    for suffix in ("001", "002"):
        add_account(
            db,
            scope,
            f"612100000{suffix}",
            famille="6121",
            usage="ht",
            nature="matieres_premieres",
        )

    result = plan_comptable_service.resoudre_compte_par_famille(
        db,
        cabinet_id=scope.cabinet_id,
        entreprise_id=scope.entreprise_id,
        famille_cgnc="6121",
        type_usage="ht",
        nature_comptable="matieres_premieres",
    )

    assert result.compte is None
    assert result.statut == "ambigu"
    assert len(result.candidats) == 2


def test_fournisseur_avec_compte_tiers_exact_retourne_compte_et_source(
    db, scope
):
    account = add_account(
        db,
        scope,
        "441103000001",
        famille="4411",
        usage="fournisseur",
        tiers="STE ALMAZ MED",
        source="import_csv",
    )

    result = plan_comptable_service.chercher_compte_tiers(
        db,
        cabinet_id=scope.cabinet_id,
        entreprise_id=scope.entreprise_id,
        tiers="  ste almaz med ",
        type_usage="fournisseur",
    )

    assert result.compte == "441103000001"
    assert result.statut == "trouve"
    assert account.source == "import_csv"


def test_fournisseur_inconnu_conserve_fallback_divers_explicite(db, scope):
    result = plan_comptable_service.chercher_compte_tiers(
        db,
        cabinet_id=scope.cabinet_id,
        entreprise_id=scope.entreprise_id,
        tiers="FOURNISSEUR INCONNU",
        type_usage="fournisseur",
    )

    assert result.statut == "introuvable"
    assert result.compte is None
    account, source = accounting_service._choisir_compte_tiers(
        type_ecriture=TypeEcritureEnum.ACHAT,
        compte_existant=None,
        compte_plan=None,
        compte_fourni=None,
        compte_historique=None,
        compte_divers_plan=None,
    )
    assert account == accounting_service.COMPTE_FOURNISSEUR_DIVERS
    assert account == "441100000000"
    assert source == "divers_provisoire"


def test_compte_fournisseur_exact_remplace_ancien_fallback_divers():
    account, source = accounting_service._choisir_compte_tiers(
        type_ecriture=TypeEcritureEnum.ACHAT,
        compte_existant="441100000000",
        compte_plan="441103000001",
        compte_fourni=None,
        compte_historique=None,
        compte_divers_plan=None,
    )

    assert account == "441103000001"
    assert source == "plan_comptable_entreprise"


def test_resolution_respecte_cabinet_et_entreprise(db, scope):
    other_scope = SimpleNamespace(
        cabinet_id=uuid.uuid4(),
        entreprise_id=uuid.uuid4(),
    )
    add_account(
        db,
        other_scope,
        "612100000099",
        famille="6121",
        usage="ht",
        nature="matieres_premieres",
    )

    result = plan_comptable_service.resoudre_compte_par_famille(
        db,
        cabinet_id=scope.cabinet_id,
        entreprise_id=scope.entreprise_id,
        famille_cgnc="6121",
        type_usage="ht",
        nature_comptable="matieres_premieres",
    )

    assert result.compte is None
    assert result.statut == "introuvable"


def test_groq_texte_conserve_la_nature_economique(monkeypatch):
    monkeypatch.setattr(groq_service.settings, "GROQ_API_KEY", "test")
    monkeypatch.setattr(
        groq_service,
        "_appeler_groq_texte_avec_retry",
        lambda _text: (
            '{"nom_fournisseur":"FOURNISSEUR","nom_client":"ANZOBAT",'
            '"categorie_document":"facture","nature_comptable":"matieres_premieres",'
            '"montant_ht":100,"montant_tva":20,"montant_ttc":120}'
        ),
    )

    result = groq_service.extraire_et_classifier("FACTURE MATIERES PREMIERES")

    assert result is not None
    assert result["nature_comptable"] == "matieres_premieres"
    assert result["confiance_par_champ"]["nature_comptable"] == 0.90


def test_fallback_ollama_conserve_la_meme_nature_controlee(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": (
                    '{"nom_entreprise":"FOURNISSEUR","tiers":"ANZOBAT",'
                    '"categorie":"achats",'
                    '"nature_comptable":"matieres_premieres"}'
                )
            }

    monkeypatch.setattr(
        ai_service.requests,
        "post",
        lambda *_args, **_kwargs: Response(),
    )

    result = ai_service.enrichir_avec_ia(
        "FACTURE MATIERES PREMIERES ANZOBAT",
        "facture",
    )

    assert result["nature_comptable"] == "matieres_premieres"
