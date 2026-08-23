"""Point d'entrée FastAPI de ComptaFlow."""

import logging
import re
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from sqlalchemy import text

from app.api.accounting import router as accounting_router
from app.api.auth import router as auth_router
from app.api.cabinet import router as cabinet_router
from app.api.chronos import router as chronos_router
from app.api.cloture import router as cloture_router
from app.api.dashboard import router as dashboard_router
from app.api.documents import router as documents_router
from app.api.entreprises import router as entreprises_router
from app.api.export import router as export_router
from app.api.exchange_rates import router as exchange_rates_router
from app.api.notifications import router as notifications_router
from app.api.plan_comptable import router as plan_comptable_router
from app.api.rappels import router as rappels_router
from app.api.rapports import router as rapports_router
from app.api.search import router as search_router
from app.api.system import router as system_router
from app.api.taches import router as taches_router
from app.api.users import router as users_router
from app.api.tva import router as tva_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging_config import configurer_logging, request_id_context

configurer_logging()

app = FastAPI(title=settings.APP_NAME)
logger = logging.getLogger("comptaflow.http")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def ajouter_contexte_requete(request: Request, call_next):
    valeur = request.headers.get("X-Request-ID", "")
    request_id = valeur if re.fullmatch(r"[A-Za-z0-9._-]{1,128}", valeur) else str(uuid.uuid4())
    token = request_id_context.set(request_id)
    debut = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        duree_ms = (time.perf_counter() - debut) * 1000
        logger.info("%s %s duration_ms=%.1f", request.method, request.url.path, duree_ms)
        request_id_context.reset(token)
    response.headers["X-Request-ID"] = request_id
    return response

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(documents_router)
app.include_router(accounting_router)
app.include_router(entreprises_router)
app.include_router(chronos_router)
app.include_router(dashboard_router)
app.include_router(search_router)
app.include_router(notifications_router)
app.include_router(export_router)
app.include_router(exchange_rates_router)
app.include_router(taches_router)
app.include_router(cabinet_router)
app.include_router(system_router)
app.include_router(rappels_router)
app.include_router(rapports_router)
app.include_router(plan_comptable_router)
app.include_router(tva_router)
app.include_router(cloture_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/ready")
def readiness_check():
    services = {"database": False, "redis": False}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        services["database"] = True
        client = Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        services["redis"] = bool(client.ping())
    except Exception:
        logger.exception("Readiness check failed")
        raise HTTPException(status_code=503, detail={"status": "not_ready", "services": services})
    return {"status": "ready", "services": services}


@app.get("/")
def root_health_check():
    return health_check()
