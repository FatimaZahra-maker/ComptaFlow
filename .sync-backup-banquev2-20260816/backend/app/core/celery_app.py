"""
app/core/celery_app.py

Instance Celery partagée par l'API et le worker.
Redis sert à la fois de broker et de backend de résultats.

Objectifs de cette configuration :
- ne pas précharger Ollama au démarrage ;
- limiter la réservation de tâches lourdes avec worker_prefetch_multiplier=1 ;
- conserver les tâches fiables avec task_acks_late=True ;
- utiliser la même configuration de logs que l'API.

Ollama reste disponible comme fallback : il sera chargé uniquement lorsqu'un
document en aura réellement besoin. Cela évite d'occuper inutilement la RAM
quand Groq fonctionne normalement.
"""

from celery import Celery
from celery.signals import setup_logging as celery_setup_logging_signal

from app.core.config import settings


celery_app = Celery(
    "comptaflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    timezone="Africa/Casablanca",
    enable_utc=True,

    task_track_started=True,

    # Si le worker plante pendant le traitement,
    # la tâche n'est pas considérée comme terminée trop tôt.
    task_acks_late=True,

    # Reconnexion automatique à Redis au démarrage.
    broker_connection_retry_on_startup=True,

    # IMPORTANT pour les documents lourds :
    # le worker ne réserve pas plusieurs documents en avance.
    worker_prefetch_multiplier=1,
)


# Recherche automatiquement les tâches Celery déclarées dans app/.
celery_app.autodiscover_tasks(["app"])


@celery_setup_logging_signal.connect
def _configurer_logging_worker(**kwargs):
    """
    Utilise le même système de logs que l'API FastAPI.
    """
    from app.core.logging_config import configurer_logging

    configurer_logging()