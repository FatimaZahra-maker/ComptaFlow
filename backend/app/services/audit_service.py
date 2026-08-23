"""Écriture minimale et transactionnelle de la piste d'audit existante."""

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


def enregistrer(
    db: Session,
    *,
    user: User,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID,
    avant: dict[str, Any] | None = None,
    apres: dict[str, Any] | None = None,
) -> AuditLog:
    journal = AuditLog(
        cabinet_id=user.cabinet_id,
        user_id=user.id,
        action=action,
        details={
            "resource_type": resource_type,
            "resource_id": str(resource_id),
            "avant": avant,
            "apres": apres,
        },
    )
    db.add(journal)
    return journal
