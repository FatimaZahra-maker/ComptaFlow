"""
app/services/accounting_service.py

Ce service s'occupe de transformer les données extraites d'un Document (MVC2) 
en une écriture comptable structurée (EcritureComptable) ou en mouvements bancaires.
Il est orchestré par document_processing.py après le classement du document.

Résolution des montants manquants :
- Si seul montant_ttc est connu avec un taux de TVA, on calcule le HT et la TVA par déduction.
- Si aucun montant n'est exploitable, la valeur 0.00 est stockée en base (colonne NOT NULL) 
  et l'écriture est marquée avec une anomalie explicite pour forcer la vérification humaine.
"""
import uuid
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.enums import TypeEcritureEnum, TauxTVAEnum, StatutValidationEnum

# Mapping pour lier les catégories extraites par l'IA aux types d'écritures officiels
_MAPPING_CATEGORIE_TYPE = {
    "achats": TypeEcritureEnum.ACHAT,
    "fournisseurs": TypeEcritureEnum.ACHAT,
    "ventes": TypeEcritureEnum.VENTE,
    "clients": TypeEcritureEnum.VENTE,
    "banque": TypeEcritureEnum.BANQUE,
    "cnss": TypeEcritureEnum.CNSS,
    "tva": TypeEcritureEnum.IMPOT,
    "impots": TypeEcritureEnum.IMPOT,
}

# Dictionnaire des taux de TVA reconnus pour sécuriser l'affectation
_TAUX_VALIDES = {20: TauxTVAEnum.TAUX_20, 14: TauxTVAEnum.TAUX_14,
                 10: TauxTVAEnum.TAUX_10, 7: TauxTVAEnum.TAUX_7, 0: TauxTVAEnum.TAUX_0}


def _determiner_type_ecriture(categorie: str | None) -> TypeEcritureEnum:
    """Détermine le type d'écriture comptable en fonction de la catégorie textuelle."""
    return _MAPPING_CATEGORIE_TYPE.get(categorie, TypeEcritureEnum.AUTRE)


def _normaliser_taux_tva(valeur) -> TauxTVAEnum:
    """Convertit une valeur de TVA brute en un Enum strict, par défaut à TAUX_0."""
    if valeur is None:
        return TauxTVAEnum.TAUX_0
    try:
        entier = int(round(float(valeur)))
    except (TypeError, ValueError):
        return TauxTVAEnum.TAUX_0
    return _TAUX_VALIDES.get(entier, TauxTVAEnum.TAUX_0)


