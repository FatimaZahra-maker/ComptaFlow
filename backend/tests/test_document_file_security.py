from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api import documents


@pytest.mark.parametrize(
    ("content", "name", "mime"),
    [
        (b"%PDF-1.7\n", "facture.pdf", "application/pdf"),
        (b"\x89PNG\r\n\x1a\nrest", "scan.png", "image/png"),
        (b"\xff\xd8\xffrest", "photo.jpeg", "image/jpeg"),
    ],
)
def test_validation_upload_accepte_signature_extension_et_mime_coherents(content, name, mime):
    assert documents._valider_fichier_uploade(content, name, mime)[0] == mime


def test_validation_upload_refuse_un_pdf_deguise_en_image():
    with pytest.raises(HTTPException) as exc:
        documents._valider_fichier_uploade(b"%PDF-1.7\n", "scan.jpg", "image/jpeg")
    assert exc.value.status_code == 400


def test_validation_upload_refuse_une_taille_superieure_a_la_limite(monkeypatch):
    monkeypatch.setattr(documents, "MAX_FILE_SIZE_BYTES", 4)
    with pytest.raises(HTTPException) as exc:
        documents._valider_fichier_uploade(b"%PDF-", "facture.pdf", "application/pdf")
    assert exc.value.status_code == 400


def test_chemin_document_doît_rester_dans_storage(monkeypatch, tmp_path):
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(documents.settings, "STORAGE_PATH", str(storage))

    dedans = storage / "cabinet" / "document.pdf"
    dedans.parent.mkdir()
    dedans.write_bytes(b"%PDF-")
    assert documents._resoudre_chemin_stockage(str(dedans)) == dedans.resolve()

    with pytest.raises(HTTPException) as exc:
        documents._resoudre_chemin_stockage(str(tmp_path / "secret.txt"))
    assert exc.value.status_code == 404
