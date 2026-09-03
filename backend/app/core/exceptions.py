"""
app/core/exceptions.py

Définition des exceptions personnalisées pour le pipeline de traitement.
Permet à l'orchestrateur de distinguer les erreurs nécessitant un retry 
des erreurs bloquantes.
"""

class DocumentProcessingError(Exception):
    """Classe de base pour toutes les erreurs du pipeline de document."""
    pass


class PeriodeComptableVerrouilleeError(ValueError):
    """Mutation métier refusée car la période ComptaFlow est en lecture seule."""

    def __init__(self, message: str = "Cette période comptable ComptaFlow est verrouillée et accessible en lecture seule."):
        super().__init__(message)

class ErreurPipelineDefinitive(DocumentProcessingError):
    """
    Erreur bloquante liée au document lui-même. 
    Un retry ne résoudra pas le problème. 
    Exemples : PDF chiffré par mot de passe, image totalement noire, JSON illisible.
    """
    def __init__(self, message: str, code: str = "ERREUR_DEFINITIVE"):
        super().__init__(message)
        self.code = code

class ErreurPipelineTransitoire(DocumentProcessingError):
    """
    Erreur liée à l'infrastructure ou au réseau. 
    Doit déclencher un retry de la tâche Celery.
    Exemples : Timeout Ollama, Base de données verrouillée.
    """
    def __init__(self, message: str, code: str = "ERREUR_TRANSITOIRE"):
        super().__init__(message)
        self.code = code

# --- Sous-classes spécifiques pour plus de granularité (Définitives) ---

class FichierIllisibleError(ErreurPipelineDefinitive):
    def __init__(self, message: str):
        super().__init__(message, code="FICHIER_ILLISIBLE")

class OCRVideError(ErreurPipelineDefinitive):
    def __init__(self, message: str):
        super().__init__(message, code="OCR_VIDE")
