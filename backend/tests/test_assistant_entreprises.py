import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.entreprise import Entreprise
from app.models.enums import RoleEnum
from app.schemas.assistant import AssistantQuery
from app.services import assistant_service


QUESTIONS_LISTE = [
    "quelle sont les entreprise existe ?",
    "quelles sont les entreprises existantes ?",
    "liste les entreprises",
    "donne-moi les sociétés de mon cabinet",
]


@pytest.fixture()
def db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Entreprise.__table__.create(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _user(cabinet_id=None):
    return SimpleNamespace(
        id=uuid.uuid4(), cabinet_id=cabinet_id or uuid.uuid4(),
        role=RoleEnum.COLLABORATEUR,
    )


def _company(db, cabinet_id, nom, *, active=True, automatic=False, ice=None):
    company = Entreprise(
        cabinet_id=cabinet_id, nom=nom, ice=ice,
        is_active=active, creee_automatiquement=automatic,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


@pytest.mark.parametrize("question", QUESTIONS_LISTE)
def test_formulations_entreprises_ne_tombent_jamais_sur_une_facture(db, monkeypatch, question):
    user = _user()
    company = _company(db, user.cabinet_id, "ANZOBAT", ice="001122334455667")
    monkeypatch.setattr(
        assistant_service.groq_service,
        "interpreter_question_assistant",
        lambda _question: pytest.fail("Le fallback déterministe devait reconnaître cette intention."),
    )

    response = assistant_service.repondre(db, user, AssistantQuery(question=question))

    assert response.intent == "list_entreprises"
    assert response.response_type == "company_list"
    assert response.total_count == 1
    assert [item.entreprise_id for item in response.companies] == [company.id]
    assert "facture" not in response.message.lower()
    assert response.clarification_question is None


def test_compter_entreprises_reconnait_la_phrase_exacte(db, monkeypatch):
    user = _user()
    _company(db, user.cabinet_id, "ANZOBAT")
    _company(db, user.cabinet_id, "BETA")
    monkeypatch.setattr(assistant_service.groq_service, "interpreter_question_assistant", lambda _q: None)

    response = assistant_service.repondre(
        db, user, AssistantQuery(question="combien d’entreprises avons-nous ?"),
    )

    assert response.intent == "count_entreprises"
    assert response.total_count == 2
    assert [item.nom for item in response.companies] == ["ANZOBAT", "BETA"]


def test_liste_entreprises_respecte_cabinet_inactives_et_dossiers_non_valides(db):
    user = _user()
    own = _company(db, user.cabinet_id, "AUTORISEE")
    _company(db, user.cabinet_id, "INACTIVE", active=False)
    _company(db, user.cabinet_id, "A IDENTIFIER", automatic=True)
    _company(db, uuid.uuid4(), "AUTRE CABINET")

    response = assistant_service.repondre(
        db, user, AssistantQuery(question="quelles entreprises sont disponibles ?"),
    )

    assert response.total_count == 1
    assert [item.entreprise_id for item in response.companies] == [own.id]
    serialized = response.model_dump_json()
    assert "INACTIVE" not in serialized
    assert "A IDENTIFIER" not in serialized
    assert "AUTRE CABINET" not in serialized


def test_utilisateur_sans_entreprise_autorisee(db):
    user = _user()
    _company(db, uuid.uuid4(), "AUTRE CABINET")

    response = assistant_service.repondre(
        db, user, AssistantQuery(question="liste les entreprises"),
    )

    assert response.response_type == "no_result"
    assert response.total_count == 0
    assert response.companies == []
    assert response.message == "Aucune entreprise n'est actuellement disponible pour votre compte."


def test_question_inconnue_reste_inconnue_si_ia_indisponible(monkeypatch):
    monkeypatch.setattr(assistant_service.groq_service, "interpreter_question_assistant", lambda _q: None)

    response = assistant_service.repondre(
        None, _user(), AssistantQuery(question="Peux-tu analyser ma demande mystérieuse ?"),
    )

    assert response.intent == "unknown"
    assert response.response_type == "clarification"
    assert "numéro" not in response.message.lower()
    assert "quelle facture" not in response.message.lower()
    assert "entreprises" in response.message.lower()


def test_recherche_facture_sans_critere_conserve_sa_clarification(monkeypatch):
    monkeypatch.setattr(assistant_service, "_resolve_company", lambda *_args, **_kwargs: None)

    response = assistant_service.repondre(
        None, _user(), AssistantQuery(question="Recherche une facture"),
    )

    assert response.intent == "search_document"
    assert response.response_type == "clarification"
    assert response.clarification_question == "Quelle facture recherchez-vous ?"
