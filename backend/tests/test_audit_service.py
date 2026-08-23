import uuid
from types import SimpleNamespace

from app.services.audit_service import enregistrer


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


def test_audit_est_scope_au_cabinet_et_trace_avant_apres():
    db = FakeSession()
    user = SimpleNamespace(id=uuid.uuid4(), cabinet_id=uuid.uuid4())
    resource_id = uuid.uuid4()
    journal = enregistrer(
        db, user=user, action="document.validate", resource_type="document",
        resource_id=resource_id, avant={"statut": "traite"}, apres={"statut": "valide"},
    )
    assert db.added == [journal]
    assert journal.cabinet_id == user.cabinet_id
    assert journal.user_id == user.id
    assert journal.details["resource_id"] == str(resource_id)
    assert journal.details["avant"] == {"statut": "traite"}
