from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import configurer_logging
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.documents import router as documents_router
from app.api.accounting import router as accounting_router
from app.api.entreprises import router as entreprises_router
from app.api.chronos import router as chronos_router
from app.api.dashboard import router as dashboard_router
from app.api.search import router as search_router
from app.api.notifications import router as notifications_router
from app.api.export import router as export_router
from app.api.taches import router as taches_router
# --- Nouveaux imports ajoutés ici ---
from app.api.cabinet import router as cabinet_router
from app.api.system import router as system_router

configurer_logging()

app = FastAPI(title=settings.APP_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(taches_router)
# --- Nouveaux routeurs enregistrés ici ---
app.include_router(cabinet_router)
app.include_router(system_router)


@app.get("/")
def health_check():
    return {"status": "ok", "app": settings.APP_NAME}