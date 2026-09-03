"""Indicateurs du tableau de bord, filtrables par mois (YYYY-MM)."""

from datetime import date
from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import (
    StatutDocumentEnum,
    StatutValidationEnum,
    TypeEcritureEnum,
)
from app.models.user import User
from app.schemas.dashboard import (
    DashboardOut,
    DocumentsParStatut,
    EcrituresParStatutValidation,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _parse_period(period: str | None) -> tuple[int, int] | None:
    if not period:
        return None
    try:
        year_text, month_text = period.split("-", maxsplit=1)
        year = int(year_text)
        month = int(month_text)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(
            status_code=422,
            detail="La période doit respecter le format YYYY-MM.",
        ) from exc

    if month < 1 or month > 12:
        raise HTTPException(status_code=422, detail="Mois invalide.")
    return year, month


def _document_period_clause(period: tuple[int, int] | None):
    if period is None:
        return None
    year, month = period
    return or_(
        and_(Document.annee == year, Document.mois == month),
        and_(
            Document.annee.is_(None),
            extract_year(Document.created_at) == year,
            extract_month(Document.created_at) == month,
        ),
    )


def extract_year(column):
    return func.extract("year", column)


def extract_month(column):
    return func.extract("month", column)


def _entry_period_clause(period: tuple[int, int] | None):
    if period is None:
        return None
    year, month = period
    return or_(
        and_(
            EcritureComptable.date_piece.is_not(None),
            extract_year(EcritureComptable.date_piece) == year,
            extract_month(EcritureComptable.date_piece) == month,
        ),
        and_(
            EcritureComptable.date_piece.is_(None),
            extract_year(EcritureComptable.created_at) == year,
            extract_month(EcritureComptable.created_at) == month,
        ),
    )


def _count_documents(
    db: Session,
    cabinet_id,
    period: tuple[int, int] | None,
    entreprise_id: uuid.UUID | None = None,
) -> DocumentsParStatut:
    query = select(Document.statut, func.count(Document.id)).where(
        Document.cabinet_id == cabinet_id
    )
    if entreprise_id is not None:
        query = query.where(Document.entreprise_id == entreprise_id)
    period_clause = _document_period_clause(period)
    if period_clause is not None:
        query = query.where(period_clause)

    rows = db.execute(query.group_by(Document.statut)).all()
    counters = {status.value: 0 for status in StatutDocumentEnum}
    for status, count in rows:
        counters[status.value] = int(count)

    return DocumentsParStatut(**counters)


def _count_entries(
    db: Session,
    cabinet_id,
    period: tuple[int, int] | None,
    entreprise_id: uuid.UUID | None = None,
) -> EcrituresParStatutValidation:
    query = select(
        EcritureComptable.statut_validation,
        func.count(EcritureComptable.id),
    ).where(EcritureComptable.cabinet_id == cabinet_id)
    if entreprise_id is not None:
        query = query.where(EcritureComptable.entreprise_id == entreprise_id)
    period_clause = _entry_period_clause(period)
    if period_clause is not None:
        query = query.where(period_clause)

    rows = db.execute(query.group_by(EcritureComptable.statut_validation)).all()
    counters = {status.value: 0 for status in StatutValidationEnum}
    for status, count in rows:
        counters[status.value] = int(count)

    return EcrituresParStatutValidation(**counters)


def _calculate_tax(
    db: Session,
    cabinet_id,
    period: tuple[int, int] | None,
    entreprise_id: uuid.UUID | None = None,
) -> tuple[Decimal, Decimal, Decimal]:
    def total_for(entry_type: TypeEcritureEnum) -> Decimal:
        query = select(
            func.coalesce(func.sum(EcritureComptable.montant_tva), 0)
        ).where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.statut_validation.in_([
                StatutValidationEnum.PRETE_TOPAZE,
                StatutValidationEnum.SAISIE_TOPAZE,
                # Compatibilité avec les données antérieures au workflow
                # de pré-comptabilité actuel.
                StatutValidationEnum.VALIDE,
            ]),
            EcritureComptable.type_ecriture == entry_type,
        )
        period_clause = _entry_period_clause(period)
        if entreprise_id is not None:
            query = query.where(EcritureComptable.entreprise_id == entreprise_id)
        if period_clause is not None:
            query = query.where(period_clause)
        return Decimal(db.execute(query).scalar_one())

    collected = total_for(TypeEcritureEnum.VENTE)
    deductible = total_for(TypeEcritureEnum.ACHAT)
    return collected, deductible, collected - deductible


@router.get("", response_model=DashboardOut)
def get_dashboard(
    period: str | None = Query(default=None),
    entreprise_id: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    parsed_period = _parse_period(period)
    cabinet_id = current_user.cabinet_id

    if entreprise_id is not None:
        entreprise = db.execute(select(Entreprise).where(
            Entreprise.id == entreprise_id,
            Entreprise.cabinet_id == cabinet_id,
            Entreprise.is_active.is_(True),
        )).scalar_one_or_none()
        if entreprise is None:
            raise HTTPException(status_code=404, detail="Entreprise introuvable dans votre cabinet.")

    document_counts = _count_documents(db, cabinet_id, parsed_period, entreprise_id)
    entry_counts = _count_entries(db, cabinet_id, parsed_period, entreprise_id)
    collected, deductible, net = _calculate_tax(db, cabinet_id, parsed_period, entreprise_id)

    company_count = 1 if entreprise_id is not None else db.execute(
        select(func.count(Entreprise.id)).where(Entreprise.cabinet_id == cabinet_id)
    ).scalar_one()

    return DashboardOut(
        total_documents=sum(document_counts.model_dump().values()),
        documents_par_statut=document_counts,
        total_ecritures=sum(entry_counts.model_dump().values()),
        ecritures_par_statut=entry_counts,
        tva_collectee=collected,
        tva_deductible=deductible,
        tva_nette=net,
        total_entreprises=int(company_count),
    )
