"""
backend/app/api/documents.py
Route d'upload : recoit un fichier, le sauvegarde physiquement sur le
disque, enregistre ses metadonnees en base, puis declenche le pipeline
OCR/IA en arriere-plan via Celery.

Route de detail (GET /{document_id}) : renvoie toutes les informations
d'un document pour alimenter la page "Detail document" du frontend.

Route de fichier (GET /{document_id}/fichier) : stream le fichier
original (PDF/image) depuis le disque -- alimente le lien "Consulter"
du tableau comptable, pour que le comptable puisse vérifier l'original
face aux données extraites.

Route de retraitement (POST /{document_id}/retraiter) : relance le
pipeline complet sur un document déjà uploadé (bouton "Retraiter" du
frontend, ChronosPage.tsx) -- utile après un correctif OCR/IA, ou si
le document était tombé en erreur. Supprime l'écriture comptable
existante avant de relancer, pour ne jamais créer de doublon.
"""
import hashlib
import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_flexible
from app.core.config import settings
from app.models.user import User
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.enums import StatutDocumentEnum
from app.schemas.document import DocumentOut
from app.schemas.document_detail import DocumentDetailOut
from app.tasks.document_processing import process_document

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf", "image/png", "image/jpeg", "image/jpg"
}
MAX_FILE_SIZE_MB = 20


@router.post("/upload", response_model=DocumentOut)
def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Type de fichier non autorise : {file.content_type}. "
                   f"Types acceptes : PDF, PNG, JPEG.",
        )

    content = file.file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Fichier trop volumineux : {size_mb:.1f}MB (max {MAX_FILE_SIZE_MB}MB).",
        )

    file_hash = hashlib.sha256(content).hexdigest()
    existing = db.execute(
        select(Document).where(
            Document.cabinet_id == current_user.cabinet_id,
            Document.hash_fichier == file_hash,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Ce fichier a deja ete uploade (document {existing.id}).",
        )

    storage_dir = Path(settings.STORAGE_PATH) / str(current_user.cabinet_id)
    storage_dir.mkdir(parents=True, exist_ok=True)
    file_extension = Path(file.filename).suffix
    stored_filename = f"{uuid.uuid4()}{file_extension}"
    stored_path = storage_dir / stored_filename

    with open(stored_path, "wb") as f:
        f.write(content)

    document = Document(
        cabinet_id=current_user.cabinet_id,
        uploaded_by=current_user.id,
        nom_fichier_original=file.filename,
        chemin_stockage=str(stored_path),
        hash_fichier=file_hash,
        taille_octets=len(content),
        mime_type=file.content_type,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    process_document.delay(str(document.id))

    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    documents = db.execute(
        select(Document).where(Document.cabinet_id == current_user.cabinet_id)
    ).scalars().all()
    return documents


@router.get("/{document_id}", response_model=DocumentDetailOut)
def get_document_detail(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Renvoie le detail complet d'un document : metadonnees, texte OCR,
    donnees extraites, et l'ecriture comptable generee si elle existe.
    """
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.cabinet_id == current_user.cabinet_id,
        )
    ).scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    ecriture = db.execute(
        select(EcritureComptable).where(EcritureComptable.document_id == document.id)
    ).scalars().first()
    
    mouvements = db.execute(
        select(MouvementBancaire).where(MouvementBancaire.document_id == document.id)
    ).scalars().all()

    return DocumentDetailOut(
        id=document.id,
        nom_fichier_original=document.nom_fichier_original,
        taille_octets=document.taille_octets,
        mime_type=document.mime_type,
        statut=document.statut,
        created_at=document.created_at,
        entreprise_id=document.entreprise_id,
        annee=document.annee,
        mois=document.mois,
        categorie=document.categorie.value if document.categorie else None,
        texte_ocr=document.texte_ocr,
        donnees_extraites=document.donnees_extraites,
        message_erreur=document.message_erreur,
        type_erreur=document.type_erreur.value if document.type_erreur else None,
        error_code=document.error_code,
        ecriture=ecriture,
        mouvements_bancaires=mouvements,
    )


@router.get("/{document_id}/fichier")
def telecharger_fichier_original(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    """
    Stream le fichier original (PDF/image) tel qu'uploadé, pour
    consultation dans le tableau comptable ("vérifier l'original").

    Utilise get_current_user_flexible (token en query param ?token=...)
    car cette route est ouverte via <a href> ou <iframe src> depuis le
    frontend, qui ne peut pas envoyer de header Authorization -- même
    principe que la route d'export (voir app/api/export.py).

    Le filtre cabinet_id est OBLIGATOIRE : sans lui, un utilisateur
    pourrait deviner l'UUID d'un document d'un AUTRE cabinet et accéder
    à son fichier physique (règle de sécurité du projet).
    """
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.cabinet_id == current_user.cabinet_id,
        )
    ).scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    chemin_fichier = Path(document.chemin_stockage)
    if not chemin_fichier.exists():
        raise HTTPException(
            status_code=404,
            detail="Fichier original introuvable sur le serveur (a-t-il été déplacé/supprimé ?).",
        )

    type_mime = document.mime_type or mimetypes.guess_type(str(chemin_fichier))[0] or "application/octet-stream"

    return FileResponse(
        path=chemin_fichier,
        media_type=type_mime,
        filename=document.nom_fichier_original,
        # inline (pas attachment) : le navigateur affiche le PDF/image
        # directement plutôt que de forcer un téléchargement -- plus
        # pratique pour une consultation rapide de vérification.
        headers={"Content-Disposition": f'inline; filename="{document.nom_fichier_original}"'},
    )


@router.post("/{document_id}/retraiter", response_model=DocumentOut)
def retraiter_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Relance le pipeline complet (OCR + extraction + comptabilisation)
    sur un document déjà uploadé -- bouton "Retraiter" du frontend
    (ChronosPage.tsx). Ne re-sauvegarde PAS le fichier physique (déjà
    sur disque, chemin_stockage inchangé) : réinitialise juste l'état
    du document et relance process_document dessus.

    L'écriture comptable existante est supprimée avant de relancer,
    pour ne jamais créer de doublon si le retraitement produit une
    nouvelle écriture (ex: après un correctif de l'extraction IA).
    """
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.cabinet_id == current_user.cabinet_id,
        )
    ).scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="Document introuvable.")

    chemin_fichier = Path(document.chemin_stockage)
    if not chemin_fichier.exists():
        raise HTTPException(
            status_code=404,
            detail="Fichier original introuvable sur le serveur -- impossible de retraiter.",
        )

    db.query(EcritureComptable).filter(EcritureComptable.document_id == document.id).delete()
    db.query(MouvementBancaire).filter(MouvementBancaire.document_id == document.id).delete()

    document.statut = StatutDocumentEnum.EN_ATTENTE
    document.texte_ocr = None
    document.donnees_extraites = None
    document.message_erreur = None
    document.type_erreur = None
    document.error_code = None
    document.categorie = None
    document.annee = None
    document.mois = None
    document.entreprise_id = None
    db.commit()
    db.refresh(document)

    process_document.delay(str(document.id))

    return document