def _vers_decimal(valeur) -> Decimal | None:
    """Convertit de manière sécurisée une valeur en Decimal arrondi à 2 décimales."""
    if valeur is None:
        return None
    try:
        return Decimal(str(valeur)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _resoudre_montants(donnees: dict, taux_enum: TauxTVAEnum) -> tuple[Decimal | None, Decimal | None, Decimal, bool, str | None]:
    """
    Tente de déduire les montants HT, TVA et TTC s'il en manque certains.
    Retourne : (montant_ht, montant_tva, montant_ttc, anomalie_detectee, message_erreur)
    """
    ht = _vers_decimal(donnees.get("montant_ht"))
    tva = _vers_decimal(donnees.get("montant_tva"))
    ttc = _vers_decimal(donnees.get("montant_ttc"))
    taux_pct = Decimal(taux_enum.value) / Decimal(100)

    # Scénario 1 : On a le TTC mais pas le HT ni la TVA (Déduction par le bas)
    if ttc is not None and ht is None and tva is None:
        if taux_pct > 0:
            ht = (ttc / (1 + taux_pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tva = (ttc - ht).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            ht, tva = ttc, Decimal("0.00")

    # Scénario 2 : On a le HT, on calcule le reste (Déduction par le haut)
    if ttc is None and ht is not None:
        tva = tva if tva is not None else (ht * taux_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ttc = (ht + tva).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Scénario 3 : Impossible de déterminer le TTC (Cas d'anomalie sévère)
    if ttc is None:
        # Le TTC étant obligatoire en base, on force 0.00 et on lève une anomalie
        return ht, tva, Decimal("0.00"), True, "Aucun montant total TTC détecté dans le document."

    return ht, tva, ttc, False, None


def creer_ecriture_depuis_document(db: Session, document: Document) -> EcritureComptable:
    """
    Génère l'écriture comptable finale après le classement d'un document.
    Combine les données de base et les vérifications d'anomalies.
    """
    donnees = document.donnees_extraites or {}

    type_ecriture = _determiner_type_ecriture(donnees.get("categorie"))
    taux_enum = _normaliser_taux_tva(donnees.get("taux_tva"))
    ht, tva, ttc, anomalie_montants, message_montants = _resoudre_montants(donnees, taux_enum)

    # Récupération des drapeaux d'anomalies détectées par le service d'extraction (Regex/IA)
    anomalie_regex = bool(donnees.get("a_verifier"))
    raison_regex = donnees.get("raison_verification")

    # Fusion des anomalies (montants + extraction)
    anomalie_detectee = anomalie_montants or anomalie_regex
    if anomalie_montants and anomalie_regex:
        anomalie_details = f"{message_montants} | {raison_regex}"
    else:
        anomalie_details = message_montants or raison_regex

    # Formatage sécurisé de la date de la pièce comptable
    date_piece_str = donnees.get("date_piece")
    date_piece: date_type | None = None
    if date_piece_str:
        try:
            date_piece = date_type.fromisoformat(date_piece_str)
        except ValueError:
            date_piece = None

    # Création de l'entité
    ecriture = EcritureComptable(
        cabinet_id=document.cabinet_id,
        document_id=document.id,
        entreprise_id=document.entreprise_id,
        type_ecriture=type_ecriture,
        numero_piece=donnees.get("numero_piece"),
        date_piece=date_piece,
        tiers=donnees.get("tiers"),
        montant_ht=ht,
        taux_tva=taux_enum,
        montant_tva=tva,
        montant_ttc=ttc,
        statut_validation=(
            StatutValidationEnum.A_VERIFIER if anomalie_detectee else StatutValidationEnum.BROUILLON
        ),
        anomalie_detectee=anomalie_detectee,
        anomalie_details=anomalie_details,
    )
    
    db.add(ecriture)
    db.commit()
    db.refresh(ecriture)
    return ecriture


def creer_mouvements_bancaires(db: Session, document: Document) -> list[MouvementBancaire]:
    """
    Traite spécifiquement les relevés bancaires pour générer 
    les lignes de mouvements individuelles à partir du tableau extrait.
    """
    donnees = document.donnees_extraites or {}
    lignes_extraites = donnees.get("lignes_bancaires", [])
    
    mouvements_crees = []
    
    for ligne in lignes_extraites:
        # Sécurisation de la date (fallback sur la date d'upload si introuvable)
        date_str = ligne.get("date_operation")
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else document.created_at.date()
        except ValueError:
            date_obj = document.created_at.date()
            
        # Sécurisation des montants et des soldes
        try:
            montant = Decimal(str(ligne.get("montant", "0.00")))
        except:
            montant = Decimal("0.00")
            
        try:
            solde = Decimal(str(ligne.get("solde_apres_operation", "0.00"))) if ligne.get("solde_apres_operation") else None
        except:
            solde = None

        # Création du mouvement individuel
        mouvement = MouvementBancaire(
            document_id=document.id,
            entreprise_id=document.entreprise_id,
            date_operation=date_obj,
            libelle=ligne.get("libelle", "Opération inconnue")[:255],
            reference=ligne.get("reference"),
            type_mouvement=ligne.get("type_mouvement", "DEBIT"),
            montant=montant,
            solde_apres_operation=solde
        )
        db.add(mouvement)
        mouvements_crees.append(mouvement)
        
    db.commit()
    return mouvements_crees