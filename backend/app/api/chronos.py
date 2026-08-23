"""API de la vue Chronos.

Une seule requête renvoie le document, son entreprise et sa première écriture.
Le statut de saisie est porté par Document afin de fonctionner également avec
les relevés bancaires qui n'ont pas nécessairement d'écriture comptable.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import CategorieDocumentEnum
from app.models.user import User
from app.schemas.chrono import DocumentChronoOut

router = APIRouter(prefix="/chronos", tags=["chronos"])

_EMPTY_FILTERS = {"", "toutes", "tous", "all", "none", "null"}


def _normalize_text_filter(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return None if normalized.lower() in _EMPTY_FILTERS else normalized


@router.get("/documents", response_model=list[DocumentChronoOut])
def list_chrono_documents(
    entreprise_id: str | None = Query(default=None),
    categorie: str | None = Query(default=None),
    annee: int | None = Query(default=None),
    mois: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized_company = _normalize_text_filter(entreprise_id)
    normalized_category = _normalize_text_filter(categorie)

    query = (
        select(Document, Entreprise.nom, EcritureComptable)
        .join(Entreprise, Document.entreprise_id == Entreprise.id, isouter=True)
        .join(
            EcritureComptable,
            EcritureComptable.document_id == Document.id,
            isouter=True,
        )
        .where(Document.cabinet_id == current_user.cabinet_id)
    )

    if normalized_company is not None:
        try:
            query = query.where(Document.entreprise_id == uuid.UUID(normalized_company))
        except ValueError:
            return []

    if normalized_category is not None:
        try:
            category_enum = CategorieDocumentEnum(normalized_category.lower())
        except ValueError:
            return []
        query = query.where(Document.categorie == category_enum)

    if annee is not None:
        query = query.where(Document.annee == annee)
    if mois is not None:
        query = query.where(Document.mois == mois)

    rows = db.execute(
        query.order_by(Document.created_at.desc(), EcritureComptable.created_at.asc())
    ).all()

    # Une ancienne base peut exceptionnellement contenir plusieurs écritures
    # liées au même document. La vue Chronos affiche une ligne par document.
    output_by_document: dict[uuid.UUID, DocumentChronoOut] = {}

    for document, company_name, entry in rows:
        if document.id in output_by_document:
            continue

        # Les doublons restent visibles dans Documents, mais ne doivent pas
        # créer de deuxième ligne dans le chrono.
        if document.est_doublon:
            continue

        item = DocumentChronoOut.model_validate(document)
        item.entreprise_nom = company_name
        item.saisie_topaze = document.saisie_topaze

        if entry is not None:
            item.ecriture_id = entry.id
            item.numero_piece = entry.numero_piece
            item.date_piece = entry.date_piece
            item.tiers = entry.tiers
            item.montant_ht = entry.montant_ht
            item.taux_tva = (
                entry.taux_tva.value
                if entry.taux_tva is not None and hasattr(entry.taux_tva, "value")
                else entry.taux_tva
            )
            item.montant_tva = entry.montant_tva
            item.montant_ttc = entry.montant_ttc
            item.statut_validation = (
                entry.statut_validation.value
                if hasattr(entry.statut_validation, "value")
                else str(entry.statut_validation)
            )
            item.anomalie_detectee = entry.anomalie_detectee
            item.anomalie_details = entry.anomalie_details

        output_by_document[document.id] = item

    return list(output_by_document.values())


@router.get("/annees", response_model=list[int])
def list_annees_disponibles(
    entreprise_id: str | None = Query(default=None),
    categorie: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    normalized_company = _normalize_text_filter(entreprise_id)
    normalized_category = _normalize_text_filter(categorie)

    query = select(Document.annee).where(
        Document.cabinet_id == current_user.cabinet_id,
        Document.annee.is_not(None),
    )

    if normalized_company is not None:
        try:
            query = query.where(Document.entreprise_id == uuid.UUID(normalized_company))
        except ValueError:
            return []

    if normalized_category is not None:
        try:
            category_enum = CategorieDocumentEnum(normalized_category.lower())
        except ValueError:
            return []
        query = query.where(Document.categorie == category_enum)

    years = [row[0] for row in db.execute(query.distinct()).all()]
    return sorted(years, reverse=True)
