"""API TVA V2, complémentaire à la synthèse comptable V1."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.entreprise import Entreprise
from app.models.document import Document
from app.models.enums import RoleEnum
from app.models.tva_periode import TvaConfigurationEntreprise, TvaPeriode, TvaRegularisation
from app.models.user import User
from app.schemas.tva import (
    TvaConfigurationOut,
    TvaConfigurationUpdate,
    TvaPeriodeOut,
    TvaPeriodesAnneeOut,
    TvaRegularisationCreate,
    TvaRegularisationOut,
    TvaDeclarationCreate,
    TvaDeadlineUpdate,
    TvaTopazeMark,
)
from app.services import audit_service, tva_comptable_service, workflow_comptable_service

router = APIRouter(prefix="/accounting/tva-v2", tags=["accounting", "tva-v2"])
_ROLES_VALIDATION = (
    RoleEnum.ADMIN_CABINET,
    RoleEnum.EXPERT_COMPTABLE,
    RoleEnum.CHEF_MISSION,
)


def _ensure_company(db: Session, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID) -> None:
    exists = db.execute(
        select(Entreprise.id).where(
            Entreprise.id == entreprise_id,
            Entreprise.cabinet_id == cabinet_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Entreprise introuvable dans ce cabinet.")


def _get_period(
    db: Session,
    period_id: uuid.UUID,
    user: User,
    entreprise_id: uuid.UUID,
) -> TvaPeriode:
    period = db.execute(
        select(TvaPeriode).where(
            TvaPeriode.id == period_id,
            TvaPeriode.cabinet_id == user.cabinet_id,
            TvaPeriode.entreprise_id == entreprise_id,
        )
    ).scalar_one_or_none()
    if period is None:
        raise HTTPException(status_code=404, detail="Période TVA introuvable.")
    return period


def _verifier_periode_tva_modifiable(db: Session, period: TvaPeriode) -> None:
    workflow_comptable_service.verifier_date_modifiable(
        db,
        cabinet_id=period.cabinet_id,
        entreprise_id=period.entreprise_id,
        target_date=date(period.annee, period.mois, 1),
    )


@router.post("/recalculer", response_model=TvaPeriodesAnneeOut)
def recalculate_periods(
    entreprise_id: uuid.UUID,
    annee: int = Query(ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_company(db, current_user.cabinet_id, entreprise_id)
    workflow_comptable_service.verifier_intervalle_modifiable(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        periode_debut=date(annee, 1, 1),
        periode_fin=date(annee, 12, 31),
    )
    periods = tva_comptable_service.recalculer_periodes_tva(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        annee=annee,
    )
    configuration = db.execute(
        select(TvaConfigurationEntreprise).where(
            TvaConfigurationEntreprise.cabinet_id == current_user.cabinet_id,
            TvaConfigurationEntreprise.entreprise_id == entreprise_id,
        )
    ).scalar_one_or_none()
    db.commit()
    return TvaPeriodesAnneeOut(
        entreprise_id=entreprise_id,
        annee=annee,
        periodes=[TvaPeriodeOut.model_validate(item) for item in periods],
        configuration=(TvaConfigurationOut.model_validate(configuration) if configuration else None),
    )


@router.put("/configuration/{entreprise_id}", response_model=TvaConfigurationOut)
def update_configuration(
    entreprise_id: uuid.UUID,
    payload: TvaConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    _ensure_company(db, current_user.cabinet_id, entreprise_id)
    config = db.execute(
        select(TvaConfigurationEntreprise).where(
            TvaConfigurationEntreprise.cabinet_id == current_user.cabinet_id,
            TvaConfigurationEntreprise.entreprise_id == entreprise_id,
        )
    ).scalar_one_or_none()
    account_fields = (
        "compte_tva_collectee",
        "compte_tva_recuperable_charges",
        "compte_tva_recuperable_immobilisations",
        "compte_tva_a_payer",
        "compte_credit_tva",
    )
    before = (
        {name: getattr(config, name) for name in account_fields}
        if config is not None
        else None
    )
    if config is None:
        config = TvaConfigurationEntreprise(
            cabinet_id=current_user.cabinet_id,
            entreprise_id=entreprise_id,
        )
        db.add(config)
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(config, name, value)
    db.flush()
    audit_service.enregistrer(
        db,
        user=current_user,
        action=audit_service.AuditAction.VAT_CONFIGURATION_UPDATED,
        entreprise_id=entreprise_id,
        resource_type="tva_configuration",
        resource_id=config.id,
        description="Mise à jour de la configuration TVA de l'entreprise.",
        avant=before,
        apres={name: getattr(config, name) for name in account_fields},
    )
    db.commit()
    db.refresh(config)
    return config


@router.post("/periodes/{period_id}/regularisations", response_model=TvaRegularisationOut)
def create_adjustment(
    period_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    payload: TvaRegularisationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    period = _get_period(db, period_id, current_user, entreprise_id)
    _verifier_periode_tva_modifiable(db, period)
    workflow_comptable_service.verifier_date_modifiable(
        db,
        cabinet_id=period.cabinet_id,
        entreprise_id=period.entreprise_id,
        target_date=payload.date_regularisation,
    )
    if period.statut == "cloturee":
        raise HTTPException(status_code=422, detail="Période TVA clôturée.")
    adjustment = TvaRegularisation(
        cabinet_id=current_user.cabinet_id,
        entreprise_id=period.entreprise_id,
        periode_id=period.id,
        nature=payload.nature,
        montant_signe=payload.montant_signe,
        motif=payload.motif,
        date_regularisation=payload.date_regularisation,
        statut="validee" if payload.valider else "brouillon",
        source=payload.source,
        created_by=current_user.id,
    )
    db.add(adjustment)
    db.commit()
    db.refresh(adjustment)
    return adjustment


@router.post("/periodes/{period_id}/valider", response_model=TvaPeriodeOut)
def validate_period(
    period_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    period = _get_period(db, period_id, current_user, entreprise_id)
    _verifier_periode_tva_modifiable(db, period)
    try:
        tva_comptable_service.valider_periode_tva(
            db,
            periode=period,
            cabinet_id=current_user.cabinet_id,
            entreprise_id=period.entreprise_id,
            user_id=current_user.id,
        )
        db.commit()
        db.refresh(period)
        return period
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/periodes/{period_id}/saisie-topaze", response_model=TvaPeriodeOut)
def mark_period_topaze(
    period_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    payload: TvaTopazeMark,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    period = _get_period(db, period_id, current_user, entreprise_id)
    _verifier_periode_tva_modifiable(db, period)
    if payload.saisie and period.statut_comptable not in {"prete_topaze", "saisie_topaze"}:
        raise HTTPException(status_code=422, detail="La centralisation TVA doit être contrôlée avant la saisie Topaze.")
    before = period.statut_comptable
    if payload.saisie:
        period.statut_comptable = "saisie_topaze"
        period.topaze_entered_at = datetime.now(timezone.utc)
        period.topaze_entered_by = current_user.id
        period.topaze_batch_reference = payload.reference_lot.strip() if payload.reference_lot else None
    else:
        period.statut_comptable = "prete_topaze"
        period.topaze_entered_at = None
        period.topaze_entered_by = None
        period.topaze_batch_reference = None
    audit_service.enregistrer(
        db,
        user=current_user,
        action=audit_service.AuditAction.ENTRY_MARKED_TOPAZE,
        entreprise_id=entreprise_id,
        resource_type="tva_periode",
        resource_id=period.id,
        description="Modification du statut Topaze de la centralisation TVA.",
        avant={"statut_comptable": before},
        apres={
            "statut_comptable": period.statut_comptable,
            "reference_lot": period.topaze_batch_reference,
        },
    )
    db.commit()
    db.refresh(period)
    return period


@router.patch("/periodes/{period_id}/echeance", response_model=TvaPeriodeOut)
def update_declaration_deadline(
    period_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    payload: TvaDeadlineUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    period = _get_period(db, period_id, current_user, entreprise_id)
    _verifier_periode_tva_modifiable(db, period)
    before = period.date_limite_declaration
    period.date_limite_declaration = payload.date_limite
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.DEADLINE_UPDATED,
        entreprise_id=period.entreprise_id, resource_type="tva_periode", resource_id=period.id,
        description="Modification de l'échéance de déclaration TVA.",
        avant={"date_limite_declaration": before}, apres={"date_limite_declaration": payload.date_limite},
    )
    db.commit()
    db.refresh(period)
    return period


@router.post("/periodes/{period_id}/declarer", response_model=TvaPeriodeOut)
def mark_period_declared(
    period_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    payload: TvaDeclarationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    period = _get_period(db, period_id, current_user, entreprise_id)
    _verifier_periode_tva_modifiable(db, period)
    if period.a_verifier or period.statut_comptable == "a_verifier":
        raise HTTPException(status_code=422, detail="Les anomalies TVA doivent être résolues avant la déclaration.")
    receipt_path = None
    if payload.justificatif_document_id is not None:
        proof = db.execute(select(Document).where(
            Document.id == payload.justificatif_document_id,
            Document.cabinet_id == current_user.cabinet_id,
            Document.entreprise_id == entreprise_id,
        )).scalar_one_or_none()
        if proof is None:
            raise HTTPException(status_code=404, detail="Justificatif introuvable dans cette entreprise.")
        receipt_path = proof.chemin_stockage
    before = period.statut_declaration
    period.statut_declaration = "declaree"
    period.declared_at = datetime.now(timezone.utc)
    period.declared_by = current_user.id
    period.declaration_date_reelle = payload.date_declaration
    period.declaration_reference = payload.reference.strip() if payload.reference else None
    period.declaration_receipt_path = receipt_path
    period.declaration_note = payload.note.strip() if payload.note else None
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.VAT_DECLARED,
        entreprise_id=period.entreprise_id, resource_type="tva_periode", resource_id=period.id,
        description="Période TVA marquée manuellement comme déclarée.",
        avant={"statut_declaration": before},
        apres={"statut_declaration": "declaree", "date_declaration": payload.date_declaration, "reference": period.declaration_reference, "justificatif": bool(receipt_path)},
    )
    db.commit()
    db.refresh(period)
    output = TvaPeriodeOut.model_validate(period)
    output.justificatif_disponible = bool(period.declaration_receipt_path)
    return output
