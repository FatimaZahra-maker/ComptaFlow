"""
app/core/celery_app.py

Instance Celery partagée par l'API et le worker. Redis sert de broker
ET de backend (stockage des résultats).

CORRECTIF : la version précédente référençait settings.CELERY_BROKER_URL
/ settings.CELERY_RESULT_BACKEND, qui n'existent PAS dans app/core/config.py
(seul REDIS_URL y est défini) -- ça aurait fait planter le worker au
démarrage avec une AttributeError. Revenu à settings.REDIS_URL pour les
deux.

worker_prefetch_multiplier=1 : chaque tâche charge des pages entières en
RAM (prétraitement + OCR) -- on ne veut jamais qu'un worker réserve
plusieurs documents lourds d'avance.
"""
from celery import Celery
from celery.signals import setup_logging as celery_setup_logging_signal
from celery.signals import worker_ready

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
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
)

celery_app.autodiscover_tasks(["app"])


@celery_setup_logging_signal.connect
def _configurer_logging_worker(**kwargs):
    """Remplace le setup de logging par défaut de Celery par le nôtre
    (même format que l'API -- voir app/core/logging_config.py)."""
    from app.core.logging_config import configurer_logging
    configurer_logging()


@worker_ready.connect
def _prechauffer_au_demarrage(**kwargs):
    """Charge le modèle Ollama en mémoire dès le démarrage du worker,
    pour ne pas payer le rechargement sur le premier document."""
    from app.services.ai_service import prechauffer_modele
    prechauffer_modele()