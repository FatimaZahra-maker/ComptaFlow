"""Écriture minimale et transactionnelle de la piste d'audit existante."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User


class AuditAction:
    LOGIN_SUCCEEDED = "LOGIN_SUCCEEDED"
    LOGIN_FAILED = "LOGIN_FAILED"
    USER_CREATED = "USER_CREATED"
    USER_UPDATED = "USER_UPDATED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    DOCUMENTS_UPLOADED = "DOCUMENTS_UPLOADED"
    DOCUMENT_OPENED = "DOCUMENT_OPENED"
    DOCUMENT_UPDATED = "DOCUMENT_UPDATED"
    DOCUMENT_REPROCESSED = "DOCUMENT_REPROCESSED"
    DOCUMENT_VALIDATED = "DOCUMENT_VALIDATED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"
    DOCUMENT_MARKED_TOPAZE = "DOCUMENT_MARKED_TOPAZE"
    ENTRY_UPDATED = "ENTRY_UPDATED"
    ENTRY_VALIDATED = "ENTRY_VALIDATED"
    ENTRY_REJECTED = "ENTRY_REJECTED"
    ENTRY_MARKED_TOPAZE = "ENTRY_MARKED_TOPAZE"
    ENTRY_READY_FOR_TOPAZE = "ENTRY_READY_FOR_TOPAZE"
    ENTRY_REQUIRES_REVIEW = "ENTRY_REQUIRES_REVIEW"
    VAT_DECLARED = "VAT_DECLARED"
    VAT_CONFIGURATION_UPDATED = "VAT_CONFIGURATION_UPDATED"
    PERIOD_LOCKED = "PERIOD_LOCKED"
    PERIOD_REOPENED = "PERIOD_REOPENED"
    DEADLINE_UPDATED = "DEADLINE_UPDATED"
    BANK_MOVEMENT_UPDATED = "BANK_MOVEMENT_UPDATED"
    BANK_RECONCILIATION_CONFIRMED = "BANK_RECONCILIATION_CONFIRMED"
    BANK_RECONCILIATION_CANCELLED = "BANK_RECONCILIATION_CANCELLED"
    BANK_ALLOCATIONS_CONFIRMED = "BANK_ALLOCATIONS_CONFIRMED"
    ACCOUNT_PLAN_IMPORTED = "ACCOUNT_PLAN_IMPORTED"
    ACCOUNT_CREATED = "ACCOUNT_CREATED"
    ACCOUNT_UPDATED = "ACCOUNT_UPDATED"
    ACCOUNT_DEACTIVATED = "ACCOUNT_DEACTIVATED"
    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_DELETED = "TASK_DELETED"
    EXPORT_GENERATED = "EXPORT_GENERATED"
    CHAT_QUERY_EXECUTED = "CHAT_QUERY_EXECUTED"
    MESSAGE_SENT = "MESSAGE_SENT"
    ACCESS_RENEWAL_REQUESTED = "ACCESS_RENEWAL_REQUESTED"
    MESSAGE_PLANNED_AS_TASK = "MESSAGE_PLANNED_AS_TASK"


_SENSITIVE_PARTS = {
    "password", "mot_de_passe", "hashed_password", "hash_mot_de_passe",
    "jwt", "token", "secret", "api_key", "apikey", "authorization",
    "cookie", "set_cookie", "binary", "contenu_binaire", "texte_ocr",
}


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    if depth > 6:
        return "[profondeur limitée]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item, depth=depth + 1)
            for key, item in value.items()
            if not _is_sensitive(str(key))
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item, depth=depth + 1) for item in list(value)[:200]]
    return str(value)[:2000]


def nettoyer_donnees(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Copie sérialisable sans secrets ni texte OCR complet."""
    if value is None:
        return None
    cleaned = _json_safe(value)
    return cleaned if isinstance(cleaned, dict) else None


def _module_for(action: str, resource_type: str | None) -> str:
    prefix = action.split("_", 1)[0].lower()
    mapping = {
        "login": "authentification", "user": "utilisateurs",
        "document": "documents", "documents": "documents",
        "entry": "comptabilite", "accounting": "comptabilite",
        "bank": "banque", "account": "plan_comptable",
        "task": "taches", "export": "exports", "chat": "assistant",
        "message": "messagerie", "access": "authentification",
    }
    return mapping.get(prefix, (resource_type or "systeme").lower())[:50]


def enregistrer(
    db: Session,
    *,
    action: str,
    user: User | None = None,
    cabinet_id: uuid.UUID | None = None,
    entreprise_id: uuid.UUID | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    avant: dict[str, Any] | None = None,
    apres: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    description: str | None = None,
    status: str = "success",
    actor_type: str = "user",
    ip_address: str | None = None,
    user_agent: str | None = None,
    correlation_id: str | None = None,
    item_count: int | None = None,
    resource_ids: Iterable[uuid.UUID | str] | None = None,
    module: str | None = None,
) -> AuditLog:
    resolved_cabinet_id = cabinet_id or (getattr(user, "cabinet_id", None) if user else None)
    if resolved_cabinet_id is None:
        raise ValueError("cabinet_id est obligatoire pour un événement d'audit")
    if status not in {"success", "failed"}:
        raise ValueError("status d'audit invalide")

    role = getattr(user, "role", None) if user else None
    role_value = role.value if isinstance(role, enum.Enum) else (str(role) if role else None)
    prenom = getattr(user, "prenom", "") if user else ""
    nom = getattr(user, "nom", "") if user else ""
    actor_name = " ".join(part for part in (prenom, nom) if part).strip() or None
    cleaned_before = nettoyer_donnees(avant)
    cleaned_after = nettoyer_donnees(apres)
    ids = [str(value) for value in list(resource_ids or [])[:200]] or None

    journal = AuditLog(
        cabinet_id=resolved_cabinet_id,
        entreprise_id=entreprise_id,
        user_id=getattr(user, "id", None) if user else None,
        action=action[:100],
        module=(module or _module_for(action, resource_type))[:50],
        resource_type=resource_type[:50] if resource_type else None,
        resource_id=resource_id,
        description=description[:1000] if description else None,
        status=status,
        actor_type=actor_type[:30],
        actor_name=actor_name,
        actor_email=getattr(user, "email", None) if user else None,
        actor_role=role_value,
        details={
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id else None,
            "avant": cleaned_before,
            "apres": cleaned_after,
        },
        old_values=cleaned_before,
        new_values=cleaned_after,
        event_metadata=nettoyer_donnees(metadata),
        resource_ids=ids,
        item_count=item_count,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
        correlation_id=correlation_id[:128] if correlation_id else None,
    )
    db.add(journal)
    return journal


def valeurs_modifiees(avant: dict[str, Any], apres: dict[str, Any]) -> tuple[dict, dict]:
    """Réduit les snapshots aux seuls champs réellement modifiés."""
    changed = {key for key in set(avant) | set(apres) if avant.get(key) != apres.get(key)}
    return (
        nettoyer_donnees({key: avant.get(key) for key in changed}) or {},
        nettoyer_donnees({key: apres.get(key) for key in changed}) or {},
    )
