from datetime import time
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import messages as messages_api
from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.cabinet import Cabinet
from app.models.cabinet_message import CabinetMessage
from app.models.enums import RoleEnum
from app.models.tache import Tache
from app.models.user import User


@pytest.fixture()
def messaging(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Cabinet.__table__.create(engine)
    User.__table__.create(engine)
    Tache.__table__.create(engine)
    CabinetMessage.__table__.create(engine)
    session = Session(engine)
    cabinet_a = Cabinet(nom="Cabinet A")
    cabinet_b = Cabinet(nom="Cabinet B")
    session.add_all([cabinet_a, cabinet_b])
    session.flush()

    def user(cabinet, email, role):
        item = User(
            cabinet_id=cabinet.id,
            email=email,
            hashed_password="not-used",
            nom=email.split("@")[0].upper(),
            prenom="Test",
            role=role,
            is_active=True,
        )
        session.add(item)
        session.flush()
        return item

    admin_a = user(cabinet_a, "admin-a@example.com", RoleEnum.ADMIN_CABINET)
    collaborator_a = user(cabinet_a, "collab-a@example.com", RoleEnum.COLLABORATEUR)
    other_a = user(cabinet_a, "other-a@example.com", RoleEnum.ASSISTANT)
    admin_b = user(cabinet_b, "admin-b@example.com", RoleEnum.ADMIN_CABINET)
    session.commit()

    monkeypatch.setattr(messages_api.audit_service, "enregistrer", lambda *_args, **_kwargs: None)
    messages_api._access_attempts.clear()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: collaborator_a
    client = TestClient(app)
    yield client, session, admin_a, collaborator_a, other_a, admin_b
    app.dependency_overrides.clear()
    session.close()
    engine.dispose()


def test_demande_renouvellement_cree_un_message_sans_exposer_le_compte(messaging):
    client, session, admin, collaborator, *_ = messaging
    response = client.post("/messages/access-request", json={
        "email": collaborator.email,
        "message": "Merci de renouveler mon accès.",
    })

    assert response.status_code == 202
    assert "Si cette adresse appartient" in response.json()["message"]
    message = session.execute(select(CabinetMessage)).scalar_one()
    assert message.cabinet_id == collaborator.cabinet_id
    assert message.sender_id == collaborator.id
    assert message.recipient_id == admin.id
    assert message.message_type == "access_request"

    unknown = client.post("/messages/access-request", json={"email": "inconnu@example.com"})
    assert unknown.status_code == 202
    assert unknown.json()["message"] == response.json()["message"]


def test_utilisateur_ne_peut_pas_ecrire_hors_cabinet_ni_a_un_autre_utilisateur(messaging):
    client, _, _, _, other, admin_other_cabinet = messaging

    cross_tenant = client.post("/messages", json={"recipient_id": str(admin_other_cabinet.id), "contenu": "Interdit"})
    peer_message = client.post("/messages", json={"recipient_id": str(other.id), "contenu": "Interdit"})

    assert cross_tenant.status_code == 404
    assert peer_message.status_code == 403


def test_non_lu_est_marque_lu_a_louverture_de_la_conversation(messaging):
    client, _, admin, collaborator, *_ = messaging
    sent = client.post("/messages", json={"recipient_id": str(admin.id), "contenu": "Pouvez-vous vérifier ?"})
    assert sent.status_code == 201

    app.dependency_overrides[get_current_user] = lambda: admin
    assert client.get("/messages/unread-count").json()["count"] == 1
    conversation = client.get(f"/messages/{collaborator.id}")
    assert conversation.status_code == 200
    assert conversation.json()[0]["read_at"] is not None
    assert client.get("/messages/unread-count").json()["count"] == 0


def test_administrateur_planifie_un_message_avec_date_et_heure(messaging):
    client, session, admin, collaborator, *_ = messaging
    app.dependency_overrides[get_current_user] = lambda: admin
    sent = client.post("/messages", json={
        "recipient_id": str(collaborator.id),
        "contenu": "Préparer la déclaration de TVA.",
    })
    assert sent.status_code == 201

    planned = client.post(f"/messages/{sent.json()['id']}/task", json={
        "titre": "Préparer la TVA",
        "date_echeance": "2026-09-01",
        "heure_echeance": "14:30",
        "priorite": "haute",
        "recurrence": "mensuelle",
    })

    assert planned.status_code == 201
    assert planned.json()["assignee_a"] == str(collaborator.id)
    assert planned.json()["heure_echeance"] == "14:30:00"
    task = session.execute(select(Tache)).scalar_one()
    assert task.heure_echeance == time(14, 30)
    message = session.get(CabinetMessage, uuid.UUID(sent.json()["id"]))
    assert message.task_id == task.id
