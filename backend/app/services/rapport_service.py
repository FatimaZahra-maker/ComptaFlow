"""
app/services/rapport_service.py

Calcule un rapport de synthèse pour une entreprise, sur une période
donnée (année entière ou un mois précis). Ne stocke rien : tout est
recalculé à la demande à partir des documents/écritures existants,
même principe que les registres (Phase 5) et le tableau de bord
(Phase 6) -- une seule source de vérité, jamais de duplication de
données déjà en base.
"""
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import StatutDocumentEnum, StatutValidationEnum, TypeEcritureEnum
from app.schemas.rapport import RapportOut


# Construit le rapport de synthèse pour une entreprise et une période
# (annee obligatoire, mois optionnel -- si absent, couvre l'année
# entière). Regroupe des comptages déjà utilisés ailleurs (dashboard,
# registres) en une seule requête cohérente.
def generer_rapport(db: Session, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID, annee: int, mois: int | None) -> RapportOut:
    entreprise = db.query(Entreprise).filter(
        Entreprise.id == entreprise_id, Entreprise.cabinet_id == cabinet_id,
    ).first()
    if entreprise is None:
        raise ValueError("Entreprise introuvable.")

    filtre_periode = [Document.annee == annee]
    if mois is not None:
        filtre_periode.append(Document.mois == mois)

    # --- Comptages documents ---
    nombre_documents = db.execute(
        select(func.count(Document.id)).where(
            Document.cabinet_id == cabinet_id, Document.entreprise_id == entreprise_id, *filtre_periode,
        )
    ).scalar_one()

    nombre_documents_erreur = db.execute(
        select(func.count(Document.id)).where(
            Document.cabinet_id == cabinet_id, Document.entreprise_id == entreprise_id,
            Document.statut == StatutDocumentEnum.ERREUR, *filtre_periode,
        )
    ).scalar_one()

    # --- Comptages écritures (jointes au document pour filtrer par période) ---
    requete_ecritures = (
        select(EcritureComptable)
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(EcritureComptable.cabinet_id == cabinet_id, EcritureComptable.entreprise_id == entreprise_id, *filtre_periode)
    )
    ecritures = db.execute(requete_ecritures).scalars().all()

    nombre_validees = sum(1 for e in ecritures if e.statut_validation == StatutValidationEnum.VALIDE)
    nombre_a_verifier = sum(1 for e in ecritures if e.statut_validation == StatutValidationEnum.A_VERIFIER)
    nombre_anomalies = sum(1 for e in ecritures if e.anomalie_detectee)

    # --- Totaux financiers, uniquement sur les écritures VALIDÉES ---
    validees = [e for e in ecritures if e.statut_validation == StatutValidationEnum.VALIDE]
    total_achats_ht = sum((e.montant_ht for e in validees if e.type_ecriture == TypeEcritureEnum.ACHAT), Decimal("0.00"))
    total_ventes_ht = sum((e.montant_ht for e in validees if e.type_ecriture == TypeEcritureEnum.VENTE), Decimal("0.00"))
    tva_collectee = sum((e.montant_tva for e in validees if e.type_ecriture == TypeEcritureEnum.VENTE), Decimal("0.00"))
    tva_deductible = sum((e.montant_tva for e in validees if e.type_ecriture == TypeEcritureEnum.ACHAT), Decimal("0.00"))

    return RapportOut(
        entreprise_id=entreprise_id,
        entreprise_nom=entreprise.nom,
        annee=annee,
        mois=mois,
        nombre_documents=nombre_documents,
        nombre_documents_erreur=nombre_documents_erreur,
        nombre_ecritures_validees=nombre_validees,
        nombre_ecritures_a_verifier=nombre_a_verifier,
        nombre_anomalies=nombre_anomalies,
        total_achats_ht=total_achats_ht,
        total_ventes_ht=total_ventes_ht,
        tva_collectee=tva_collectee,
        tva_deductible=tva_deductible,
        tva_nette=tva_collectee - tva_deductible,
    )