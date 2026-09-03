"""API des échéances documentaires et périodes de travail ComptaFlow."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import RoleEnum, StatutDocumentEnum, StatutValidationEnum
from app.models.tva_periode import TvaPeriode
from app.models.user import User
from app.models.workflow_comptable import DocumentAttenduConfiguration, PeriodeTravail
from app.schemas.workflow_comptable import (
    DocumentAttenduCreate, DocumentAttenduOut, PeriodeTravailCreate,
    PeriodeTravailOut, ReouverturePeriode,
)
from app.services import audit_service, precloture_service, workflow_comptable_service

router = APIRouter(prefix="/accounting/workflow", tags=["accounting", "workflow"])
_ROLES = (RoleEnum.ADMIN_CABINET, RoleEnum.EXPERT_COMPTABLE, RoleEnum.CHEF_MISSION)
_ROLES_REOPEN = (RoleEnum.ADMIN_CABINET, RoleEnum.EXPERT_COMPTABLE)


def _company(db: Session, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID) -> None:
    if db.execute(select(Entreprise.id).where(
        Entreprise.id == entreprise_id, Entreprise.cabinet_id == cabinet_id
    )).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Entreprise introuvable dans ce cabinet.")


def _expected_output(db: Session, item: DocumentAttenduConfiguration) -> DocumentAttenduOut:
    documents = db.execute(select(Document).where(
        Document.cabinet_id == item.cabinet_id,
        Document.entreprise_id == item.entreprise_id,
        Document.statut.notin_([StatutDocumentEnum.ERREUR]),
    )).scalars().all()
    received = 0
    for document in documents:
        if document.annee is None:
            continue
        month = document.mois or 1
        period_marker = date(document.annee, month, 1)
        category = getattr(document.categorie, "value", document.categorie)
        if item.periode_debut.replace(day=1) <= period_marker <= item.periode_fin.replace(day=1) and str(category) == item.type_document:
            received += 1
    missing = max(item.nombre_attendu - received, 0) if item.nombre_attendu is not None else None
    complete = item.complete_manuellement or (missing == 0 if missing is not None else False)
    late_days = max((date.today() - item.date_limite_reception).days, 0)
    if complete:
        status = "complet"
        late_days = 0
    elif late_days > 0:
        status = "en_retard"
    elif missing is not None and missing > 0:
        status = "incomplet"
    else:
        status = "en_attente"
    output = DocumentAttenduOut.model_validate(item)
    output.documents_recus = received
    output.documents_manquants = missing
    output.jours_retard = late_days
    output.statut = status
    return output


@router.get("/documents-attendus", response_model=list[DocumentAttenduOut])
def list_expected_documents(
    entreprise_id: uuid.UUID, exercice: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _company(db, current_user.cabinet_id, entreprise_id)
    items = db.execute(select(DocumentAttenduConfiguration).where(
        DocumentAttenduConfiguration.cabinet_id == current_user.cabinet_id,
        DocumentAttenduConfiguration.entreprise_id == entreprise_id,
        DocumentAttenduConfiguration.periode_debut <= date(exercice, 12, 31),
        DocumentAttenduConfiguration.periode_fin >= date(exercice, 1, 1),
    ).order_by(DocumentAttenduConfiguration.date_limite_reception)).scalars().all()
    return [_expected_output(db, item) for item in items]


@router.post("/documents-attendus", response_model=DocumentAttenduOut)
def create_expected_document(
    entreprise_id: uuid.UUID, payload: DocumentAttenduCreate,
    db: Session = Depends(get_db), current_user: User = Depends(require_role(*_ROLES)),
):
    _company(db, current_user.cabinet_id, entreprise_id)
    workflow_comptable_service.verifier_intervalle_modifiable(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        periode_debut=payload.periode_debut,
        periode_fin=payload.periode_fin,
    )
    item = DocumentAttenduConfiguration(
        cabinet_id=current_user.cabinet_id, entreprise_id=entreprise_id,
        **payload.model_dump(),
    )
    db.add(item)
    db.flush()
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.DEADLINE_UPDATED,
        entreprise_id=entreprise_id, resource_type="document_attendu", resource_id=item.id,
        description="Configuration d'un document attendu et de son échéance.",
        apres=payload.model_dump(),
    )
    db.commit(); db.refresh(item)
    return _expected_output(db, item)


@router.patch("/documents-attendus/{item_id}/completer", response_model=DocumentAttenduOut)
def mark_expected_complete(
    item_id: uuid.UUID, entreprise_id: uuid.UUID,
    db: Session = Depends(get_db), current_user: User = Depends(require_role(*_ROLES)),
):
    item = db.execute(select(DocumentAttenduConfiguration).where(
        DocumentAttenduConfiguration.id == item_id,
        DocumentAttenduConfiguration.cabinet_id == current_user.cabinet_id,
        DocumentAttenduConfiguration.entreprise_id == entreprise_id,
    )).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Configuration documentaire introuvable.")
    workflow_comptable_service.verifier_intervalle_modifiable(
        db,
        cabinet_id=item.cabinet_id,
        entreprise_id=item.entreprise_id,
        periode_debut=item.periode_debut,
        periode_fin=item.periode_fin,
    )
    item.complete_manuellement = True
    item.complete_at = datetime.now(timezone.utc)
    item.complete_by = current_user.id
    db.commit(); db.refresh(item)
    return _expected_output(db, item)


@router.get("/periodes", response_model=list[PeriodeTravailOut])
def list_periods(
    entreprise_id: uuid.UUID, exercice: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _company(db, current_user.cabinet_id, entreprise_id)
    return db.execute(select(PeriodeTravail).where(
        PeriodeTravail.cabinet_id == current_user.cabinet_id,
        PeriodeTravail.entreprise_id == entreprise_id,
        PeriodeTravail.exercice == exercice,
    ).order_by(PeriodeTravail.periode_debut)).scalars().all()


@router.post("/periodes/verrouiller", response_model=PeriodeTravailOut)
def lock_period(
    entreprise_id: uuid.UUID, payload: PeriodeTravailCreate,
    db: Session = Depends(get_db), current_user: User = Depends(require_role(*_ROLES)),
):
    _company(db, current_user.cabinet_id, entreprise_id)
    workflow_comptable_service.verifier_intervalle_modifiable(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        periode_debut=payload.periode_debut,
        periode_fin=payload.periode_fin,
    )
    controls = precloture_service.calculer_precloture(
        db, cabinet_id=current_user.cabinet_id, entreprise_id=entreprise_id, exercice=payload.exercice
    )
    blocking = [item for item in controls.anomalies if item.niveau == "bloquant"]
    blocking_titles = [item.titre for item in blocking]

    ready_not_entered = db.execute(select(EcritureComptable.id).where(
        EcritureComptable.cabinet_id == current_user.cabinet_id,
        EcritureComptable.entreprise_id == entreprise_id,
        EcritureComptable.date_piece >= payload.periode_debut,
        EcritureComptable.date_piece <= payload.periode_fin,
        EcritureComptable.statut_validation.in_([
            StatutValidationEnum.PRETE_TOPAZE,
            StatutValidationEnum.VALIDE,  # compatibilité des données historiques
        ]),
        EcritureComptable.saisie_topaze.is_(False),
    )).scalars().all()
    if ready_not_entered:
        blocking_titles.append(
            f"{len(ready_not_entered)} pré-écriture(s) prête(s) ne sont pas encore marquées comme saisies dans Topaze."
        )

    vat_not_declared = db.execute(select(TvaPeriode.id).where(
        TvaPeriode.cabinet_id == current_user.cabinet_id,
        TvaPeriode.entreprise_id == entreprise_id,
        TvaPeriode.date_limite_declaration.is_not(None),
        TvaPeriode.date_limite_declaration <= payload.periode_fin,
        TvaPeriode.statut_declaration != "declaree",
    )).scalars().all()
    if vat_not_declared:
        blocking_titles.append(
            f"{len(vat_not_declared)} déclaration(s) de TVA exigible(s) ne sont pas marquées comme déclarées."
        )

    vat_ready_not_entered = db.execute(select(TvaPeriode.id).where(
        TvaPeriode.cabinet_id == current_user.cabinet_id,
        TvaPeriode.entreprise_id == entreprise_id,
        TvaPeriode.annee == payload.exercice,
        TvaPeriode.statut_comptable == "prete_topaze",
        TvaPeriode.topaze_entered_at.is_(None),
    )).scalars().all()
    if vat_ready_not_entered:
        blocking_titles.append(
            f"{len(vat_ready_not_entered)} centralisation(s) TVA prête(s) ne sont pas encore saisies dans Topaze."
        )

    if blocking_titles:
        raise HTTPException(status_code=422, detail={
            "message": "La période ne peut pas être verrouillée tant que des blocages subsistent.",
            "blocages": list(dict.fromkeys(blocking_titles)),
        })
    period = db.execute(select(PeriodeTravail).where(
        PeriodeTravail.cabinet_id == current_user.cabinet_id,
        PeriodeTravail.entreprise_id == entreprise_id,
        PeriodeTravail.periode_debut == payload.periode_debut,
        PeriodeTravail.periode_fin == payload.periode_fin,
    )).scalar_one_or_none()
    if period is None:
        period = PeriodeTravail(cabinet_id=current_user.cabinet_id, entreprise_id=entreprise_id, **payload.model_dump())
        db.add(period)
    else:
        period.date_limite_saisie_topaze = payload.date_limite_saisie_topaze
    period.verrouillee = True
    period.locked_at = datetime.now(timezone.utc)
    period.locked_by = current_user.id
    db.flush()
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.PERIOD_LOCKED,
        entreprise_id=entreprise_id, resource_type="periode_travail", resource_id=period.id,
        description="Verrouillage d'une période de travail ComptaFlow.", apres=payload.model_dump(),
    )
    db.commit(); db.refresh(period)
    return period


@router.post("/periodes/{period_id}/reouvrir", response_model=PeriodeTravailOut)
def reopen_period(
    period_id: uuid.UUID, entreprise_id: uuid.UUID, payload: ReouverturePeriode,
    db: Session = Depends(get_db), current_user: User = Depends(require_role(*_ROLES_REOPEN)),
):
    period = db.execute(select(PeriodeTravail).where(
        PeriodeTravail.id == period_id,
        PeriodeTravail.cabinet_id == current_user.cabinet_id,
        PeriodeTravail.entreprise_id == entreprise_id,
    )).scalar_one_or_none()
    if period is None:
        raise HTTPException(status_code=404, detail="Période introuvable.")
    period.verrouillee = False
    period.reopened_at = datetime.now(timezone.utc)
    period.reopened_by = current_user.id
    period.reopen_reason = payload.justification
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.PERIOD_REOPENED,
        entreprise_id=entreprise_id, resource_type="periode_travail", resource_id=period.id,
        description="Réouverture justifiée d'une période ComptaFlow.",
        avant={"verrouillee": True}, apres={"verrouillee": False, "justification": payload.justification},
    )
    db.commit(); db.refresh(period)
    return period
