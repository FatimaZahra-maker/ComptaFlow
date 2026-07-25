"""app/models/enums.py — enums métier, basés sur le cahier des charges."""
import enum


class RoleEnum(str, enum.Enum):
    """§7 — les 6 rôles du cabinet."""
    SUPER_ADMIN = "super_admin"
    ADMIN_CABINET = "admin_cabinet"
    EXPERT_COMPTABLE = "expert_comptable"
    CHEF_MISSION = "chef_mission"
    COLLABORATEUR = "collaborateur"
    ASSISTANT = "assistant"


class CategorieDocumentEnum(str, enum.Enum):
    """§6 — catégories du chrono."""
    CLIENTS = "clients"
    FOURNISSEURS = "fournisseurs"
    BANQUE = "banque"
    CNSS = "cnss"
    TVA = "tva"
    IMPOTS = "impots"
    ACHATS = "achats"
    VENTES = "ventes"
    DIVERS = "divers"


class StatutDocumentEnum(str, enum.Enum):
    EN_ATTENTE = "en_attente"        # uploadé, pas encore traité
    EN_TRAITEMENT = "en_traitement"  # OCR/IA en cours (tâche Celery)
    TRAITE = "traite"                # OCR/IA fini, écriture proposée
    VALIDE = "valide"                # validé par le comptable
    ERREUR = "erreur"                # échec, intervention manuelle requise


class TypeErreurEnum(str, enum.Enum):
    """
    SPRINT 1.1 — catégorise Document.type_erreur quand statut == ERREUR.
    Alimente le dashboard : différencier "en cours de nouvelle tentative
    automatique" (transitoire) de "nécessite une action humaine"
    (définitive) sans avoir à parser message_erreur.
    """
    TRANSITOIRE = "transitoire"
    DEFINITIVE = "definitive"


class TypeEcritureEnum(str, enum.Enum):
    ACHAT = "achat"
    VENTE = "vente"
    BANQUE = "banque"
    CNSS = "cnss"
    IMPOT = "impot"
    AUTRE = "autre"


class TauxTVAEnum(str, enum.Enum):
    """Taux TVA marocains — sert à la détection d'anomalies."""
    TAUX_20 = "20"
    TAUX_14 = "14"
    TAUX_10 = "10"
    TAUX_7 = "7"
    TAUX_0 = "0"


class StatutValidationEnum(str, enum.Enum):
    BROUILLON = "brouillon"     # extraction IA brute
    A_VERIFIER = "a_verifier"   # anomalie détectée automatiquement
    VALIDE = "valide"
    REJETE = "rejete"
    
class StatutTacheEnum(str, enum.Enum):
    A_FAIRE = "a_faire"
    EN_COURS = "en_cours"
    TERMINEE = "terminee"


class PrioriteTacheEnum(str, enum.Enum):
    BASSE = "basse"
    NORMALE = "normale"
    HAUTE = "haute"


class RecurrenceTacheEnum(str, enum.Enum):
    AUCUNE = "aucune"
    MENSUELLE = "mensuelle"
    TRIMESTRIELLE = "trimestrielle"
    ANNUELLE = "annuelle"
    
class TypeMouvementBancaireEnum(str, enum.Enum):
    """Pour catégoriser les lignes d'un relevé bancaire."""
    DEBIT = "debit"    # Retrait / Décaissement
    CREDIT = "credit"  # Dépôt / Encaissement