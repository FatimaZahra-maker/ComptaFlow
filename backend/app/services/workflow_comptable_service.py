"""Contrôles déterministes et transitions du workflow pré-comptable Topaze."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import PeriodeComptableVerrouilleeError
from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import StatutDocumentEnum, StatutValidationEnum, TypeEcritureEnum
from app.models.ligne_comptable import LigneComptable
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.models.user import User
from app.models.workflow_comptable import AnomalieComptable, PeriodeTravail
from app.services import audit_service, ligne_comptable_service

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
STATUTS_INCLUS_ETATS = {
    StatutValidationEnum.PRETE_TOPAZE,
    StatutValidationEnum.SAISIE_TOPAZE,
    StatutValidationEnum.VALIDE,  # compatibilité historique
}


def _value(value: object | None) -> str:
    return value.value if hasattr(value, "value") else str(value or "")


def _anomaly(kind: str, message: str, field: str | None = None, value: object | None = None) -> dict:
    return {
        "type": kind,
        "gravite": "bloquante",
        "message": message,
        "champ": field,
        "valeur": None if value is None else str(value),
    }


def periode_verrouillee(
    db: Session, *, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID, target_date: date | None
) -> bool:
    if target_date is None:
        return False
    return db.execute(
        select(PeriodeTravail.id).where(
            PeriodeTravail.cabinet_id == cabinet_id,
            PeriodeTravail.entreprise_id == entreprise_id,
            PeriodeTravail.verrouillee.is_(True),
            PeriodeTravail.periode_debut <= target_date,
            PeriodeTravail.periode_fin >= target_date,
        )
    ).scalar_one_or_none() is not None


def intervalle_verrouille(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    periode_debut: date,
    periode_fin: date,
) -> bool:
    """Indique si l'intervalle demandé chevauche au moins une période verrouillée."""
    if periode_fin < periode_debut:
        raise ValueError("La date de fin doit être postérieure ou égale à la date de début.")
    return db.execute(
        select(PeriodeTravail.id).where(
            PeriodeTravail.cabinet_id == cabinet_id,
            PeriodeTravail.entreprise_id == entreprise_id,
            PeriodeTravail.verrouillee.is_(True),
            PeriodeTravail.periode_debut <= periode_fin,
            PeriodeTravail.periode_fin >= periode_debut,
        )
    ).scalar_one_or_none() is not None


def verifier_date_modifiable(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID | None,
    target_date: date | None,
) -> None:
    """Point de contrôle commun avant toute mutation datée."""
    if entreprise_id is None or target_date is None:
        return
    if periode_verrouillee(
        db,
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        target_date=target_date,
    ):
        raise PeriodeComptableVerrouilleeError()


def verifier_dates_modifiables(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID | None,
    target_dates: list[date | None] | tuple[date | None, ...] | set[date | None],
) -> None:
    """Vérifie plusieurs dates avant une mutation atomique multi-objets."""
    for target_date in {item for item in target_dates if item is not None}:
        verifier_date_modifiable(
            db,
            cabinet_id=cabinet_id,
            entreprise_id=entreprise_id,
            target_date=target_date,
        )


def verifier_intervalle_modifiable(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    periode_debut: date,
    periode_fin: date,
) -> None:
    """Refuse une mutation qui porte sur un intervalle chevauchant un verrou."""
    if intervalle_verrouille(
        db,
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        periode_debut=periode_debut,
        periode_fin=periode_fin,
    ):
        raise PeriodeComptableVerrouilleeError()


def verifier_entreprise_modifiable(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
) -> None:
    """Bloque une reconstruction globale si l'entreprise contient un verrou."""
    locked = db.execute(
        select(PeriodeTravail.id).where(
            PeriodeTravail.cabinet_id == cabinet_id,
            PeriodeTravail.entreprise_id == entreprise_id,
            PeriodeTravail.verrouillee.is_(True),
        )
    ).scalar_one_or_none()
    if locked is not None:
        raise PeriodeComptableVerrouilleeError(
            "Une période comptable de cette entreprise est verrouillée ; la reconstruction globale est interdite."
        )


