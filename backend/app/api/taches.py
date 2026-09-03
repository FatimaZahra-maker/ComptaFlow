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
from app.services import audit_service

router = APIRouter(prefix="/taches", tags=["taches"])


def _vers_tache_out(tache: Tache, entreprise_nom: str | None, assignee_nom: str | None) -> TacheOut:
    item = TacheOut.model_validate(tache)
    item.entreprise_nom = entreprise_nom
    item.assignee_nom = assignee_nom
    item.est_en_retard = est_en_retard(tache)
    return item


def _verifier_assignee(db: Session, user_id: uuid.UUID | None, cabinet_id: uuid.UUID) -> None:
    if user_id is None:
        return
    exists = db.execute(select(User.id).where(
        User.id == user_id, User.cabinet_id == cabinet_id, User.is_active.is_(True),
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Utilisateur assigné introuvable dans ce cabinet.")


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

    _verifier_assignee(db, payload.assignee_a, current_user.cabinet_id)
    tache = Tache(
        cabinet_id=current_user.cabinet_id,
        cree_par=current_user.id,
        entreprise_id=payload.entreprise_id,
        assignee_a=payload.assignee_a,
        titre=payload.titre,
        description=payload.description,
        date_echeance=payload.date_echeance,
        heure_echeance=payload.heure_echeance,
        priorite=payload.priorite,
        recurrence=payload.recurrence,
    )
    db.add(tache)
    db.flush()
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.TASK_CREATED,
        entreprise_id=tache.entreprise_id, resource_type="tache", resource_id=tache.id,
        description=f"Création de la tâche {tache.titre}.",
        apres={"titre": tache.titre, "date_echeance": tache.date_echeance,
               "heure_echeance": tache.heure_echeance,
               "assignee_a": tache.assignee_a, "priorite": tache.priorite},
    )
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
    if "assignee_a" in donnees:
        _verifier_assignee(db, donnees["assignee_a"], current_user.cabinet_id)
    avant = {champ: getattr(tache, champ) for champ in donnees}
    for champ, valeur in donnees.items():
        setattr(tache, champ, valeur)
    apres = {champ: getattr(tache, champ) for champ in donnees}
    avant_modifie, apres_modifie = audit_service.valeurs_modifiees(avant, apres)
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.TASK_UPDATED,
        entreprise_id=tache.entreprise_id, resource_type="tache", resource_id=tache.id,
        description=f"Modification de la tâche {tache.titre}.",
        avant=avant_modifie, apres=apres_modifie,
    )
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

    prochaine = marquer_terminee_et_regenerer(db, tache)
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.TASK_COMPLETED,
        entreprise_id=tache.entreprise_id, resource_type="tache", resource_id=tache.id,
        description=f"Achèvement de la tâche {tache.titre}.",
        avant={"statut": "a_faire"}, apres={"statut": "terminee"},
        metadata={"prochaine_occurrence_id": prochaine.id if prochaine else None},
    )
    db.commit()
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
    audit_service.enregistrer(
        db, user=current_user, action=audit_service.AuditAction.TASK_DELETED,
        entreprise_id=tache.entreprise_id, resource_type="tache", resource_id=tache.id,
        description=f"Suppression de la tâche {tache.titre}.",
        avant={"titre": tache.titre, "date_echeance": tache.date_echeance},
    )
    db.delete(tache)
    db.commit()
