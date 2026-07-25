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
from sqlalchemy import select, extract
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import RoleEnum, StatutValidationEnum
from app.models.user import User
from app.schemas.ecriture import EcritureOut, EcritureUpdate
from app.schemas.registre import RegistreOut, TvaAnnuelleOut, TvaMensuelle

router = APIRouter(prefix="/accounting", tags=["accounting"])

# Définition des rôles autorisés à valider, rejeter ou modifier les écritures comptables
_ROLES_VALIDATION = (RoleEnum.ADMIN_CABINET, RoleEnum.EXPERT_COMPTABLE, RoleEnum.CHEF_MISSION)


@router.get("/entries", response_model=list[EcritureOut])
def list_entries(
    entreprise_id: uuid.UUID | None = Query(default=None),
    statut_validation: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Récupère la liste des écritures comptables du cabinet de l'utilisateur connecté.
    
    Permet de filtrer par entreprise spécifique et/ou par statut de validation 
    (ex: VALIDE, REJETE, A_VERIFIER). Joint la table Document pour inclure 
    le nom du fichier d'origine lié à chaque écriture.
    """
    # Construction de la requête de base
    query = (
        select(EcritureComptable, Document.nom_fichier_original)
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(EcritureComptable.cabinet_id == current_user.cabinet_id)
    )
    
    # Application des filtres optionnels
    if entreprise_id is not None:
        query = query.where(EcritureComptable.entreprise_id == entreprise_id)
    if statut_validation is not None:
        query = query.where(EcritureComptable.statut_validation == statut_validation)
        
    # Tri par date de création, du plus récent au plus ancien
    query = query.order_by(EcritureComptable.created_at.desc())

    resultats = db.execute(query).all()

    # Formatage des résultats pour correspondre au schéma de sortie
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
    """
    Récupère les détails d'une seule écriture comptable spécifique via son ID.
    
    Vérifie également que cette écriture appartient bien au cabinet de 
    l'utilisateur connecté pour des raisons de sécurité.
    """
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
    """
    Valide une écriture comptable (passe son statut à VALIDE).
    
    L'accès est restreint aux rôles de supervision (Admin, Expert-comptable, Chef de mission).
    Enregistre également l'ID de l'utilisateur ayant effectué la validation.
    """
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
    """
    Rejette une écriture comptable (passe son statut à REJETE).
    
    L'accès est restreint aux rôles de supervision. Utilisé lorsqu'une 
    anomalie est détectée sur l'écriture extraite.
    """
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
    """
    Bascule le statut 'saisi dans Topaze' (vrai/faux) d'une écriture.
    
    Accessible à tout utilisateur du cabinet car c'est une tâche 
    opérationnelle courante (marquer l'écriture comme étant exportée 
    ou re-saisie dans le logiciel comptable tiers).
    """
    entry = db.query(EcritureComptable).filter(
        EcritureComptable.id == entry_id,
        EcritureComptable.cabinet_id == current_user.cabinet_id,
    ).first()
    
    if entry is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    # Inverse la valeur booléenne actuelle (True devient False, False devient True)
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
    """
    Correction manuelle d'une écriture par un rôle autorisé.
    
    Ne met à jour que les champs fournis dans la requête. Si l'écriture 
    avait déjà été validée, elle est automatiquement repassée au statut 
    'A_VERIFIER' pour imposer un nouveau cycle de validation après modification.
    """
    entry = db.query(EcritureComptable).filter(
        EcritureComptable.id == entry_id,
        EcritureComptable.cabinet_id == current_user.cabinet_id,
    ).first()
    
    if entry is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    # exclude_unset=True garantit que seuls les champs explicitement envoyés sont modifiés
    donnees = payload.model_dump(exclude_unset=True)
    for champ, valeur in donnees.items():
        setattr(entry, champ, valeur)

    # Réinitialise la validation après modification manuelle
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
    Calcule un registre dynamique (achats, ventes, etc.) en sommant 
    les écritures VALIDÉES pour une période donnée.
    
    Fonctionnement au choix :
    - Par 'mois' (1-12) : retourne les données du mois ciblé.
    - Par 'trimestre' (1-4) : regroupe les données des 3 mois de ce trimestre.
    """
    # Validation stricte : on ne peut pas fournir les deux filtres temporels à la fois, ni aucun des deux
    if (mois is None) == (trimestre is None):
        raise HTTPException(
            status_code=400,
            detail="Fournir soit 'mois' soit 'trimestre' (exclusif l'un de l'autre).",
        )

    # Détermine la liste des mois à requêter selon qu'on demande un mois unique ou un trimestre
    if trimestre is not None:
        mois_cibles = [(trimestre - 1) * 3 + 1, (trimestre - 1) * 3 + 2, (trimestre - 1) * 3 + 3]
    else:
        mois_cibles = [mois]

    # Construit la requête sur les écritures validées de la période ciblée
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

    # Formate les résultats
    lignes: list[EcritureOut] = []
    for ecriture, nom_fichier in resultats:
        item = EcritureOut.model_validate(ecriture)
        item.nom_fichier_document = nom_fichier
        lignes.append(item)

    # Calcule les totaux globaux du registre avec protection contre les valeurs None
    total_ht = sum((l.montant_ht or Decimal("0.00") for l in lignes), Decimal("0.00"))
    total_tva = sum((l.montant_tva or Decimal("0.00") for l in lignes), Decimal("0.00"))
    total_ttc = sum((l.montant_ttc or Decimal("0.00") for l in lignes), Decimal("0.00"))

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


@router.get("/tva-mensuelle", response_model=TvaAnnuelleOut)
def get_tva_mensuelle(
    entreprise_id: uuid.UUID = Query(...),
    annee: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Ventile la TVA collectée, déductible et nette mois par mois, sur 
    l'ensemble d'une année donnée pour une entreprise.
    
    Règles de calcul basées uniquement sur les écritures VALIDÉES :
    - TVA collectée = Somme de la TVA sur les factures de VENTE.
    - TVA déductible = Somme de la TVA sur les factures d'ACHAT.
    - TVA nette = Collectée - Déductible.
    """
    # Extraction des données nécessaires regroupées et identifiées par mois
    lignes = db.execute(
        select(
            extract("month", EcritureComptable.date_piece).label("mois"),
            EcritureComptable.type_ecriture,
            EcritureComptable.montant_tva,
        )
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(
            EcritureComptable.cabinet_id == current_user.cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            Document.annee == annee,
            EcritureComptable.date_piece.isnot(None),
        )
    ).all()

    # Initialisation d'un dictionnaire avec tous les mois (1 à 12) à zéro
    par_mois: dict[int, dict[str, Decimal]] = {
        m: {"collectee": Decimal("0.00"), "deductible": Decimal("0.00"), "nombre": 0}
        for m in range(1, 13)
    }

    # Agrégation des montants par mois en fonction du type d'écriture (vente vs achat)
    for mois, type_ecriture, montant_tva in lignes:
        mois = int(mois)
        type_str = type_ecriture.value if hasattr(type_ecriture, "value") else str(type_ecriture)
        
        valeur_tva = montant_tva or Decimal("0.00")
        
        if type_str.lower() == "vente":
            par_mois[mois]["collectee"] += valeur_tva
        elif type_str.lower() == "achat":
            par_mois[mois]["deductible"] += valeur_tva
            
        par_mois[mois]["nombre"] += 1

    # Formatage des totaux mensuels
    mensualites = [
        TvaMensuelle(
            mois=m,
            annee=annee,
            tva_collectee=str(par_mois[m]["collectee"]),
            tva_deductible=str(par_mois[m]["deductible"]),
            tva_nette=str(par_mois[m]["collectee"] - par_mois[m]["deductible"]),
            nombre_ecritures=par_mois[m]["nombre"],
        )
        for m in range(1, 13)
    ]

    # Calcul des totaux annuels globaux
    total_collectee = sum((Decimal(m.tva_collectee) for m in mensualites), Decimal("0.00"))
    total_deductible = sum((Decimal(m.tva_deductible) for m in mensualites), Decimal("0.00"))

    return TvaAnnuelleOut(
        entreprise_id=entreprise_id,
        annee=annee,
        mensualites=mensualites,
        total_tva_collectee=str(total_collectee),
        total_tva_deductible=str(total_deductible),
        total_tva_nette=str(total_collectee - total_deductible),
    )