def date_document(document: Document) -> date | None:
    """Résout la date comptable connue d'un document sans date fictive."""
    if document.annee is not None and document.mois is not None:
        return date(document.annee, document.mois, 1)
    raw = document.donnees_extraites if isinstance(document.donnees_extraites, dict) else {}
    value = raw.get("date_piece")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value not in (None, ""):
        text = str(value).strip()
        for date_format in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(text[:10], date_format).date()
            except ValueError:
                continue
    return None


def verifier_document_modifiable(db: Session, document: Document) -> None:
    """Protège un document ainsi que ses écritures et mouvements associés."""
    entries = db.execute(select(EcritureComptable).where(
        EcritureComptable.cabinet_id == document.cabinet_id,
        EcritureComptable.document_id == document.id,
    )).scalars().all()
    movements = db.execute(select(MouvementBancaire).where(
        MouvementBancaire.cabinet_id == document.cabinet_id,
        MouvementBancaire.document_id == document.id,
    )).scalars().all()
    for entry in entries:
        verifier_periode_modifiable(db, entry)
    for movement in movements:
        verifier_mouvement_modifiable(db, movement)
    verifier_date_modifiable(
        db,
        cabinet_id=document.cabinet_id,
        entreprise_id=document.entreprise_id,
        target_date=date_document(document),
    )


def verifier_mouvement_modifiable(
    db: Session,
    mouvement: MouvementBancaire,
    *,
    ecritures_supplementaires: tuple[EcritureComptable, ...] = (),
    nouvelle_date: date | None = None,
) -> None:
    """Protège un mouvement et les pré-écritures touchées par son rapprochement."""
    verifier_dates_modifiables(
        db,
        cabinet_id=mouvement.cabinet_id,
        entreprise_id=mouvement.entreprise_id,
        target_dates=(mouvement.date_operation, nouvelle_date),
    )
    entry_ids = set(db.execute(select(RapprochementBancaireAllocation.ecriture_id).where(
        RapprochementBancaireAllocation.cabinet_id == mouvement.cabinet_id,
        RapprochementBancaireAllocation.entreprise_id == mouvement.entreprise_id,
        RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
    )).scalars().all())
    if mouvement.ecriture_rapprochee_id is not None:
        entry_ids.add(mouvement.ecriture_rapprochee_id)
    linked_entries = list(ecritures_supplementaires)
    if entry_ids:
        linked_entries.extend(db.execute(select(EcritureComptable).where(
            EcritureComptable.id.in_(entry_ids),
            EcritureComptable.cabinet_id == mouvement.cabinet_id,
            EcritureComptable.entreprise_id == mouvement.entreprise_id,
        )).scalars().all())
    for entry in {item.id: item for item in linked_entries}.values():
        verifier_periode_modifiable(db, entry)


def verifier_periode_modifiable(db: Session, ecriture: EcritureComptable) -> None:
    verifier_date_modifiable(
        db,
        cabinet_id=ecriture.cabinet_id,
        entreprise_id=ecriture.entreprise_id,
        target_date=ecriture.date_piece,
    )


