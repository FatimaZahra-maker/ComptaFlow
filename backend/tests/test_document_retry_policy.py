from app.core.exceptions import ErreurPipelineTransitoire
from app.tasks.document_processing import _erreur_est_transitoire


class HttpError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


def test_retry_uniquement_pour_erreurs_transitoires():
    assert _erreur_est_transitoire(ErreurPipelineTransitoire("temporaire"))
    assert _erreur_est_transitoire(TimeoutError())
    assert _erreur_est_transitoire(HttpError(429))
    assert _erreur_est_transitoire(HttpError(503))
    assert not _erreur_est_transitoire(ValueError("json invalide"))
    assert not _erreur_est_transitoire(HttpError(400))
