"""
app/api/dashboard.py

Route du tableau de bord (Phase 6). Un seul endpoint qui agrège tout ce
qui est nécessaire à l'écran d'accueil décisionnel : compteurs de
documents par statut, compteurs d'écritures par statut de validation,
TVA collectée/déductible/nette, nombre d'entreprises.

Tout est filtré sur cabinet_id de l'utilisateur connecté (même règle de
sécurité que partout ailleurs dans le projet).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import StatutDocumentEnum, StatutValidationEnum, TypeEcritureEnum
from app.schemas.dashboard import DashboardOut, DocumentsParStatut, EcrituresParStatutValidation

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _compter_documents_par_statut(db: Session, cabinet_id) -> DocumentsParStatut:
    """
    Une seule requête groupée par statut, plutôt que 5 requêtes
    séparées -- plus efficace pour Postgres.
    """
    resultats = db.execute(
        select(Document.statut, func.count(Document.id))
        .where(Document.cabinet_id == cabinet_id)
        .group_by(Document.statut)
    ).all()

    compteurs = {statut.value: 0 for statut in StatutDocumentEnum}
    for statut, nombre in resultats:
        compteurs[statut.value] = nombre

    return DocumentsParStatut(
        en_attente=compteurs[StatutDocumentEnum.EN_ATTENTE.value],
        en_traitement=compteurs[StatutDocumentEnum.EN_TRAITEMENT.value],
        traite=compteurs[StatutDocumentEnum.TRAITE.value],
        valide=compteurs[StatutDocumentEnum.VALIDE.value],
        erreur=compteurs[StatutDocumentEnum.ERREUR.value],
    )


def _compter_ecritures_par_statut(db: Session, cabinet_id) -> EcrituresParStatutValidation:
    resultats = db.execute(
        select(EcritureComptable.statut_validation, func.count(EcritureComptable.id))
        .where(EcritureComptable.cabinet_id == cabinet_id)
        .group_by(EcritureComptable.statut_validation)
    ).all()

    compteurs = {statut.value: 0 for statut in StatutValidationEnum}
    for statut, nombre in resultats:
        compteurs[statut.value] = nombre

    return EcrituresParStatutValidation(
        brouillon=compteurs[StatutValidationEnum.BROUILLON.value],
        a_verifier=compteurs[StatutValidationEnum.A_VERIFIER.value],
        valide=compteurs[StatutValidationEnum.VALIDE.value],
        rejete=compteurs[StatutValidationEnum.REJETE.value],
    )


def _calculer_tva(db: Session, cabinet_id) -> tuple[Decimal, Decimal, Decimal]:
    """
    TVA collectée = somme des montant_tva des écritures VALIDEES de
    type VENTE. TVA déductible = idem pour type ACHAT. TVA nette =
    collectée - déductible (peut être négative, c'est un cas normal
    en comptabilité : crédit de TVA).
    """
    tva_collectee = db.execute(
        select(func.coalesce(func.sum(EcritureComptable.montant_tva), 0)).where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            EcritureComptable.type_ecriture == TypeEcritureEnum.VENTE,
        )
    ).scalar_one()

    tva_deductible = db.execute(
        select(func.coalesce(func.sum(EcritureComptable.montant_tva), 0)).where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            EcritureComptable.type_ecriture == TypeEcritureEnum.ACHAT,
        )
    ).scalar_one()

    tva_collectee = Decimal(tva_collectee)
    tva_deductible = Decimal(tva_deductible)
    return tva_collectee, tva_deductible, tva_collectee - tva_deductible


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cabinet_id = current_user.cabinet_id

    documents_par_statut = _compter_documents_par_statut(db, cabinet_id)
    total_documents = sum(documents_par_statut.model_dump().values())

    ecritures_par_statut = _compter_ecritures_par_statut(db, cabinet_id)
    total_ecritures = sum(ecritures_par_statut.model_dump().values())

    tva_collectee, tva_deductible, tva_nette = _calculer_tva(db, cabinet_id)

    total_entreprises = db.execute(
        select(func.count(Entreprise.id)).where(Entreprise.cabinet_id == cabinet_id)
    ).scalar_one()

    return DashboardOut(
        total_documents=total_documents,
        documents_par_statut=documents_par_statut,
        total_ecritures=total_ecritures,
        ecritures_par_statut=ecritures_par_statut,
        tva_collectee=tva_collectee,
        tva_deductible=tva_deductible,
        tva_nette=tva_nette,
        total_entreprises=total_entreprises,
    )