def controler_ecriture(
    db: Session, ecriture: EcritureComptable, document: Document | None = None
) -> tuple[list[dict], ligne_comptable_service.GenerationLignesResultat]:
    anomalies: list[dict] = []
    kind = _value(ecriture.type_ecriture)
    if ecriture.entreprise_id is None:
        anomalies.append(_anomaly("entreprise_absente", "Entreprise non identifiée.", "entreprise_id"))
    if not (ecriture.tiers or "").strip() and kind in {"achat", "vente"}:
        anomalies.append(_anomaly("tiers_absent", "Fournisseur ou client non identifié.", "tiers"))
    if ecriture.date_piece is None:
        anomalies.append(_anomaly("date_absente", "Date de pièce obligatoire absente.", "date_piece"))
    elif ecriture.date_piece > date.today():
        anomalies.append(_anomaly("date_future", "La date de pièce est située dans le futur.", "date_piece", ecriture.date_piece))

    ht = ecriture.montant_ht
    tva = ecriture.montant_tva
    ttc = ecriture.montant_ttc
    if ht is not None and tva is not None and ttc is not None:
        ecart = (Decimal(ht) + Decimal(tva) - Decimal(ttc)).quantize(MONEY)
        if abs(ecart) > MONEY:
            anomalies.append(_anomaly(
                "montants_incoherents", "HT + TVA ne correspond pas au TTC extrait.",
                "montant_ttc", f"écart {ecart}",
            ))
    if tva is not None and Decimal(tva) > ZERO and ecriture.taux_tva is None:
        anomalies.append(_anomaly("taux_tva_absent", "Le taux de TVA est absent ou inconnu.", "taux_tva"))

    required_accounts = {
        "compte_tiers": ecriture.compte_tiers,
        "compte_ht": ecriture.compte_ht,
    }
    if tva is not None and Decimal(tva) > ZERO:
        required_accounts["compte_tva"] = ecriture.compte_tva
    account_numbers = {str(value) for value in required_accounts.values() if value}
    rows = db.execute(
        select(CompteComptableEntreprise).where(
            CompteComptableEntreprise.cabinet_id == ecriture.cabinet_id,
            CompteComptableEntreprise.entreprise_id == ecriture.entreprise_id,
            CompteComptableEntreprise.numero_compte.in_(account_numbers),
            CompteComptableEntreprise.is_active.is_(True),
        )
    ).scalars().all() if account_numbers else []
    plan = {row.numero_compte: row for row in rows}
    for field, number in required_accounts.items():
        if not number:
            anomalies.append(_anomaly("compte_manquant", f"Le {field.replace('_', ' ')} est introuvable.", field))
        elif str(number) not in plan:
            anomalies.append(_anomaly(
                "compte_hors_plan", "Le compte proposé n'existe pas dans le plan comptable actif de l'entreprise.",
                field, number,
            ))
    if ecriture.compte_tiers and ecriture.compte_tiers in plan:
        expected = "fournisseur" if kind == TypeEcritureEnum.ACHAT.value else "client"
        if kind in {"achat", "vente"} and plan[ecriture.compte_tiers].type_usage != expected:
            anomalies.append(_anomaly(
                "compte_tiers_incompatible", f"Le compte tiers doit être un compte {expected}.",
                "compte_tiers", ecriture.compte_tiers,
            ))
    if ecriture.compte_tva and ecriture.compte_tva in plan and plan[ecriture.compte_tva].type_usage != "tva":
        anomalies.append(_anomaly("compte_tva_incompatible", "Le compte TVA sélectionné n'est pas typé TVA.", "compte_tva", ecriture.compte_tva))
    if ecriture.compte_ht and ecriture.compte_ht in plan and plan[ecriture.compte_ht].type_usage != "ht":
        anomalies.append(_anomaly("compte_ht_incompatible", "Le compte HT sélectionné n'est pas typé HT.", "compte_ht", ecriture.compte_ht))

    if ecriture.doublon_potentiel_id is not None:
        anomalies.append(_anomaly("doublon_potentiel", "Cette facture ressemble à une écriture déjà enregistrée.", "doublon_potentiel_id", ecriture.doublon_potentiel_id))
    if document is not None:
        raw = document.donnees_extraites if isinstance(document.donnees_extraites, dict) else {}
        confidence = raw.get("confiance_globale", raw.get("confidence"))
        try:
            if confidence is not None and Decimal(str(confidence)) < Decimal("0.70"):
                anomalies.append(_anomaly("confiance_insuffisante", "La confiance OCR/IA est insuffisante.", "confiance_globale", confidence))
        except Exception:
            anomalies.append(_anomaly("confiance_invalide", "La confiance OCR/IA n'est pas exploitable.", "confiance_globale", confidence))
        if document.statut == StatutDocumentEnum.ERREUR:
            anomalies.append(_anomaly("document_en_erreur", "Le traitement du document source est en erreur.", "statut"))

    generation = ligne_comptable_service.synchroniser_lignes_facture(db, ecriture)
    for reason in generation.raisons:
        anomalies.append(_anomaly("ecriture_incomplete", reason))
    return anomalies, generation


