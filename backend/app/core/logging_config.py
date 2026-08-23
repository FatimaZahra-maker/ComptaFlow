"""
app/core/logging_config.py

Configuration centralisée du logging pour toute l'application
(API FastAPI ET worker Celery). Un seul format partout pour que les
logs soient faciles à lire/grep, que l'erreur vienne de l'API ou du
pipeline en arrière-plan.

Appelée une fois au démarrage de chaque processus :
- app/main.py (API)
- app/core/celery_app.py (worker, via le signal setup_logging)
"""
import logging
import sys
from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class _RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        return True


_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configurer_logging(niveau: int = logging.INFO) -> None:
    """
    Configure le logger racine avec un format unique.
    Idempotent : si déjà configuré (handlers présents), ne fait rien --
    évite les logs dupliqués si appelé plusieurs fois (ex: reload
    FastAPI en dev).
    """
    logger_racine = logging.getLogger()
    if logger_racine.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_RequestContextFilter())
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    logger_racine.setLevel(niveau)
    logger_racine.addHandler(handler)

    # Librairies tierces trop verbeuses en INFO -> on les calme pour
    # ne garder que ce qui vient vraiment de ComptaFlow dans les logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
