"""
app/services/tache_service.py

Logique métier des Rappels & Tâches : calcul du retard, et génération
automatique de la prochaine occurrence quand une tâche récurrente est
marquée terminée (ex: "déclarer la TVA" tous les mois -- terminer
l'échéance de juillet crée automatiquement celle d'août).
"""
from datetime import date, timedelta

from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models.tache import Tache
from app.models.enums import StatutTacheEnum, RecurrenceTacheEnum

_DELTA_RECURRENCE = {
    RecurrenceTacheEnum.MENSUELLE: relativedelta(months=1),
    RecurrenceTacheEnum.TRIMESTRIELLE: relativedelta(months=3),
    RecurrenceTacheEnum.ANNUELLE: relativedelta(years=1),
}


def est_en_retard(tache: Tache) -> bool:
    return tache.statut != StatutTacheEnum.TERMINEE and tache.date_echeance < date.today()


def marquer_terminee_et_regenerer(db: Session, tache: Tache) -> Tache | None:
    """
    Marque `tache` comme terminée. Si elle est récurrente, crée et
    retourne la prochaine occurrence (nouvelle ligne, même titre/
    description/priorité/entreprise, date_echeance décalée). Retourne
    None si la tâche n'était pas récurrente -- rien à régénérer.
    """
    tache.statut = StatutTacheEnum.TERMINEE

    if tache.recurrence == RecurrenceTacheEnum.AUCUNE:
        db.commit()
        return None

    delta = _DELTA_RECURRENCE[tache.recurrence]
    prochaine = Tache(
        cabinet_id=tache.cabinet_id,
        entreprise_id=tache.entreprise_id,
        cree_par=tache.cree_par,
        assignee_a=tache.assignee_a,
        titre=tache.titre,
        description=tache.description,
        date_echeance=tache.date_echeance + delta,
        priorite=tache.priorite,
        recurrence=tache.recurrence,
        statut=StatutTacheEnum.A_FAIRE,
    )
    db.add(prochaine)
    db.commit()
    db.refresh(prochaine)
    return prochaine