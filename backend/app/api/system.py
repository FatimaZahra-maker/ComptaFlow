"""
app/api/system.py

Route unique, en lecture seule : expose la configuration IA active
(cloud/local, modèle Ollama) pour affichage dans Paramètres. Ne
renvoie JAMAIS la clé API elle-même -- seulement un booléen indiquant
si elle est configurée, pour ne pas exposer un secret côté frontend.
"""
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.system import SystemInfoOut

router = APIRouter(prefix="/system", tags=["system"])


# Renvoie l'état de la configuration IA du backend, pour que
# l'utilisateur comprenne quel fournisseur traite ses documents.
@router.get("/info", response_model=SystemInfoOut)
def get_system_info(current_user: User = Depends(get_current_user)):
    return SystemInfoOut(
        ai_provider=settings.AI_PROVIDER,
        groq_configure=bool(settings.GROQ_API_KEY),
        ollama_model=settings.OLLAMA_MODEL,
    )
