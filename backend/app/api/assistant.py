"""Endpoint protégé de l'Assistant ComptaFlow en lecture métier seule."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.assistant import AssistantQuery, AssistantResponse
from app.services import assistant_service, audit_service


router = APIRouter(prefix="/assistant", tags=["assistant"])
_WINDOW_SECONDS = 60.0
_MAX_REQUESTS_PER_WINDOW = 30
_requests: dict[uuid.UUID, deque[float]] = defaultdict(deque)


def _check_rate_limit(user_id: uuid.UUID) -> None:
    now = time.monotonic()
    values = _requests[user_id]
    while values and now - values[0] > _WINDOW_SECONDS:
        values.popleft()
    if len(values) >= _MAX_REQUESTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de questions en peu de temps. Réessayez dans une minute.",
        )
    values.append(now)


@router.post("/query", response_model=AssistantResponse)
def query_assistant(
    payload: AssistantQuery,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _check_rate_limit(current_user.id)
    started = time.perf_counter()
    try:
        response = assistant_service.repondre(db, current_user, payload)
    except assistant_service.AssistantForbidden as exc:
        audit_service.enregistrer(
            db, user=current_user, action=audit_service.AuditAction.CHAT_QUERY_EXECUTED,
            resource_type="assistant_query", status="failed",
            description="Question Assistant refusée par les permissions.",
            metadata={"result": "forbidden"},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except assistant_service.AssistantNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        audit_service.enregistrer(
            db, user=current_user, action=audit_service.AuditAction.CHAT_QUERY_EXECUTED,
            resource_type="assistant_query", status="failed",
            description="Échec technique d'une question Assistant.",
            metadata={"result": "error", "error_type": type(exc).__name__},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="L'assistant ne peut pas traiter cette question pour le moment.",
        ) from exc

    resources = [source.resource_id for source in response.sources]
    resources.extend(company.entreprise_id for company in response.companies)
    resources.extend(item.resource_id for item in response.data)
    resources = list(dict.fromkeys(resources))
    entreprise_id = (
        response.documents[0].entreprise_id if response.documents
        else response.companies[0].entreprise_id if len(response.companies) == 1
        else payload.entreprise_id
    )
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.CHAT_QUERY_EXECUTED,
        entreprise_id=entreprise_id, resource_type="assistant_query",
        # Le journal d'audit n'accepte que les statuts techniques
        # ``success`` et ``failed``. Une réponse vide ou une demande de
        # clarification reste une exécution réussie ; sa nature détaillée est
        # conservée dans metadata.response_type ci-dessous.
        status="failed" if response.response_type == "error" else "success",
        description="Question Assistant exécutée.",
        metadata={
            "intent": response.intent, "response_type": response.response_type,
            "domain": response.plan_summary.get("domain"),
            "operation": response.plan_summary.get("operation"),
            "planner_provider": response.plan_summary.get("provider"),
            "result_count": len(response.documents) + len(response.companies) + len(response.payments) + len(response.data),
            "duration_ms": round((time.perf_counter() - started) * 1000),
        },
        resource_ids=resources,
        item_count=len(resources) or None,
        correlation_id=str(response.conversation_id),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return response
