"""
app/services/accounting_service.py

Transforme les données extraites d'un Document (MVC2) en une écriture
comptable structurée (EcritureComptable). Ne s'appelle jamais soi-même
ni un autre service métier : c'est document_processing.py qui orchestre
l'appel à ce service après le classement du document.

Résolution des montants manquants :
- Si seul montant_ttc est connu et qu'un taux de TVA est identifié, on
  calcule ht et tva par déduction (ht = ttc / (1 + taux/100)).
- Si aucun montant n'est exploitable, on stocke 0.00 (la colonne est
  NOT NULL) et on marque l'écriture anomalie_detectee=True avec un
  message explicite, plutôt que de deviner une valeur.
"""
import uuid
from datetime import date as date_type
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import TypeEcritureEnum, TauxTVAEnum, StatutValidationEnum

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

_TAUX_VALIDES = {20: TauxTVAEnum.TAUX_20, 14: TauxTVAEnum.TAUX_14,
                 10: TauxTVAEnum.TAUX_10, 7: TauxTVAEnum.TAUX_7, 0: TauxTVAEnum.TAUX_0}


def _determiner_type_ecriture(categorie: str | None) -> TypeEcritureEnum:
    return _MAPPING_CATEGORIE_TYPE.get(categorie, TypeEcritureEnum.AUTRE)


def _normaliser_taux_tva(valeur) -> TauxTVAEnum:
    if valeur is None:
        return TauxTVAEnum.TAUX_0
    try:
        entier = int(round(float(valeur)))
    except (TypeError, ValueError):
        return TauxTVAEnum.TAUX_0
    return _TAUX_VALIDES.get(entier, TauxTVAEnum.TAUX_0)


def _vers_decimal(valeur) -> Decimal | None:
    if valeur is None:
        return None
    try:
        return Decimal(str(valeur)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _resoudre_montants(donnees: dict, taux_enum: TauxTVAEnum) -> tuple[Decimal, Decimal, Decimal, bool, str | None]:
    """
    Retourne (montant_ht, montant_tva, montant_ttc, anomalie, message).
    Tente de déduire les montants manquants avant d'abandonner sur 0.00.
    """
    ht = _vers_decimal(donnees.get("montant_ht"))
    tva = _vers_decimal(donnees.get("montant_tva"))
    ttc = _vers_decimal(donnees.get("montant_ttc"))
    taux_pct = Decimal(taux_enum.value) / Decimal(100)

    if ttc is not None and ht is None and tva is None:
        if taux_pct > 0:
            ht = (ttc / (1 + taux_pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tva = (ttc - ht).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            ht, tva = ttc, Decimal("0.00")

    if ttc is None and ht is not None:
        tva = tva if tva is not None else (ht * taux_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ttc = (ht + tva).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if ht is None:
        ht = Decimal("0.00")
    if tva is None:
        tva = Decimal("0.00")

    if ttc is None:
        # Aucun montant exploitable trouvé dans le document -> anomalie
        # explicite, on ne devine rien.
        return ht, tva, Decimal("0.00"), True, "Aucun montant total détecté dans le document."

    return ht, tva, ttc, False, None


def creer_ecriture_depuis_document(db: Session, document: Document) -> EcritureComptable:
    """
    Crée et enregistre une EcritureComptable à partir de
    document.donnees_extraites. Appelée une seule fois par document,
    juste après son classement dans document_processing.py.
    """
    donnees = document.donnees_extraites or {}

    type_ecriture = _determiner_type_ecriture(donnees.get("categorie"))
    taux_enum = _normaliser_taux_tva(donnees.get("taux_tva"))
    ht, tva, ttc, anomalie_montants, message_montants = _resoudre_montants(donnees, taux_enum)

    # Reprend le garde-fou déjà calculé par regex_extraction_service en
    # MVC2 (a_verifier / raison_verification), sans le recalculer.
    anomalie_regex = bool(donnees.get("a_verifier"))
    raison_regex = donnees.get("raison_verification")

    anomalie_detectee = anomalie_montants or anomalie_regex
    if anomalie_montants and anomalie_regex:
        anomalie_details = f"{message_montants} | {raison_regex}"
    else:
        anomalie_details = message_montants or raison_regex

    date_piece_str = donnees.get("date_piece")
    date_piece: date_type | None = None
    if date_piece_str:
        try:
            date_piece = date_type.fromisoformat(date_piece_str)
        except ValueError:
            date_piece = None

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