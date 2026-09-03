"""Messagerie interne et transformation contrôlée d'un message en tâche."""

from __future__ import annotations

import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.cabinet_message import CabinetMessage
from app.models.enums import RoleEnum
from app.models.tache import Tache
from app.models.user import User
from app.schemas.message import (
    AccessRenewalRequest,
    AccessRenewalResponse,
    MessageContactOut,
    MessageCreate,
    MessageOut,
    MessageTaskCreate,
)
from app.schemas.tache import TacheOut
from app.services import audit_service
from app.services.tache_service import est_en_retard


router = APIRouter(prefix="/messages", tags=["messages"])
ADMIN_ROLES = {RoleEnum.ADMIN_CABINET, RoleEnum.SUPER_ADMIN}
_ACCESS_WINDOW = timedelta(minutes=15)
_ACCESS_LIMIT = 3
_access_attempts: dict[str, deque[datetime]] = defaultdict(deque)


def _is_admin(user: User) -> bool:
    return user.role in ADMIN_ROLES


def _name(user: User | None) -> str | None:
    if user is None:
        return None
    return " ".join(part for part in (user.prenom, user.nom) if part).strip() or user.email


def _rate_limit_access(request: Request, email: str) -> None:
    now = datetime.now(timezone.utc)
    key = f"{request.client.host if request.client else 'unknown'}:{email.lower()}"
    attempts = _access_attempts[key]
    while attempts and now - attempts[0] > _ACCESS_WINDOW:
        attempts.popleft()
    if len(attempts) >= _ACCESS_LIMIT:
        raise HTTPException(status_code=429, detail="Trop de demandes. Réessayez dans quelques minutes.")
    attempts.append(now)


def _contact(db: Session, current_user: User, contact_id: uuid.UUID) -> User:
    if contact_id == current_user.id:
        raise HTTPException(status_code=400, detail="Vous ne pouvez pas vous écrire à vous-même.")
    contact = db.execute(select(User).where(
        User.id == contact_id,
        User.cabinet_id == current_user.cabinet_id,
    )).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact introuvable dans votre cabinet.")
    if not _is_admin(current_user) and contact.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Les utilisateurs peuvent contacter uniquement les administrateurs du cabinet.")
    return contact


def _message_out(message: CabinetMessage, users: dict[uuid.UUID, User], current_user: User) -> MessageOut:
    return MessageOut(
        id=message.id,
        sender_id=message.sender_id,
        recipient_id=message.recipient_id,
        sender_name=_name(users.get(message.sender_id)) if message.sender_id else None,
        recipient_name=_name(users.get(message.recipient_id)) if message.recipient_id else None,
        contenu=message.contenu,
        message_type=message.message_type,
        read_at=message.read_at,
        task_id=message.task_id,
        created_at=message.created_at,
        is_mine=message.sender_id == current_user.id,
    )