def _persist_anomalies(
    db: Session, ecriture: EcritureComptable, document: Document | None,
    anomalies: list[dict], user: User | None,
) -> None:
    now = datetime.now(timezone.utc)
    active = db.execute(
        select(AnomalieComptable).where(
            AnomalieComptable.cabinet_id == ecriture.cabinet_id,
            AnomalieComptable.entreprise_id == ecriture.entreprise_id,
            AnomalieComptable.ecriture_id == ecriture.id,
            AnomalieComptable.resolved_at.is_(None),
        )
    ).scalars().all()
    for item in active:
        item.resolved_at = now
        item.resolved_by = user.id if user else None
    for item in anomalies:
        db.add(AnomalieComptable(
            cabinet_id=ecriture.cabinet_id,
            entreprise_id=ecriture.entreprise_id,
            document_id=document.id if document else ecriture.document_id,
            ecriture_id=ecriture.id,
            type_anomalie=item["type"], gravite=item["gravite"], message=item["message"],
            champ_concerne=item["champ"], valeur_detectee=item["valeur"], detected_at=now,
        ))


def controler_et_transitionner(
    db: Session,
    ecriture: EcritureComptable,
    *,
    document: Document | None = None,
    user: User | None = None,
    actor_type: str = "system",
) -> list[dict]:
    """Relance tous les contrôles et applique PRETE_TOPAZE ou A_VERIFIER."""
    previous = _value(ecriture.statut_validation)
    ecriture.statut_validation = StatutValidationEnum.CALCUL_EN_COURS
    db.flush()
    anomalies, generation = controler_ecriture(db, ecriture, document)
    now = datetime.now(timezone.utc)
    if anomalies or not generation.complet:
        ecriture.statut_validation = StatutValidationEnum.A_VERIFIER
        ecriture.anomalie_detectee = True
        ecriture.anomalie_details = " | ".join(item["message"] for item in anomalies) or None
        ecriture.saisie_topaze = False
        ecriture.topaze_entered_at = None
        ecriture.topaze_entered_by = None
        if document is not None:
            document.statut = StatutDocumentEnum.TRAITE
            document.saisie_topaze = False
    else:
        ecriture.statut_validation = StatutValidationEnum.PRETE_TOPAZE
        ecriture.anomalie_detectee = False
        ecriture.anomalie_details = None
        ecriture.saisie_topaze = False
        ecriture.ready_for_topaze_at = ecriture.ready_for_topaze_at or now
        if document is not None:
            document.statut = StatutDocumentEnum.VALIDE
            document.saisie_topaze = False
    db.execute(
        LigneComptable.__table__.update()
        .where(LigneComptable.ecriture_id == ecriture.id)
        .values(est_validee=ecriture.statut_validation == StatutValidationEnum.PRETE_TOPAZE)
    )
    _persist_anomalies(db, ecriture, document, anomalies, user)
    current = _value(ecriture.statut_validation)
    if current != previous:
        audit_service.enregistrer(
            db, user=user, cabinet_id=ecriture.cabinet_id,
            action=("ENTRY_READY_FOR_TOPAZE" if current == "prete_topaze" else "ENTRY_REQUIRES_REVIEW"),
            entreprise_id=ecriture.entreprise_id, resource_type="ecriture_comptable", resource_id=ecriture.id,
            description=("Contrôles automatiques réussis : pré-écriture prête pour Topaze." if current == "prete_topaze" else "Contrôles automatiques : pré-écriture à vérifier."),
            avant={"statut_validation": previous},
            apres={"statut_validation": current, "anomalies": [item["type"] for item in anomalies]},
            actor_type=actor_type,
        )
    return anomalies
