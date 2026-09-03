import uuid
from types import SimpleNamespace

from app.models.enums import RoleEnum
from app.services import audit_service


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


def _user():
    return SimpleNamespace(
        id=uuid.uuid4(), cabinet_id=uuid.uuid4(), email="admin@example.test",
        prenom="Fati", nom="Radoui", role=RoleEnum.ADMIN_CABINET,
    )


def test_audit_v2_conserve_snapshot_et_scope_cabinet():
    db = FakeSession()
    user = _user()
    company_id = uuid.uuid4()
    event = audit_service.enregistrer(
        db, user=user, action=audit_service.AuditAction.DOCUMENT_UPDATED,
        entreprise_id=company_id, resource_type="document", resource_id=uuid.uuid4(),
        avant={"montant_tva": "1500.00"}, apres={"montant_tva": "1566.67"},
    )
    assert db.added == [event]
    assert event.cabinet_id == user.cabinet_id
    assert event.entreprise_id == company_id
    assert event.actor_email == user.email
    assert event.actor_role == RoleEnum.ADMIN_CABINET.value
    assert event.old_values == {"montant_tva": "1500.00"}


def test_audit_v2_supprime_secrets_et_texte_ocr_des_metadonnees():
    event = audit_service.enregistrer(
        FakeSession(), user=_user(), action="TEST", resource_type="document",
        metadata={
            "password": "secret", "jwt_token": "token", "texte_ocr": "contenu",
            "utile": "conservé", "nested": {"api_key": "x", "statut": "ok"},
        },
    )
    assert event.event_metadata == {"utile": "conservé", "nested": {"statut": "ok"}}


def test_audit_v2_ne_garde_que_les_champs_modifies():
    before, after = audit_service.valeurs_modifiees(
        {"tiers": "ALPHA", "tva": "100", "statut": "a_verifier"},
        {"tiers": "ALPHA", "tva": "120", "statut": "valide"},
    )
    assert before == {"tva": "100", "statut": "a_verifier"}
    assert after == {"tva": "120", "statut": "valide"}


def test_audit_v2_operation_groupee_stocke_uniquement_les_identifiants():
    ids = [uuid.uuid4() for _ in range(3)]
    event = audit_service.enregistrer(
        FakeSession(), user=_user(), action=audit_service.AuditAction.DOCUMENTS_UPLOADED,
        resource_type="document", resource_ids=ids, item_count=3,
        metadata={"filenames": ["FA-120.pdf", "FA-121.pdf", "FA-122.pdf"]},
    )
    assert event.item_count == 3
    assert event.resource_ids == [str(value) for value in ids]
    assert "contenu" not in event.event_metadata
