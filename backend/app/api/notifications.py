"""
app/api/notifications.py

Centre de notifications + endpoint d'agrégats (page dédiée avec
graphiques). Chaque notification porte désormais son contexte
entreprise, pour répondre précisément à "pour quelle entreprise
exactement" plutôt qu'un message générique.
"""
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.entreprise import Entreprise
from app.models.ecriture import EcritureComptable
from app.models.enums import StatutDocumentEnum, StatutValidationEnum
from app.schemas.notification import (
    NotificationOut, NotificationsOut, NotificationsStatsOut,
    RepartitionParType, RepartitionParEntreprise,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])

MAX_NOTIFICATIONS = 100


def _construire_notifications(db: Session, cabinet_id) -> list[NotificationOut]:
    notifications: list[NotificationOut] = []

    # --- 1. Documents en erreur (OCR/IA échoué) ---
    documents_erreur = db.execute(
        select(Document, Entreprise.nom)
        .join(Entreprise, Document.entreprise_id == Entreprise.id, isouter=True)
        .where(Document.cabinet_id == cabinet_id, Document.statut == StatutDocumentEnum.ERREUR)
    ).all()
    for document, entreprise_nom in documents_erreur:
        notifications.append(NotificationOut(
            id=f"document_erreur-{document.id}",
            type="document_erreur",
            message=f"Échec du traitement de « {document.nom_fichier_original} »"
                     + (f" : {document.message_erreur}" if document.message_erreur else ""),
            route=f"/documents/{document.id}",
            created_at=document.updated_at,
            entreprise_id=document.entreprise_id,
            entreprise_nom=entreprise_nom,
        ))

    # --- 2. Écritures avec anomalie détectée ---
    ecritures_anomalie = db.execute(
        select(EcritureComptable, Entreprise.nom)
        .join(Entreprise, EcritureComptable.entreprise_id == Entreprise.id, isouter=True)
        .where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.anomalie_detectee == True,  # noqa: E712
        )
    ).all()
    for ecriture, entreprise_nom in ecritures_anomalie:
        notifications.append(NotificationOut(
            id=f"ecriture_anomalie-{ecriture.id}",
            type="ecriture_anomalie",
            message=f"Anomalie détectée sur l'écriture de « {ecriture.tiers or 'tiers inconnu'} »"
                     + (f" : {ecriture.anomalie_details}" if ecriture.anomalie_details else ""),
            route=f"/documents/{ecriture.document_id}",
            created_at=ecriture.updated_at,
            entreprise_id=ecriture.entreprise_id,
            entreprise_nom=entreprise_nom,
        ))

    # --- 3. Écritures à vérifier (hors doublon avec anomalie) ---
    ecritures_a_verifier = db.execute(
        select(EcritureComptable, Entreprise.nom)
        .join(Entreprise, EcritureComptable.entreprise_id == Entreprise.id, isouter=True)
        .where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.statut_validation == StatutValidationEnum.A_VERIFIER,
        )
    ).all()
    ids_deja_notifies = {n.id for n in notifications}
    for ecriture, entreprise_nom in ecritures_a_verifier:
        notif_id = f"ecriture_a_verifier-{ecriture.id}"
        if f"ecriture_anomalie-{ecriture.id}" in ids_deja_notifies:
            continue
        notifications.append(NotificationOut(
            id=notif_id,
            type="ecriture_a_verifier",
            message=f"Écriture à vérifier pour « {ecriture.tiers or 'tiers inconnu'} »",
            route=f"/documents/{ecriture.document_id}",
            created_at=ecriture.updated_at,
            entreprise_id=ecriture.entreprise_id,
            entreprise_nom=entreprise_nom,
        ))

    # --- 4. Documents nouvellement traités ---
    documents_traites = db.execute(
        select(Document, Entreprise.nom)
        .join(Entreprise, Document.entreprise_id == Entreprise.id, isouter=True)
        .where(Document.cabinet_id == cabinet_id, Document.statut == StatutDocumentEnum.TRAITE)
    ).all()
    for document, entreprise_nom in documents_traites:
        notifications.append(NotificationOut(
            id=f"document_nouveau-{document.id}",
            type="document_nouveau",
            message=f"Nouveau document classé : « {document.nom_fichier_original} »",
            route=f"/documents/{document.id}",
            created_at=document.updated_at,
            entreprise_id=document.entreprise_id,
            entreprise_nom=entreprise_nom,
        ))

    notifications.sort(key=lambda n: n.created_at, reverse=True)
    return notifications


@router.get("", response_model=NotificationsOut)
def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    notifications = _construire_notifications(db, current_user.cabinet_id)[:MAX_NOTIFICATIONS]
    return NotificationsOut(total=len(notifications), notifications=notifications)


@router.get("/stats", response_model=NotificationsStatsOut)
def get_notifications_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Agrégats pour la page Notifications dédiée : répartition par type
    (graphique en barres) et par entreprise (identifier précisément
    quelle entreprise génère le plus d'alertes).
    """
    notifications = _construire_notifications(db, current_user.cabinet_id)

    compteur_type = Counter(n.type for n in notifications)
    par_type = [RepartitionParType(type=t, total=n) for t, n in compteur_type.most_common()]

    compteur_entreprise: dict[str, dict] = {}
    for n in notifications:
        cle = str(n.entreprise_id) if n.entreprise_id else "inconnue"
        if cle not in compteur_entreprise:
            compteur_entreprise[cle] = {
                "entreprise_id": n.entreprise_id,
                "entreprise_nom": n.entreprise_nom or "Entreprise non identifiée",
                "total": 0,
            }
        compteur_entreprise[cle]["total"] += 1

    par_entreprise = [
        RepartitionParEntreprise(**v)
        for v in sorted(compteur_entreprise.values(), key=lambda x: x["total"], reverse=True)
    ]

    return NotificationsStatsOut(par_type=par_type, par_entreprise=par_entreprise)