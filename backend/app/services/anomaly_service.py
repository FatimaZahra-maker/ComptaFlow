"""
app/services/anomaly_service.py

Détection de doublons potentiels : même entreprise, même tiers, même
montant TTC, date à ±3 jours. N'appelle jamais accounting_service ni
inversement — c'est document_processing.py qui enchaîne les deux.
"""
from datetime import timedelta

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.ecriture import EcritureComptable

_TOLERANCE_JOURS = 3


def appliquer_detection_doublon(db: Session, ecriture: EcritureComptable) -> None:
    """
    Cherche une écriture existante potentiellement identique à
    `ecriture` (déjà en base). Si trouvée, remplit doublon_potentiel_id
    et force anomalie_detectee=True sur `ecriture`, puis commit.
    Ne fait rien si tiers ou date_piece sont absents (pas assez
    d'information pour comparer sans risquer de faux positifs).
    """
    if not ecriture.tiers or not ecriture.date_piece:
        return

    borne_min = ecriture.date_piece - timedelta(days=_TOLERANCE_JOURS)
    borne_max = ecriture.date_piece + timedelta(days=_TOLERANCE_JOURS)

    candidat = (
        db.query(EcritureComptable)
        .filter(
            and_(
                EcritureComptable.id != ecriture.id,
                EcritureComptable.entreprise_id == ecriture.entreprise_id,
                EcritureComptable.tiers == ecriture.tiers,
                EcritureComptable.montant_ttc == ecriture.montant_ttc,
                EcritureComptable.date_piece >= borne_min,
                EcritureComptable.date_piece <= borne_max,
            )
        )
        .first()
    )

    if candidat is not None:
        ecriture.doublon_potentiel_id = candidat.id
        ecriture.anomalie_detectee = True
        message_doublon = f"Doublon potentiel avec l'écriture {candidat.id}."
        ecriture.anomalie_details = (
            f"{ecriture.anomalie_details} | {message_doublon}"
            if ecriture.anomalie_details
            else message_doublon
        )
        db.commit()