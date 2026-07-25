"""
app/api/taches.py

Routes CRUD pour Rappels & Tâches, plus une route dédiée pour marquer
une tâche terminée (déclenche la régénération si récurrente -- voir
tache_service.marquer_terminee_et_regenerer).
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.tache import Tache
from app.models.entreprise import Entreprise
from app.schemas.tache import TacheCreate, TacheUpdate, TacheOut
from app.services.tache_service import est_en_retard, marquer_terminee_et_regenerer

router = APIRouter(prefix="/taches", tags=["taches"])


def _vers_tache_out(tache: Tache, entreprise_nom: str | None, assignee_nom: str | None) -> TacheOut:
    item = TacheOut.model_validate(tache)
    item.entreprise_nom = entreprise_nom
    item.assignee_nom = assignee_nom
    item.est_en_retard = est_en_retard(tache)
    return item


@router.get("", response_model=list[TacheOut])
def list_taches(
    entreprise_id: uuid.UUID | None = Query(default=None),
    statut: str | None = Query(default=None),
    seulement_en_retard: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Tache, Entreprise.nom, User.prenom, User.nom)
        .join(Entreprise, Tache.entreprise_id == Entreprise.id, isouter=True)
        .join(User, Tache.assignee_a == User.id, isouter=True)
        .where(Tache.cabinet_id == current_user.cabinet_id)
    )
    if entreprise_id is not None:
        query = query.where(Tache.entreprise_id == entreprise_id)
    if statut is not None:
        query = query.where(Tache.statut == statut)
    query = query.order_by(Tache.date_echeance)

    resultats = db.execute(query).all()

    sortie = []
    for tache, entreprise_nom, assignee_prenom, assignee_nom in resultats:
        nom_complet = f"{assignee_prenom} {assignee_nom}" if assignee_prenom else None
        item = _vers_tache_out(tache, entreprise_nom, nom_complet)
        if seulement_en_retard and not item.est_en_retard:
            continue
        sortie.append(item)
    return sortie


@router.post("", response_model=TacheOut, status_code=201)
def create_tache(
    payload: TacheCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.entreprise_id is not None:
        entreprise = db.query(Entreprise).filter(
            Entreprise.id == payload.entreprise_id,
            Entreprise.cabinet_id == current_user.cabinet_id,
        ).first()
        if entreprise is None:
            raise HTTPException(status_code=404, detail="Entreprise introuvable.")

    tache = Tache(
        cabinet_id=current_user.cabinet_id,
        cree_par=current_user.id,
        entreprise_id=payload.entreprise_id,
        assignee_a=payload.assignee_a,
        titre=payload.titre,
        description=payload.description,
        date_echeance=payload.date_echeance,
        priorite=payload.priorite,
        recurrence=payload.recurrence,
    )
    db.add(tache)
    db.commit()
    db.refresh(tache)
    return _vers_tache_out(tache, None, None)


@router.patch("/{tache_id}", response_model=TacheOut)
def update_tache(
    tache_id: uuid.UUID,
    payload: TacheUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tache = db.query(Tache).filter(
        Tache.id == tache_id, Tache.cabinet_id == current_user.cabinet_id,
    ).first()
    if tache is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")

    donnees = payload.model_dump(exclude_unset=True)
    for champ, valeur in donnees.items():
        setattr(tache, champ, valeur)
    db.commit()
    db.refresh(tache)
    return _vers_tache_out(tache, None, None)


@router.patch("/{tache_id}/terminer", response_model=TacheOut)
def terminer_tache(
    tache_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Marque la tâche terminée -- régénère automatiquement la
    prochaine occurrence si elle est récurrente."""
    tache = db.query(Tache).filter(
        Tache.id == tache_id, Tache.cabinet_id == current_user.cabinet_id,
    ).first()
    if tache is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")

    marquer_terminee_et_regenerer(db, tache)
    return _vers_tache_out(tache, None, None)


@router.delete("/{tache_id}", status_code=204)
def delete_tache(
    tache_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tache = db.query(Tache).filter(
        Tache.id == tache_id, Tache.cabinet_id == current_user.cabinet_id,
    ).first()
    if tache is None:
        raise HTTPException(status_code=404, detail="Tâche introuvable.")
    db.delete(tache)
    db.commit()