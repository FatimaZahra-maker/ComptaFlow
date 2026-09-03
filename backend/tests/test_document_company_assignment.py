from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from app.api import documents as documents_api
from app.models.enums import StatutDocumentEnum
from app.schemas.document import DocumentEntrepriseUpdate


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, company):
        self.company = company
        self.commits = 0

    def execute(self, _query):
        return _Result(self.company)

    def commit(self):
        self.commits += 1

    def refresh(self, _value):
        pass


def _document(cabinet_id):
    return SimpleNamespace(
        id=uuid.uuid4(), cabinet_id=cabinet_id, entreprise_id=None,
        donnees_extraites={"numero_facture": "F-1"},
        statut=StatutDocumentEnum.TRAITE, message_erreur="ancienne erreur",
        type_erreur="definitive", error_code="OCR", saisie_topaze=True,
    )


def test_attribution_manuelle_est_auditee_et_relance_le_traitement(monkeypatch):
    cabinet_id, company_id = uuid.uuid4(), uuid.uuid4()
    document = _document(cabinet_id)
    company = SimpleNamespace(id=company_id)
    db = _Db(company)
    calls = {"deleted": 0, "queued": 0, "audit": 0}
    monkeypatch.setattr(documents_api, "_get_document_or_404", lambda *_args: document)
    monkeypatch.setattr(documents_api.workflow_comptable_service, "verifier_document_modifiable", lambda *_args: None)
    monkeypatch.setattr(documents_api, "_delete_accounting_data", lambda *_args: calls.__setitem__("deleted", 1))
    monkeypatch.setattr(documents_api.audit_service, "enregistrer", lambda *_args, **_kwargs: calls.__setitem__("audit", 1))
    monkeypatch.setattr(documents_api.process_document, "delay", lambda *_args: calls.__setitem__("queued", 1))
    monkeypatch.setattr(documents_api, "_build_document_detail", lambda _db, item: item)

    result = documents_api.attribuer_document_entreprise(
        document.id, DocumentEntrepriseUpdate(entreprise_id=company_id), db,
        SimpleNamespace(id=uuid.uuid4(), cabinet_id=cabinet_id),
    )

    assert result.entreprise_id == company_id
    assert result.donnees_extraites["_entreprise_forcee_id"] == str(company_id)
    assert result.statut == StatutDocumentEnum.EN_ATTENTE
    assert result.saisie_topaze is False
    assert calls == {"deleted": 1, "queued": 1, "audit": 1}
    assert db.commits == 1


def test_attribution_refuse_entreprise_non_autorisee(monkeypatch):
    cabinet_id = uuid.uuid4()
    document = _document(cabinet_id)
    db = _Db(None)
    monkeypatch.setattr(documents_api, "_get_document_or_404", lambda *_args: document)
    monkeypatch.setattr(documents_api.workflow_comptable_service, "verifier_document_modifiable", lambda *_args: None)

    with pytest.raises(HTTPException) as error:
        documents_api.attribuer_document_entreprise(
            document.id, DocumentEntrepriseUpdate(entreprise_id=uuid.uuid4()), db,
            SimpleNamespace(id=uuid.uuid4(), cabinet_id=cabinet_id),
        )
    assert error.value.status_code == 404
    assert db.commits == 0
