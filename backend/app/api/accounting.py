"""
app/api/accounting.py

Routes de consultation et validation des écritures comptables.
Validate/reject/saisie/update : voir rôles autorisés ci-dessous.

CORRECTIF (rôle) : ADMIN_CABINET ajouté aux rôles autorisés sur
validate/reject -- absent avant, ce qui causait un 403 silencieux pour
tout compte admin (le compte de test créé par create_first_user.py a
précisément ce rôle).

AJOUT (tableau comptable complet) : list_entries/get_entry joignent
désormais Document (pour nom_fichier_document) -- alimente le lien de
consultation du fichier source à côté de chaque ligne.

AJOUT (registre trimestriel) : get_registre accepte soit 'mois' (un
mois unique, comportement historique) soit 'trimestre' (1-4, somme des
3 mois correspondants) -- utile pour les déclarations TVA trimestrielles
marocaines.

AJOUT (saisie Topaze) : route dédiée pour basculer le statut "saisi
dans le logiciel comptable externe", indépendant du statut_validation.

AJOUT (correction manuelle) : route PATCH /entries/{entry_id} pour
permettre au comptable de corriger manuellement les champs d'une écriture.
"""
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import RoleEnum, StatutValidationEnum
from app.models.user import User
from app.schemas.ecriture import EcritureOut, EcritureUpdate
from app.schemas.registre import RegistreOut

router = APIRouter(prefix="/accounting", tags=["accounting"])

_ROLES_VALIDATION = (RoleEnum.ADMIN_CABINET, RoleEnum.EXPERT_COMPTABLE, RoleEnum.CHEF_MISSION)


@router.get("/entries", response_model=list[EcritureOut])
def list_entries(
    entreprise_id: uuid.UUID | None = Query(default=None),
    statut_validation: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(EcritureComptable, Document.nom_fichier_original)
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(EcritureComptable.cabinet_id == current_user.cabinet_id)
    )
    if entreprise_id is not None:
        query = query.where(EcritureComptable.entreprise_id == entreprise_id)
    if statut_validation is not None:
        query = query.where(EcritureComptable.statut_validation == statut_validation)
    query = query.order_by(EcritureComptable.created_at.desc())

    resultats = db.execute(query).all()

    sortie: list[EcritureOut] = []
    for ecriture, nom_fichier in resultats:
        item = EcritureOut.model_validate(ecriture)
        item.nom_fichier_document = nom_fichier
        sortie.append(item)
    return sortie


@router.get("/entries/{entry_id}", response_model=EcritureOut)
def get_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resultat = db.execute(
        select(EcritureComptable, Document.nom_fichier_original)
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(
            EcritureComptable.id == entry_id,
            EcritureComptable.cabinet_id == current_user.cabinet_id,
        )
    ).first()
    if resultat is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    ecriture, nom_fichier = resultat
    item = EcritureOut.model_validate(ecriture)
    item.nom_fichier_document = nom_fichier
    return item


@router.patch("/entries/{entry_id}/validate", response_model=EcritureOut)
def validate_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    entry = db.query(EcritureComptable).filter(
        EcritureComptable.id == entry_id,
        EcritureComptable.cabinet_id == current_user.cabinet_id,
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    entry.statut_validation = StatutValidationEnum.VALIDE
    entry.validated_by = current_user.id
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/entries/{entry_id}/reject", response_model=EcritureOut)
def reject_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    entry = db.query(EcritureComptable).filter(
        EcritureComptable.id == entry_id,
        EcritureComptable.cabinet_id == current_user.cabinet_id,
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    entry.statut_validation = StatutValidationEnum.REJETE
    entry.validated_by = current_user.id
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/entries/{entry_id}/saisie", response_model=EcritureOut)
def toggle_saisie_topaze(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bascule le statut 'saisi dans Topaze' d'une écriture -- accessible
    à tout utilisateur du cabinet (tâche opérationnelle courante, pas
    réservée aux rôles de validation comptable)."""
    entry = db.query(EcritureComptable).filter(
        EcritureComptable.id == entry_id,
        EcritureComptable.cabinet_id == current_user.cabinet_id,
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    entry.saisie_topaze = not entry.saisie_topaze
    db.commit()
    db.refresh(entry)
    return entry


@router.patch("/entries/{entry_id}", response_model=EcritureOut)
def update_entry(
    entry_id: uuid.UUID,
    payload: EcritureUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    """Correction manuelle d'une écriture par le comptable (bouton
    'Corriger' du frontend). Ne touche que les champs fournis --
    exclude_unset=True évite d'écraser les autres avec None."""
    entry = db.query(EcritureComptable).filter(
        EcritureComptable.id == entry_id,
        EcritureComptable.cabinet_id == current_user.cabinet_id,
    ).first()
    if entry is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    donnees = payload.model_dump(exclude_unset=True)
    for champ, valeur in donnees.items():
        setattr(entry, champ, valeur)

    # Une correction manuelle repasse l'écriture en "à vérifier" --
    # elle vient d'être modifiée à la main, elle ne doit pas rester
    # "validée" sans qu'un humain la revoie une seconde fois.
    if entry.statut_validation == StatutValidationEnum.VALIDE:
        entry.statut_validation = StatutValidationEnum.A_VERIFIER

    db.commit()
    db.refresh(entry)
    return entry


@router.get("/registers", response_model=RegistreOut)
def get_registre(
    entreprise_id: uuid.UUID = Query(...),
    categorie: str = Query(...),
    annee: int = Query(...),
    mois: int | None = Query(default=None),
    trimestre: int | None = Query(default=None, ge=1, le=4),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Calcule un registre dynamique : écritures VALIDEES d'une entreprise,
    pour une catégorie/année données, filtrées soit par MOIS unique,
    soit par TRIMESTRE (1=jan-mar, 2=avr-juin, 3=juil-sept, 4=oct-déc).
    Exactement un des deux doit être fourni.
    """
    if (mois is None) == (trimestre is None):
        raise HTTPException(
            status_code=400,
            detail="Fournir soit 'mois' soit 'trimestre' (exclusif l'un de l'autre).",
        )

    if trimestre is not None:
        mois_cibles = [(trimestre - 1) * 3 + 1, (trimestre - 1) * 3 + 2, (trimestre - 1) * 3 + 3]
    else:
        mois_cibles = [mois]

    query = (
        select(EcritureComptable, Document.nom_fichier_original)
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(
            EcritureComptable.cabinet_id == current_user.cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            Document.categorie == categorie,
            Document.annee == annee,
            Document.mois.in_(mois_cibles),
        )
        .order_by(EcritureComptable.date_piece)
    )
    resultats = db.execute(query).all()

    lignes: list[EcritureOut] = []
    for ecriture, nom_fichier in resultats:
        item = EcritureOut.model_validate(ecriture)
        item.nom_fichier_document = nom_fichier
        lignes.append(item)

    total_ht = sum((l.montant_ht for l in lignes), Decimal("0.00"))
    total_tva = sum((l.montant_tva for l in lignes), Decimal("0.00"))
    total_ttc = sum((l.montant_ttc for l in lignes), Decimal("0.00"))

    return RegistreOut(
        categorie=categorie,
        entreprise_id=entreprise_id,
        annee=annee,
        mois=mois or mois_cibles[0],
        nombre=len(lignes),
        total_ht=total_ht,
        total_tva=total_tva,
        total_ttc=total_ttc,
        lignes=lignes,
    )