"""API en lecture seule du journal d'audit, réservée aux administrateurs."""

from __future__ import annotations

import math
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_role
from app.models.audit_log import AuditLog
from app.models.entreprise import Entreprise
from app.models.enums import RoleEnum
from app.models.user import User
from app.schemas.audit import (
    AuditEventOut,
    AuditFilterOptionsOut,
    AuditPageOut,
    AuditResourceLink,
)


router = APIRouter(prefix="/audit", tags=["audit"])
_ADMIN_ROLES = (RoleEnum.ADMIN_CABINET, RoleEnum.SUPER_ADMIN)


def _legacy(log: AuditLog, key: str):
    details = log.details if isinstance(log.details, dict) else {}
    return details.get(key)


def _links(log: AuditLog) -> list[AuditResourceLink]:
    resource_type = log.resource_type or _legacy(log, "resource_type")
    resource_id = log.resource_id or _legacy(log, "resource_id")
    if not resource_type or not resource_id:
        return []
    try:
        parsed_id = uuid.UUID(str(resource_id))
    except (TypeError, ValueError):
        return []
    routes = {
        "document": f"/documents/{parsed_id}",
        "ecriture": f"/registers?entry_id={parsed_id}",
        "accounting_entry": f"/registers?entry_id={parsed_id}",
        "mouvement_bancaire": f"/banque?movement_id={parsed_id}",
        "tache": f"/rappels?task_id={parsed_id}",
        "user": f"/admin/utilisateurs?user_id={parsed_id}",
    }
    route = routes.get(str(resource_type))
    if route is None:
        return []
    return [AuditResourceLink(
        label="Ouvrir la ressource", resource_type=str(resource_type),
        resource_id=parsed_id, route=route,
    )]


def _serialize(log: AuditLog, entreprise_nom: str | None = None) -> AuditEventOut:
    legacy_before = _legacy(log, "avant")
    legacy_after = _legacy(log, "apres")
    return AuditEventOut(
        id=log.id, cabinet_id=log.cabinet_id, entreprise_id=log.entreprise_id,
        entreprise_nom=entreprise_nom, user_id=log.user_id,
        actor_name=log.actor_name, actor_email=log.actor_email,
        actor_role=log.actor_role, actor_type=log.actor_type or "user",
        action=log.action, module=log.module or "systeme",
        resource_type=log.resource_type or _legacy(log, "resource_type"),
        resource_id=log.resource_id,
        description=log.description, status=log.status or "success",
        event_at=log.event_at or log.created_at,
        correlation_id=log.correlation_id, item_count=log.item_count,
        resource_ids=log.resource_ids or [],
        old_values=log.old_values if log.old_values is not None else legacy_before,
        new_values=log.new_values if log.new_values is not None else legacy_after,
        metadata=log.event_metadata, links=_links(log),
    )


def _base_query(current_user: User):
    # Le modèle actuel rattache aussi le SUPER_ADMIN à un cabinet. Il conserve
    # donc le même scope par défaut : aucun paramètre client ne peut l'élargir.
    return select(AuditLog, Entreprise.nom).outerjoin(
        Entreprise,
        (Entreprise.id == AuditLog.entreprise_id)
        & (Entreprise.cabinet_id == AuditLog.cabinet_id),
    ).where(AuditLog.cabinet_id == current_user.cabinet_id)


@router.get("/options", response_model=AuditFilterOptionsOut)
def get_filter_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    def distinct(column):
        return [value for value in db.execute(
            select(column).where(
                AuditLog.cabinet_id == current_user.cabinet_id,
                column.is_not(None),
            ).distinct().order_by(column)
        ).scalars().all() if value]
    return AuditFilterOptionsOut(
        actions=distinct(AuditLog.action), modules=distinct(AuditLog.module),
        roles=distinct(AuditLog.actor_role), statuses=distinct(AuditLog.status),
    )


@router.get("", response_model=AuditPageOut)
def list_audit_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    user_id: uuid.UUID | None = None,
    role: str | None = Query(None, max_length=50),
    entreprise_id: uuid.UUID | None = None,
    module: str | None = Query(None, max_length=50),
    action: str | None = Query(None, max_length=100),
    resource_type: str | None = Query(None, max_length=50),
    status: str | None = Query(None, pattern="^(success|failed)$"),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    if entreprise_id is not None:
        allowed = db.execute(select(Entreprise.id).where(
            Entreprise.id == entreprise_id,
            Entreprise.cabinet_id == current_user.cabinet_id,
        )).scalar_one_or_none()
        if allowed is None:
            raise HTTPException(status_code=404, detail="Entreprise introuvable dans ce cabinet.")
    if user_id is not None:
        allowed = db.execute(select(User.id).where(
            User.id == user_id, User.cabinet_id == current_user.cabinet_id,
        )).scalar_one_or_none()
        if allowed is None:
            raise HTTPException(status_code=404, detail="Utilisateur introuvable dans ce cabinet.")

    query = _base_query(current_user)
    filters = []
    for column, value in (
        (AuditLog.user_id, user_id), (AuditLog.actor_role, role),
        (AuditLog.entreprise_id, entreprise_id), (AuditLog.module, module),
        (AuditLog.action, action), (AuditLog.resource_type, resource_type),
        (AuditLog.status, status),
    ):
        if value is not None:
            filters.append(column == value)
    if date_from is not None:
        filters.append(AuditLog.event_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.event_at <= date_to)
    if search and search.strip():
        motif = f"%{search.strip()}%"
        filters.append(or_(
            AuditLog.actor_email.ilike(motif), AuditLog.actor_name.ilike(motif),
            AuditLog.description.ilike(motif), AuditLog.action.ilike(motif),
            cast(AuditLog.resource_id, String).ilike(motif),
            cast(AuditLog.event_metadata, String).ilike(motif),
        ))
    query = query.where(*filters)

    count_query = select(func.count()).select_from(query.subquery())
    total = int(db.execute(count_query).scalar_one())
    order = AuditLog.event_at.asc() if sort == "asc" else AuditLog.event_at.desc()
    rows = db.execute(
        query.order_by(order).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return AuditPageOut(
        items=[_serialize(log, company_name) for log, company_name in rows],
        page=page, page_size=page_size, total=total,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/{event_id}", response_model=AuditEventOut)
def get_audit_event(
    event_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ADMIN_ROLES)),
):
    row = db.execute(_base_query(current_user).where(AuditLog.id == event_id)).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Événement d'audit introuvable.")
    return _serialize(row[0], row[1])