@router.post("/access-request", response_model=AccessRenewalResponse, status_code=status.HTTP_202_ACCEPTED)
def request_access_renewal(
    payload: AccessRenewalRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Crée une demande sans révéler si l'adresse existe dans ComptaFlow."""
    normalized_email = str(payload.email).strip().lower()
    _rate_limit_access(request, normalized_email)
    generic = AccessRenewalResponse(
        message="Si cette adresse appartient à un compte, l’administrateur du cabinet a reçu votre demande.",
    )
    requester = db.execute(select(User).where(func.lower(User.email) == normalized_email)).scalar_one_or_none()
    if requester is None:
        return generic
    administrator = db.execute(select(User).where(
        User.cabinet_id == requester.cabinet_id,
        User.id != requester.id,
        User.role.in_(ADMIN_ROLES),
        User.is_active.is_(True),
    ).order_by(User.role, User.nom, User.prenom)).scalars().first()
    if administrator is None:
        return generic

    cutoff = datetime.now(timezone.utc) - _ACCESS_WINDOW
    duplicate = db.execute(select(CabinetMessage.id).where(
        CabinetMessage.cabinet_id == requester.cabinet_id,
        CabinetMessage.sender_id == requester.id,
        CabinetMessage.recipient_id == administrator.id,
        CabinetMessage.message_type == "access_request",
        CabinetMessage.created_at >= cutoff,
    )).scalar_one_or_none()
    if duplicate is not None:
        return generic

    extra = payload.message.strip() if payload.message else ""
    content = "Demande de renouvellement d’accès à ComptaFlow."
    if extra:
        content = f"{content}\n{extra}"
    message = CabinetMessage(
        cabinet_id=requester.cabinet_id,
        sender_id=requester.id,
        recipient_id=administrator.id,
        contenu=content,
        message_type="access_request",
    )
    db.add(message)
    db.flush()
    audit_service.enregistrer(
        db,
        user=requester,
        action=audit_service.AuditAction.ACCESS_RENEWAL_REQUESTED,
        resource_type="message",
        resource_id=message.id,
        description="Demande de renouvellement d’accès envoyée à un administrateur.",
        metadata={"recipient_id": administrator.id},
    )
    db.commit()
    return generic


@router.get("/contacts", response_model=list[MessageContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(User).where(
        User.cabinet_id == current_user.cabinet_id,
        User.id != current_user.id,
    )
    if not _is_admin(current_user):
        query = query.where(User.role.in_(ADMIN_ROLES), User.is_active.is_(True))
    contacts = db.execute(query.order_by(User.is_active.desc(), User.nom, User.prenom)).scalars().all()
    unread = dict(db.execute(select(
        CabinetMessage.sender_id,
        func.count(CabinetMessage.id),
    ).where(
        CabinetMessage.cabinet_id == current_user.cabinet_id,
        CabinetMessage.recipient_id == current_user.id,
        CabinetMessage.read_at.is_(None),
    ).group_by(CabinetMessage.sender_id)).all())
    return [MessageContactOut(
        id=contact.id,
        nom_complet=_name(contact) or contact.email,
        email=contact.email,
        role=contact.role.value,
        is_active=contact.is_active,
        unread_count=int(unread.get(contact.id, 0)),
    ) for contact in contacts]


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = db.execute(select(func.count(CabinetMessage.id)).where(
        CabinetMessage.cabinet_id == current_user.cabinet_id,
        CabinetMessage.recipient_id == current_user.id,
        CabinetMessage.read_at.is_(None),
    )).scalar_one()
    return {"count": count}


@router.get("/{contact_id}", response_model=list[MessageOut])
def conversation(
    contact_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contact = _contact(db, current_user, contact_id)
    messages = db.execute(select(CabinetMessage).where(
        CabinetMessage.cabinet_id == current_user.cabinet_id,
        or_(
            (CabinetMessage.sender_id == current_user.id) & (CabinetMessage.recipient_id == contact.id),
            (CabinetMessage.sender_id == contact.id) & (CabinetMessage.recipient_id == current_user.id),
        ),
    ).order_by(CabinetMessage.created_at.asc()).limit(300)).scalars().all()
    now = datetime.now(timezone.utc)
    changed = False
    for message in messages:
        if message.recipient_id == current_user.id and message.read_at is None:
            message.read_at = now
            changed = True
    if changed:
        db.commit()
    return [_message_out(message, {current_user.id: current_user, contact.id: contact}, current_user) for message in messages]


@router.post("", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    payload: MessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    recipient = _contact(db, current_user, payload.recipient_id)
    if not recipient.is_active:
        raise HTTPException(status_code=409, detail="Ce compte est désactivé. Le message ne peut pas être remis.")
    message = CabinetMessage(
        cabinet_id=current_user.cabinet_id,
        sender_id=current_user.id,
        recipient_id=recipient.id,
        contenu=payload.contenu.strip(),
        message_type="chat",
    )
    db.add(message)
    db.flush()
    audit_service.enregistrer(
        db,
        user=current_user,
        action=audit_service.AuditAction.MESSAGE_SENT,
        resource_type="message",
        resource_id=message.id,
        description="Message interne envoyé.",
        metadata={"recipient_id": recipient.id, "message_type": message.message_type},
    )
    db.commit()
    db.refresh(message)
    return _message_out(message, {current_user.id: current_user, recipient.id: recipient}, current_user)


@router.post("/{message_id}/task", response_model=TacheOut, status_code=status.HTTP_201_CREATED)
def plan_message_as_task(
    message_id: uuid.UUID,
    payload: MessageTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Seul un administrateur peut planifier un message.")
    message = db.execute(select(CabinetMessage).where(
        CabinetMessage.id == message_id,
        CabinetMessage.cabinet_id == current_user.cabinet_id,
        or_(CabinetMessage.sender_id == current_user.id, CabinetMessage.recipient_id == current_user.id),
    )).scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=404, detail="Message introuvable dans votre cabinet.")
    if message.task_id is not None:
        raise HTTPException(status_code=409, detail="Ce message est déjà planifié comme tâche.")
    assignee_id = message.recipient_id if message.sender_id == current_user.id else current_user.id
    if assignee_id is None:
        raise HTTPException(status_code=400, detail="Impossible de déterminer le responsable de la tâche.")
    assignee = db.execute(select(User).where(
        User.id == assignee_id,
        User.cabinet_id == current_user.cabinet_id,
    )).scalar_one_or_none()
    if assignee is None:
        raise HTTPException(status_code=404, detail="Responsable de la tâche introuvable.")
    default_title = " ".join(message.contenu.split())[:120]
    task = Tache(
        cabinet_id=current_user.cabinet_id,
        cree_par=current_user.id,
        assignee_a=assignee.id,
        titre=(payload.titre or default_title or "Action issue de la messagerie").strip(),
        description=f"Tâche créée depuis la messagerie :\n{message.contenu}",
        date_echeance=payload.date_echeance,
        heure_echeance=payload.heure_echeance,
        priorite=payload.priorite,
        recurrence=payload.recurrence,
    )
    db.add(task)
    db.flush()
    message.task_id = task.id
    audit_service.enregistrer(
        db,
        user=current_user,
        action=audit_service.AuditAction.MESSAGE_PLANNED_AS_TASK,
        resource_type="tache",
        resource_id=task.id,
        description="Message converti en tâche planifiée.",
        apres={
            "message_id": message.id,
            "assignee_a": task.assignee_a,
            "date_echeance": task.date_echeance,
            "heure_echeance": task.heure_echeance,
        },
    )
    db.commit()
    db.refresh(task)
    output = TacheOut.model_validate(task)
    output.assignee_nom = _name(assignee)
    output.est_en_retard = est_en_retard(task)
    return output
