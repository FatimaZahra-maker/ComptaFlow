"""API de consultation et de validation des données comptables.

Cette API alimente les pages Écritures, Achats, Ventes, Banque, Registres
et TVA mensuelle. Elle ne modifie pas le pipeline OCR/IA.
"""

import uuid
from datetime import date as date_type
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, cast, extract, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import (
    CategorieDocumentEnum,
    RoleEnum,
    StatutDocumentEnum,
    StatutValidationEnum,
    TypeEcritureEnum,
    TypeMouvementBancaireEnum,
)
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.compte_bancaire_entreprise import CompteBancaireEntreprise
from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.models.user import User
from app.schemas.ecriture import EcritureOut, EcritureUpdate
from app.schemas.ledger import BalanceOut, GrandLivreOut, ReconstructionLedgerOut
from app.schemas.cpc import CpcCompteDetailOut, CpcOut, CpcV2Out
from app.schemas.bilan import BilanCompteDetailOut, BilanOut, BilanV2Out
from app.schemas.controls import PreClotureOut
from app.schemas.mouvement_bancaire import (
    AllocationRapprochementBatch,
    AllocationRapprochementOut,
    MouvementBancaireListeOut,
    MouvementBancaireOut,
    MouvementBancaireUpdate,
    RapprochementCandidatOut,
    VirementInterneCandidatOut,
)
from app.schemas.compte_bancaire import (
    CompteBancaireCreate,
    CompteBancaireOut,
    CompteBancaireUpdate,
)
from app.services import rapprochement_bancaire_service
from app.services import audit_service
from app.services import bank_account_service
from app.services import ligne_comptable_service
from app.services import tva_comptable_service
from app.services import cpc_service
from app.services import bilan_service
from app.services import precloture_service

from app.schemas.registre import (
    RegistreOptionOut,
    RegistreOut,
    TvaAnnuelleOut,
    TvaCompteDetailOut,
    TvaMensuelle,
)

router = APIRouter(prefix="/accounting", tags=["accounting"])

_ROLES_VALIDATION = (
    RoleEnum.ADMIN_CABINET,
    RoleEnum.EXPERT_COMPTABLE,
    RoleEnum.CHEF_MISSION,
)


def _period_expressions():
    """Utilise la période du document puis la date de pièce en secours."""
    year_from_date = cast(extract("year", EcritureComptable.date_piece), Integer)
    month_from_date = cast(extract("month", EcritureComptable.date_piece), Integer)
    return (
        func.coalesce(Document.annee, year_from_date),
        func.coalesce(Document.mois, month_from_date),
    )


def _decimal_json(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _date_json(value) -> date_type | None:
    if value is None or value == "":
        return None
    if isinstance(value, date_type):
        return value
    try:
        return date_type.fromisoformat(str(value))
    except ValueError:
        return None


def _to_ecriture_out(
    ecriture: EcritureComptable,
    document: Document,
    entreprise_nom: str | None,
) -> EcritureOut:
    item = EcritureOut.model_validate(ecriture)
    item.nom_fichier_document = document.nom_fichier_original
    item.entreprise_nom = entreprise_nom
    item.categorie_document = (
        document.categorie.value if document.categorie is not None else None
    )
    item.statut_document = (
        document.statut.value if hasattr(document.statut, "value") else str(document.statut)
    )

    fx = dict(document.donnees_extraites or {})
    item.devise_originale = fx.get("devise_originale") or fx.get("devise")
    item.montant_ht_devise = _decimal_json(fx.get("montant_ht_devise"))
    item.montant_tva_devise = _decimal_json(fx.get("montant_tva_devise"))
    item.montant_ttc_devise = _decimal_json(fx.get("montant_ttc_devise"))
    item.montant_ht_mad = _decimal_json(fx.get("montant_ht_mad"))
    item.montant_tva_mad = _decimal_json(fx.get("montant_tva_mad"))
    item.montant_ttc_mad = _decimal_json(fx.get("montant_ttc_mad"))
    item.date_cours_change = _date_json(fx.get("date_cours_change"))
    item.type_cours_change = fx.get("type_cours_change")
    item.taux_change = _decimal_json(fx.get("taux_change"))
    item.unite_cotation = fx.get("unite_cotation")
    item.source_cours_change = fx.get("source_cours_change")
    item.conversion_devise_statut = fx.get("conversion_devise_statut")
    return item


def _get_entry_or_404(
    db: Session,
    entry_id: uuid.UUID,
    cabinet_id: uuid.UUID,
) -> EcritureComptable:
    entry = db.execute(
        select(EcritureComptable).where(
            EcritureComptable.id == entry_id,
            EcritureComptable.cabinet_id == cabinet_id,
        )
    ).scalar_one_or_none()

    if entry is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    return entry


def _get_entry_output(
    db: Session,
    entry_id: uuid.UUID,
    cabinet_id: uuid.UUID,
) -> EcritureOut:
    result = db.execute(
        select(EcritureComptable, Document, Entreprise.nom)
        .join(Document, EcritureComptable.document_id == Document.id)
        .join(Entreprise, EcritureComptable.entreprise_id == Entreprise.id, isouter=True)
        .where(
            EcritureComptable.id == entry_id,
            EcritureComptable.cabinet_id == cabinet_id,
        )
    ).first()

    if result is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    entry, document, entreprise_nom = result
    return _to_ecriture_out(entry, document, entreprise_nom)


@router.get("/entries", response_model=list[EcritureOut])
def list_entries(
    entreprise_id: uuid.UUID | None = Query(default=None),
    statut_validation: StatutValidationEnum | None = Query(default=None),
    type_ecriture: TypeEcritureEnum | None = Query(default=None),
    categorie: CategorieDocumentEnum | None = Query(default=None),
    recherche: str | None = Query(default=None, max_length=150),
    annee: int | None = Query(default=None, ge=2000, le=2100),
    periodicite: str | None = Query(default=None),
    mois: int | None = Query(default=None, ge=1, le=12),
    trimestre: int | None = Query(default=None, ge=1, le=4),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Liste réelle des écritures avec les métadonnées du document source."""
    query = (
        select(EcritureComptable, Document, Entreprise.nom)
        .join(Document, EcritureComptable.document_id == Document.id)
        .join(Entreprise, EcritureComptable.entreprise_id == Entreprise.id, isouter=True)
        .where(EcritureComptable.cabinet_id == current_user.cabinet_id)
    )

    if entreprise_id is not None:
        query = query.where(EcritureComptable.entreprise_id == entreprise_id)
    if statut_validation is not None:
        query = query.where(EcritureComptable.statut_validation == statut_validation)
    if type_ecriture is not None:
        query = query.where(EcritureComptable.type_ecriture == type_ecriture)
    if categorie is not None:
        query = query.where(Document.categorie == categorie)

    # Filtre de période commun aux pages Écritures, Achats et Ventes.
    # La période du document est prioritaire; la date de pièce sert de secours.
    year_expression, month_expression = _period_expressions()
    if annee is not None:
        query = query.where(year_expression == annee)

    normalized_periodicity = (periodicite or "").strip().lower()
    if normalized_periodicity not in {"", "mensuelle", "trimestrielle", "annuelle"}:
        raise HTTPException(
            status_code=422,
            detail="Périodicité invalide. Valeurs: mensuelle, trimestrielle, annuelle.",
        )

    if normalized_periodicity == "mensuelle":
        if mois is None:
            raise HTTPException(status_code=422, detail="Le mois est obligatoire.")
        query = query.where(month_expression == mois)
    elif normalized_periodicity == "trimestrielle":
        if trimestre is None:
            raise HTTPException(status_code=422, detail="Le trimestre est obligatoire.")
        first_month = (trimestre - 1) * 3 + 1
        query = query.where(month_expression.between(first_month, first_month + 2))

    search_term = (recherche or "").strip()
    if search_term:
        pattern = f"%{search_term}%"
        query = query.where(
            or_(
                EcritureComptable.tiers.ilike(pattern),
                EcritureComptable.numero_piece.ilike(pattern),
                Document.nom_fichier_original.ilike(pattern),
                Entreprise.nom.ilike(pattern),
            )
        )

    rows = db.execute(
        query.order_by(
            EcritureComptable.date_piece.desc().nullslast(),
            EcritureComptable.created_at.desc(),
        )
    ).all()

    return [
        _to_ecriture_out(entry, document, entreprise_nom)
        for entry, document, entreprise_nom in rows
    ]


@router.get("/entries/{entry_id}", response_model=EcritureOut)
def get_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_entry_output(db, entry_id, current_user.cabinet_id)



def _mouvements_lies_a_ecriture(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    ecriture_id: uuid.UUID,
) -> list[MouvementBancaire]:
    allocation_ids = (
        select(RapprochementBancaireAllocation.mouvement_bancaire_id)
        .where(
            RapprochementBancaireAllocation.cabinet_id == cabinet_id,
            RapprochementBancaireAllocation.ecriture_id == ecriture_id,
            RapprochementBancaireAllocation.statut.in_(["propose", "automatique", "confirme"]),
        )
    )
    return db.execute(
        select(MouvementBancaire).where(
            MouvementBancaire.cabinet_id == cabinet_id,
            or_(
                MouvementBancaire.ecriture_rapprochee_id == ecriture_id,
                MouvementBancaire.id.in_(allocation_ids),
            ),
        )
    ).scalars().all()


def _allocation_outputs(
    db: Session,
    mouvement: MouvementBancaire,
) -> list[AllocationRapprochementOut]:
    rows = (
        db.query(RapprochementBancaireAllocation, EcritureComptable)
        .join(EcritureComptable, RapprochementBancaireAllocation.ecriture_id == EcritureComptable.id)
        .filter(
            RapprochementBancaireAllocation.cabinet_id == mouvement.cabinet_id,
            RapprochementBancaireAllocation.mouvement_bancaire_id == mouvement.id,
            RapprochementBancaireAllocation.statut.in_(["propose", "automatique", "confirme"]),
        )
        .order_by(RapprochementBancaireAllocation.created_at.asc())
        .all()
    )
    output: list[AllocationRapprochementOut] = []
    for allocation, entry in rows:
        remaining = rapprochement_bancaire_service.montant_restant_facture(
            db,
            entry,
            exclure_mouvement_id=None,
        )
        output.append(
            AllocationRapprochementOut(
                id=allocation.id,
                ecriture_id=entry.id,
                numero_piece=entry.numero_piece,
                date_piece=entry.date_piece,
                tiers=entry.tiers,
                type_ecriture=(entry.type_ecriture.value if hasattr(entry.type_ecriture, "value") else str(entry.type_ecriture)),
                montant_ttc=entry.montant_ttc,
                montant_affecte=allocation.montant_affecte,
                montant_devise_affecte=allocation.montant_devise_affecte,
                valeur_comptable_mad=allocation.valeur_comptable_mad,
                montant_reglement_mad=allocation.montant_reglement_mad,
                ecart_change_mad=allocation.ecart_change_mad,
                nature_ecart_change=allocation.nature_ecart_change,
                compte_ecart_change=allocation.compte_ecart_change,
                statut_ecart_change=allocation.statut_ecart_change,
                raison_ecart_change=allocation.raison_ecart_change,
                montant_restant_facture_apres=remaining,
                statut=allocation.statut,
                score=allocation.score,
                raison=allocation.raison,
            )
        )
    return output


def _validate_special_counterpart(
    db: Session,
    mouvement: MouvementBancaire,
) -> None:
    if mouvement.nature_operation in {"frais_bancaire", "acompte", "autre"}:
        if not mouvement.compte_contrepartie:
            return
        exists = db.execute(
            select(CompteComptableEntreprise.id).where(
                CompteComptableEntreprise.cabinet_id == mouvement.cabinet_id,
                CompteComptableEntreprise.entreprise_id == mouvement.entreprise_id,
                CompteComptableEntreprise.numero_compte == mouvement.compte_contrepartie,
                CompteComptableEntreprise.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(
                status_code=422,
                detail="Le compte de contrepartie doit exister dans le plan comptable exact de l'entreprise.",
            )

@router.patch("/entries/{entry_id}/validate", response_model=EcritureOut)
def validate_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    entry = _get_entry_or_404(db, entry_id, current_user.cabinet_id)
    document = db.get(Document, entry.document_id)

    ancien_statut = entry.statut_validation.value
    entry.statut_validation = StatutValidationEnum.VALIDE
    entry.validated_by = current_user.id

    generation = ligne_comptable_service.synchroniser_lignes_facture(db, entry)
    if generation.applicable and not generation.complet:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail=(
                "Validation refusée : les lignes Débit/Crédit ne sont pas complètes. "
                + " | ".join(generation.raisons)
            ),
        )

    if document is not None:
        document.statut = StatutDocumentEnum.VALIDE

    # Si des mouvements bancaires étaient déjà rapprochés à cette facture,
    # ils deviennent éligibles au journal Banque maintenant que la facture
    # est validée.
    mouvements = _mouvements_lies_a_ecriture(
        db,
        cabinet_id=current_user.cabinet_id,
        ecriture_id=entry.id,
    )
    for mouvement in mouvements:
        ligne_comptable_service.synchroniser_lignes_banque(db, mouvement)

    audit_service.enregistrer(
        db, user=current_user, action="accounting_entry.validate",
        resource_type="ecriture_comptable", resource_id=entry.id,
        avant={"statut_validation": ancien_statut},
        apres={"statut_validation": StatutValidationEnum.VALIDE.value},
    )

    db.commit()
    return _get_entry_output(db, entry_id, current_user.cabinet_id)


@router.patch("/entries/{entry_id}/reject", response_model=EcritureOut)
def reject_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    entry = _get_entry_or_404(db, entry_id, current_user.cabinet_id)
    document = db.get(Document, entry.document_id)

    ancien_statut = entry.statut_validation.value
    entry.statut_validation = StatutValidationEnum.REJETE
    entry.validated_by = current_user.id
    if document is not None:
        document.statut = StatutDocumentEnum.TRAITE

    ligne_comptable_service.synchroniser_lignes_facture(db, entry)
    audit_service.enregistrer(
        db, user=current_user, action="accounting_entry.reject",
        resource_type="ecriture_comptable", resource_id=entry.id,
        avant={"statut_validation": ancien_statut},
        apres={"statut_validation": StatutValidationEnum.REJETE.value},
    )
    db.commit()
    return _get_entry_output(db, entry_id, current_user.cabinet_id)


@router.patch("/entries/{entry_id}/saisie", response_model=EcritureOut)
def toggle_saisie_topaze(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = _get_entry_or_404(db, entry_id, current_user.cabinet_id)
    document = db.get(Document, entry.document_id)

    entry.saisie_topaze = not entry.saisie_topaze
    if document is not None:
        document.saisie_topaze = entry.saisie_topaze

    db.commit()
    return _get_entry_output(db, entry_id, current_user.cabinet_id)


@router.patch("/entries/{entry_id}", response_model=EcritureOut)
def update_entry(
    entry_id: uuid.UUID,
    payload: EcritureUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    entry = _get_entry_or_404(db, entry_id, current_user.cabinet_id)
    document = db.get(Document, entry.document_id)

    data = payload.model_dump(exclude_unset=True)
    if "montant_ttc" in data and data["montant_ttc"] is None:
        raise HTTPException(status_code=422, detail="Le montant TTC est obligatoire.")

    for field_name, field_value in data.items():
        setattr(entry, field_name, field_value)

    # Une correction doit toujours être contrôlée une nouvelle fois.
    entry.statut_validation = StatutValidationEnum.A_VERIFIER
    entry.validated_by = None
    if document is not None:
        document.statut = StatutDocumentEnum.TRAITE

    ligne_comptable_service.synchroniser_lignes_facture(db, entry)

    # Toute ligne Banque précédemment reliée à cette écriture doit être
    # désactivée tant que la facture corrigée n'est pas revalidée.
    mouvements = _mouvements_lies_a_ecriture(
        db,
        cabinet_id=current_user.cabinet_id,
        ecriture_id=entry.id,
    )
    for mouvement in mouvements:
        ligne_comptable_service.synchroniser_lignes_banque(db, mouvement)

    db.commit()
    return _get_entry_output(db, entry_id, current_user.cabinet_id)


@router.get("/bank-movements", response_model=list[MouvementBancaireListeOut])
def list_bank_movements(
    entreprise_id: uuid.UUID | None = Query(default=None),
    type_mouvement: TypeMouvementBancaireEnum | None = Query(default=None),
    recherche: str | None = Query(default=None, max_length=150),
    annee: int | None = Query(default=None, ge=2000, le=2100),
    mois: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les mouvements bancaires réellement extraits des relevés."""
    query = (
        select(
            MouvementBancaire,
            Document,
            Entreprise.nom,
            EcritureComptable,
        )
        .join(Document, MouvementBancaire.document_id == Document.id)
        .join(Entreprise, MouvementBancaire.entreprise_id == Entreprise.id, isouter=True)
        .join(
            EcritureComptable,
            MouvementBancaire.ecriture_rapprochee_id == EcritureComptable.id,
            isouter=True,
        )
        .where(MouvementBancaire.cabinet_id == current_user.cabinet_id)
    )

    if entreprise_id is not None:
        query = query.where(MouvementBancaire.entreprise_id == entreprise_id)
    if type_mouvement is not None:
        query = query.where(MouvementBancaire.type_mouvement == type_mouvement)

    bank_year = func.coalesce(
        Document.annee,
        cast(extract("year", MouvementBancaire.date_operation), Integer),
    )
    bank_month = func.coalesce(
        Document.mois,
        cast(extract("month", MouvementBancaire.date_operation), Integer),
    )
    if annee is not None:
        query = query.where(bank_year == annee)
    if mois is not None:
        query = query.where(bank_month == mois)

    search_term = (recherche or "").strip()
    if search_term:
        pattern = f"%{search_term}%"
        query = query.where(
            or_(
                MouvementBancaire.libelle.ilike(pattern),
                MouvementBancaire.reference.ilike(pattern),
                Document.nom_fichier_original.ilike(pattern),
                Entreprise.nom.ilike(pattern),
            )
        )

    rows = db.execute(
        query.order_by(
            MouvementBancaire.date_operation.desc(),
            MouvementBancaire.created_at.desc(),
        )
    ).all()

    output: list[MouvementBancaireListeOut] = []
    for movement, document, entreprise_nom, ecriture_rapprochee in rows:
        # MouvementBancaireListeOut contient aussi des champs qui proviennent
        # du document joint (nom du fichier, statut, période, saisie Topaze).
        # Ils doivent être fournis pendant la validation Pydantic et non après,
        # sinon Pydantic considère les champs requis comme manquants et renvoie
        # une erreur HTTP 500.
        movement_data = MouvementBancaireOut.model_validate(movement).model_dump()

        statut_document = (
            document.statut.value
            if hasattr(document.statut, "value")
            else str(document.statut)
        )

        allocations = _allocation_outputs(db, movement)
        montant_affecte_total = sum((Decimal(str(a.montant_affecte)) for a in allocations), Decimal("0.00"))
        montant_non_affecte = max(Decimal("0.00"), Decimal(str(movement.montant)) - montant_affecte_total)
        bank_account = (
            db.get(CompteBancaireEntreprise, movement.compte_bancaire_entreprise_id)
            if movement.compte_bancaire_entreprise_id
            else None
        )

        item = MouvementBancaireListeOut(
            **movement_data,
            entreprise_nom=entreprise_nom,
            nom_fichier_document=document.nom_fichier_original,
            statut_document=statut_document,
            annee=document.annee or movement.date_operation.year,
            mois=document.mois or movement.date_operation.month,
            saisie_topaze=bool(document.saisie_topaze),
            numero_piece_rapprochee=(
                ecriture_rapprochee.numero_piece if ecriture_rapprochee else None
            ),
            date_piece_rapprochee=(
                ecriture_rapprochee.date_piece if ecriture_rapprochee else None
            ),
            tiers_rapproche=(
                ecriture_rapprochee.tiers if ecriture_rapprochee else None
            ),
            type_ecriture_rapprochee=(
                ecriture_rapprochee.type_ecriture.value
                if ecriture_rapprochee and hasattr(ecriture_rapprochee.type_ecriture, "value")
                else (str(ecriture_rapprochee.type_ecriture) if ecriture_rapprochee else None)
            ),
            montant_ttc_rapproche=(
                ecriture_rapprochee.montant_ttc if ecriture_rapprochee else None
            ),
            montant_affecte_total=montant_affecte_total,
            montant_non_affecte=montant_non_affecte,
            nombre_allocations=len(allocations),
            allocations=allocations,
            compte_bancaire_libelle=(bank_account.libelle if bank_account else None),
            compte_bancaire_rib=(bank_account.rib if bank_account else None),
            compte_bancaire_iban=(bank_account.iban if bank_account else None),
        )
        output.append(item)

    return output


def _get_bank_movement_or_404(
    db: Session,
    movement_id: uuid.UUID,
    cabinet_id: uuid.UUID,
) -> MouvementBancaire:
    mouvement = db.execute(
        select(MouvementBancaire).where(
            MouvementBancaire.id == movement_id,
            MouvementBancaire.cabinet_id == cabinet_id,
        )
    ).scalar_one_or_none()

    if mouvement is None:
        raise HTTPException(status_code=404, detail="Mouvement bancaire introuvable.")
    return mouvement


@router.get(
    "/bank-movements/{movement_id}/candidates",
    response_model=list[RapprochementCandidatOut],
)
def get_bank_reconciliation_candidates(
    movement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    candidats = rapprochement_bancaire_service.calculer_candidats(db, mouvement)

    return [
        RapprochementCandidatOut(
            ecriture_id=item.ecriture.id,
            numero_piece=item.ecriture.numero_piece,
            date_piece=item.ecriture.date_piece,
            tiers=item.ecriture.tiers,
            type_ecriture=(
                item.ecriture.type_ecriture.value
                if hasattr(item.ecriture.type_ecriture, "value")
                else str(item.ecriture.type_ecriture)
            ),
            montant_ttc=item.ecriture.montant_ttc,
            montant_deja_regle=item.montant_deja_regle,
            montant_restant=item.montant_restant,
            montant_suggere=item.montant_suggere,
            type_suggestion=item.type_suggestion,
            score=item.score,
            raisons=list(item.raisons),
        )
        for item in candidats
    ]


@router.post(
    "/bank-movements/{movement_id}/reconcile-auto",
    response_model=MouvementBancaireOut,
)
def reconcile_bank_movement_auto(
    movement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    rapprochement_bancaire_service.rapprocher_mouvement(db, mouvement)
    ligne_comptable_service.synchroniser_lignes_banque(db, mouvement)
    db.commit()
    db.refresh(mouvement)
    return mouvement


@router.patch(
    "/bank-movements/{movement_id}/reconcile/{entry_id}",
    response_model=MouvementBancaireOut,
)
def confirm_bank_reconciliation(
    movement_id: uuid.UUID,
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    ecriture = _get_entry_or_404(db, entry_id, current_user.cabinet_id)

    try:
        rapprochement_bancaire_service.confirmer_rapprochement(
            db,
            mouvement,
            ecriture,
            current_user.id,
        )
        ligne_comptable_service.synchroniser_lignes_banque(db, mouvement)
        db.commit()
        db.refresh(mouvement)
        return mouvement
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete(
    "/bank-movements/{movement_id}/reconcile",
    response_model=MouvementBancaireOut,
)
def unlink_bank_reconciliation(
    movement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    rapprochement_bancaire_service.annuler_rapprochement(db, mouvement)
    ligne_comptable_service.supprimer_lignes_banque(db, mouvement.id)
    db.commit()
    db.refresh(mouvement)
    return mouvement



@router.post(
    "/bank-movements/{movement_id}/allocations",
    response_model=MouvementBancaireOut,
)
def confirm_bank_allocations(
    movement_id: uuid.UUID,
    payload: AllocationRapprochementBatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    entries: list[tuple[EcritureComptable, Decimal, Decimal | None]] = []
    for item in payload.allocations:
        entry = _get_entry_or_404(db, item.ecriture_id, current_user.cabinet_id)
        entries.append((entry, item.montant_affecte, item.montant_devise_affecte))
    try:
        rapprochement_bancaire_service.confirmer_allocations(
            db,
            mouvement,
            entries,
            current_user.id,
        )
        generation = ligne_comptable_service.synchroniser_lignes_banque(db, mouvement)
        if (
            generation.applicable
            and not generation.complet
            and mouvement.statut_rapprochement != "a_verifier"
        ):
            db.rollback()
            raise HTTPException(status_code=422, detail=" | ".join(generation.raisons))
        db.commit()
        db.refresh(mouvement)
        return mouvement
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch(
    "/bank-movements/{movement_id}/operation",
    response_model=MouvementBancaireOut,
)
def update_bank_operation(
    movement_id: uuid.UUID,
    payload: MouvementBancaireUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    data = payload.model_dump(exclude_unset=True)

    if "compte_bancaire_entreprise_id" in data:
        account_id = data["compte_bancaire_entreprise_id"]
        if account_id is None:
            mouvement.compte_bancaire_entreprise_id = None
            mouvement.compte_banque = None
        else:
            account = db.execute(
                select(CompteBancaireEntreprise).where(
                    CompteBancaireEntreprise.id == account_id,
                    CompteBancaireEntreprise.cabinet_id == current_user.cabinet_id,
                    CompteBancaireEntreprise.entreprise_id == mouvement.entreprise_id,
                    CompteBancaireEntreprise.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if account is None:
                raise HTTPException(status_code=404, detail="Compte bancaire configuré introuvable.")
            mouvement.compte_bancaire_entreprise_id = account.id
            mouvement.compte_banque = account.numero_compte_comptable
        data.pop("compte_bancaire_entreprise_id", None)

    immutable_here = {"date_operation", "libelle", "reference", "type_mouvement", "montant", "solde_apres_operation"}
    for field_name, value in data.items():
        if field_name not in immutable_here:
            setattr(mouvement, field_name, value)

    _validate_special_counterpart(db, mouvement)
    if mouvement.nature_operation != "reglement_facture":
        rapprochement_bancaire_service.annuler_rapprochement(db, mouvement)
        mouvement.mode_rapprochement = "special"
    else:
        rapprochement_bancaire_service.rapprocher_mouvement(db, mouvement)

    generation = ligne_comptable_service.synchroniser_lignes_banque(db, mouvement)
    if generation.applicable and not generation.complet and mouvement.nature_operation != "reglement_facture":
        # Une opération spéciale peut être enregistrée avant que le comptable ne
        # renseigne son compte de contrepartie ; elle reste simplement non comptabilisée.
        mouvement.raison_rapprochement = " | ".join(generation.raisons)[:500]
    db.commit()
    db.refresh(mouvement)
    return mouvement


@router.get(
    "/bank-movements/{movement_id}/internal-transfer-candidates",
    response_model=list[VirementInterneCandidatOut],
)
def get_internal_transfer_candidates(
    movement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    candidates = rapprochement_bancaire_service.calculer_candidats_virement_interne(db, mouvement)
    return [
        VirementInterneCandidatOut(
            mouvement_id=item.mouvement.id,
            date_operation=item.mouvement.date_operation,
            libelle=item.mouvement.libelle,
            type_mouvement=(item.mouvement.type_mouvement.value if hasattr(item.mouvement.type_mouvement, "value") else str(item.mouvement.type_mouvement)),
            montant=item.mouvement.montant,
            compte_banque=item.mouvement.compte_banque,
            score=item.score,
            raisons=list(item.raisons),
        )
        for item in candidates
    ]


@router.patch(
    "/bank-movements/{movement_id}/internal-transfer/{other_movement_id}",
    response_model=MouvementBancaireOut,
)
def link_internal_transfer(
    movement_id: uuid.UUID,
    other_movement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    mouvement = _get_bank_movement_or_404(db, movement_id, current_user.cabinet_id)
    other = _get_bank_movement_or_404(db, other_movement_id, current_user.cabinet_id)
    try:
        rapprochement_bancaire_service.lier_virement_interne(db, mouvement, other)
        ligne_comptable_service.synchroniser_lignes_banque(db, mouvement)
        ligne_comptable_service.synchroniser_lignes_banque(db, other)
        db.commit()
        db.refresh(mouvement)
        return mouvement
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/bank-accounts", response_model=list[CompteBancaireOut])
def list_bank_accounts(
    entreprise_id: uuid.UUID = Query(...),
    inclure_inactifs: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(CompteBancaireEntreprise).where(
        CompteBancaireEntreprise.cabinet_id == current_user.cabinet_id,
        CompteBancaireEntreprise.entreprise_id == entreprise_id,
    )
    if not inclure_inactifs:
        query = query.where(CompteBancaireEntreprise.is_active.is_(True))
    return db.execute(query.order_by(CompteBancaireEntreprise.libelle.asc())).scalars().all()


@router.post("/bank-accounts", response_model=CompteBancaireOut)
def create_bank_account(
    payload: CompteBancaireCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    bank_account_service.valider_compte_comptable_banque(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=payload.entreprise_id,
        numero_compte=payload.numero_compte_comptable,
    )
    item = CompteBancaireEntreprise(
        cabinet_id=current_user.cabinet_id,
        **payload.model_dump(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/bank-accounts/{account_id}", response_model=CompteBancaireOut)
def update_bank_account(
    account_id: uuid.UUID,
    payload: CompteBancaireUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    item = db.execute(
        select(CompteBancaireEntreprise).where(
            CompteBancaireEntreprise.id == account_id,
            CompteBancaireEntreprise.cabinet_id == current_user.cabinet_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable.")
    data = payload.model_dump(exclude_unset=True)
    if data.get("numero_compte_comptable"):
        bank_account_service.valider_compte_comptable_banque(
            db,
            cabinet_id=current_user.cabinet_id,
            entreprise_id=item.entreprise_id,
            numero_compte=data["numero_compte_comptable"],
        )
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/bank-accounts/{account_id}", response_model=CompteBancaireOut)
def deactivate_bank_account(
    account_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    item = db.execute(
        select(CompteBancaireEntreprise).where(
            CompteBancaireEntreprise.id == account_id,
            CompteBancaireEntreprise.cabinet_id == current_user.cabinet_id,
        )
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Compte bancaire introuvable.")
    item.is_active = False
    db.commit()
    db.refresh(item)
    return item


@router.get("/grand-livre", response_model=GrandLivreOut)
def get_grand_livre(
    entreprise_id: uuid.UUID = Query(...),
    date_debut: date_type | None = Query(default=None),
    date_fin: date_type | None = Query(default=None),
    compte_prefix: str | None = Query(default=None, max_length=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if date_debut is not None and date_fin is not None and date_debut > date_fin:
        raise HTTPException(status_code=422, detail="date_debut doit précéder date_fin.")

    return ligne_comptable_service.obtenir_grand_livre(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        date_debut=date_debut,
        date_fin=date_fin,
        compte_prefix=compte_prefix,
    )


@router.get("/balance", response_model=BalanceOut)
def get_balance(
    entreprise_id: uuid.UUID = Query(...),
    date_debut: date_type | None = Query(default=None),
    date_fin: date_type | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if date_debut is not None and date_fin is not None and date_debut > date_fin:
        raise HTTPException(status_code=422, detail="date_debut doit précéder date_fin.")

    return ligne_comptable_service.obtenir_balance(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        date_debut=date_debut,
        date_fin=date_fin,
    )


@router.post("/ledger/rebuild", response_model=ReconstructionLedgerOut)
def rebuild_ledger(
    entreprise_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    resultat = ligne_comptable_service.reconstruire_lignes_entreprise(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
    )
    db.commit()
    return ReconstructionLedgerOut(
        entreprise_id=entreprise_id,
        ecritures_total=resultat.ecritures_total,
        ecritures_completes=resultat.ecritures_completes,
        ecritures_incompletes=resultat.ecritures_incompletes,
        mouvements_total=resultat.mouvements_total,
        mouvements_complets=resultat.mouvements_complets,
        mouvements_incomplets=resultat.mouvements_incomplets,
        lignes_total=resultat.lignes_total,
    )


@router.get("/registers/options", response_model=list[RegistreOptionOut])
def get_registre_options(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Combinaisons entreprise/catégorie/période contenant des lignes validées."""
    year_expression, month_expression = _period_expressions()

    rows = db.execute(
        select(
            EcritureComptable.entreprise_id,
            Document.categorie,
            year_expression.label("annee"),
            month_expression.label("mois"),
            func.count(EcritureComptable.id).label("nombre"),
        )
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(
            EcritureComptable.cabinet_id == current_user.cabinet_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            Document.categorie.is_not(None),
            year_expression.is_not(None),
            month_expression.is_not(None),
        )
        .group_by(
            EcritureComptable.entreprise_id,
            Document.categorie,
            year_expression,
            month_expression,
        )
        .order_by(year_expression.desc(), month_expression.desc())
    ).all()

    return [
        RegistreOptionOut(
            entreprise_id=entreprise_id,
            categorie=categorie.value if hasattr(categorie, "value") else str(categorie),
            annee=int(annee),
            mois=int(mois),
            nombre=int(nombre),
        )
        for entreprise_id, categorie, annee, mois, nombre in rows
    ]


@router.get("/registers", response_model=RegistreOut)
def get_registre(
    entreprise_id: uuid.UUID = Query(...),
    categorie: CategorieDocumentEnum = Query(...),
    annee: int = Query(...),
    mois: int | None = Query(default=None, ge=1, le=12),
    trimestre: int | None = Query(default=None, ge=1, le=4),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if (mois is None) == (trimestre is None):
        raise HTTPException(
            status_code=400,
            detail="Fournir soit 'mois' soit 'trimestre'.",
        )

    if trimestre is not None:
        first_month = (trimestre - 1) * 3 + 1
        target_months = [first_month, first_month + 1, first_month + 2]
    else:
        target_months = [mois]

    year_expression, month_expression = _period_expressions()
    rows = db.execute(
        select(EcritureComptable, Document, Entreprise.nom)
        .join(Document, EcritureComptable.document_id == Document.id)
        .join(Entreprise, EcritureComptable.entreprise_id == Entreprise.id, isouter=True)
        .where(
            EcritureComptable.cabinet_id == current_user.cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            Document.categorie == categorie,
            year_expression == annee,
            month_expression.in_(target_months),
        )
        .order_by(EcritureComptable.date_piece, EcritureComptable.created_at)
    ).all()

    lines = [
        _to_ecriture_out(entry, document, entreprise_nom)
        for entry, document, entreprise_nom in rows
    ]

    total_ht = sum(
        (line.montant_ht or Decimal("0.00") for line in lines),
        Decimal("0.00"),
    )
    total_tva = sum(
        (line.montant_tva or Decimal("0.00") for line in lines),
        Decimal("0.00"),
    )
    total_ttc = sum(
        (line.montant_ttc or Decimal("0.00") for line in lines),
        Decimal("0.00"),
    )

    return RegistreOut(
        categorie=categorie.value,
        entreprise_id=entreprise_id,
        annee=annee,
        mois=mois or target_months[0],
        nombre=len(lines),
        total_ht=total_ht,
        total_tva=total_tva,
        total_ttc=total_ttc,
        lignes=lines,
    )


@router.get("/tva-mensuelle", response_model=TvaAnnuelleOut)
def get_tva_mensuelle(
    entreprise_id: uuid.UUID = Query(...),
    annee: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Synthèse TVA comptable basée sur les lignes Débit/Crédit validées.

    Ce endpoint conserve son URL historique pour ne pas casser le frontend,
    mais le calcul ne somme plus directement `montant_tva` des factures.
    Il lit désormais les comptes TVA réellement présents dans le Grand Livre.
    """
    resultat = tva_comptable_service.calculer_tva_annuelle(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        annee=annee,
    )

    mensualites = [
        TvaMensuelle(
            mois=item.mois,
            annee=item.annee,
            tva_collectee=format(item.tva_collectee, "f"),
            tva_deductible_charges=format(item.tva_deductible_charges, "f"),
            tva_deductible_immobilisations=format(
                item.tva_deductible_immobilisations, "f"
            ),
            tva_deductible=format(item.tva_deductible, "f"),
            tva_nette=format(item.tva_nette, "f"),
            tva_a_payer=format(item.tva_a_payer, "f"),
            credit_tva=format(item.credit_tva, "f"),
            nombre_ecritures=item.nombre_ecritures,
            nombre_lignes_tva=item.nombre_lignes_tva,
            a_verifier=item.a_verifier,
            raisons_verification=list(item.raisons_verification),
            comptes=[
                TvaCompteDetailOut(
                    compte=compte.compte,
                    nature=compte.nature,
                    debit=format(compte.debit, "f"),
                    credit=format(compte.credit, "f"),
                    montant_net=format(compte.montant_net, "f"),
                )
                for compte in item.comptes
            ],
        )
        for item in resultat.mensualites
    ]

    return TvaAnnuelleOut(
        entreprise_id=resultat.entreprise_id,
        annee=resultat.annee,
        mensualites=mensualites,
        total_tva_collectee=format(resultat.total_tva_collectee, "f"),
        total_tva_deductible_charges=format(
            resultat.total_tva_deductible_charges, "f"
        ),
        total_tva_deductible_immobilisations=format(
            resultat.total_tva_deductible_immobilisations, "f"
        ),
        total_tva_deductible=format(resultat.total_tva_deductible, "f"),
        total_tva_nette=format(resultat.total_tva_nette, "f"),
        total_tva_a_payer_technique=format(
            resultat.total_tva_a_payer_technique, "f"
        ),
        total_credit_tva_technique=format(
            resultat.total_credit_tva_technique, "f"
        ),
        nombre_mois_a_verifier=resultat.nombre_mois_a_verifier,
        source_calcul=resultat.source_calcul,
        declaration_fiscale_prete=resultat.declaration_fiscale_prete,
        limites=list(resultat.limites),
    )


@router.get("/cpc", response_model=CpcOut)
def get_cpc(
    entreprise_id: uuid.UUID = Query(...),
    annee: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Compte de Produits et Charges construit depuis le Grand Livre validé."""
    resultat = cpc_service.calculer_cpc(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        annee=annee,
    )

    return CpcOut(
        entreprise_id=resultat.entreprise_id,
        annee=resultat.annee,
        date_debut=resultat.date_debut,
        date_fin=resultat.date_fin,
        produits_exploitation=resultat.produits_exploitation,
        charges_exploitation=resultat.charges_exploitation,
        resultat_exploitation=resultat.resultat_exploitation,
        produits_financiers=resultat.produits_financiers,
        charges_financieres=resultat.charges_financieres,
        resultat_financier=resultat.resultat_financier,
        resultat_courant=resultat.resultat_courant,
        produits_non_courants=resultat.produits_non_courants,
        charges_non_courantes=resultat.charges_non_courantes,
        resultat_non_courant=resultat.resultat_non_courant,
        resultat_avant_impots=resultat.resultat_avant_impots,
        impots_sur_resultats=resultat.impots_sur_resultats,
        resultat_net=resultat.resultat_net,
        nombre_lignes=resultat.nombre_lignes,
        nombre_comptes=resultat.nombre_comptes,
        a_verifier=resultat.a_verifier,
        raisons_verification=list(resultat.raisons_verification),
        comptes=[
            CpcCompteDetailOut(
                compte=item.compte,
                libelle_compte=item.libelle_compte,
                rubrique=item.rubrique,
                debit=item.debit,
                credit=item.credit,
                montant=item.montant,
            )
            for item in resultat.comptes
        ],
        source_calcul=resultat.source_calcul,
    )


@router.get("/bilan", response_model=BilanOut)
def get_bilan(
    entreprise_id: uuid.UUID = Query(...),
    annee: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bilan technique construit depuis le Grand Livre validé + résultat CPC."""
    resultat = bilan_service.calculer_bilan(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        annee=annee,
    )

    return BilanOut(
        entreprise_id=resultat.entreprise_id,
        annee=resultat.annee,
        date_cloture=resultat.date_cloture,
        actif_immobilise_brut=resultat.actif_immobilise_brut,
        amortissements_provisions_immobilisations=(
            resultat.amortissements_provisions_immobilisations
        ),
        actif_immobilise_net=resultat.actif_immobilise_net,
        actif_circulant_brut=resultat.actif_circulant_brut,
        provisions_actif_circulant=resultat.provisions_actif_circulant,
        actif_circulant_net=resultat.actif_circulant_net,
        tresorerie_actif=resultat.tresorerie_actif,
        total_actif=resultat.total_actif,
        financement_permanent_comptabilise=(
            resultat.financement_permanent_comptabilise
        ),
        passif_circulant=resultat.passif_circulant,
        tresorerie_passif=resultat.tresorerie_passif,
        total_passif_comptable=resultat.total_passif_comptable,
        resultat_net_cpc=resultat.resultat_net_cpc,
        resultat_cpc_integre=resultat.resultat_cpc_integre,
        total_passif_technique=resultat.total_passif_technique,
        ecart_avant_resultat_cpc=resultat.ecart_avant_resultat_cpc,
        ecart_bilan=resultat.ecart_bilan,
        equilibre=resultat.equilibre,
        nombre_lignes=resultat.nombre_lignes,
        nombre_comptes=resultat.nombre_comptes,
        a_verifier=resultat.a_verifier,
        raisons_verification=list(resultat.raisons_verification),
        comptes=[
            BilanCompteDetailOut(
                compte=item.compte,
                libelle_compte=item.libelle_compte,
                rubrique=item.rubrique,
                cote=item.cote,
                debit=item.debit,
                credit=item.credit,
                solde_debiteur=item.solde_debiteur,
                solde_crediteur=item.solde_crediteur,
                montant_bilan=item.montant_bilan,
                est_compte_correcteur=item.est_compte_correcteur,
            )
            for item in resultat.comptes
        ],
        source_calcul=resultat.source_calcul,
    )


def _ensure_company_for_state(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
) -> None:
    exists = db.execute(select(Entreprise.id).where(
        Entreprise.id == entreprise_id,
        Entreprise.cabinet_id == cabinet_id,
    )).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=404, detail="Entreprise introuvable dans ce cabinet.")


@router.get("/cpc-v2", response_model=CpcV2Out)
def get_cpc_v2(
    entreprise_id: uuid.UUID = Query(...),
    exercice: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_company_for_state(
        db, cabinet_id=current_user.cabinet_id, entreprise_id=entreprise_id
    )
    return cpc_service.calculer_cpc_v2(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        exercice=exercice,
    )


@router.get("/bilan-v2", response_model=BilanV2Out)
def get_bilan_v2(
    entreprise_id: uuid.UUID = Query(...),
    exercice: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_company_for_state(
        db, cabinet_id=current_user.cabinet_id, entreprise_id=entreprise_id
    )
    return bilan_service.calculer_bilan_v2(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        exercice=exercice,
    )


@router.get("/controls/{entreprise_id}", response_model=PreClotureOut)
def get_precloture_controls(
    entreprise_id: uuid.UUID,
    exercice: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne les controles techniques dynamiques, sans aucune correction."""
    _ensure_company_for_state(
        db, cabinet_id=current_user.cabinet_id, entreprise_id=entreprise_id
    )
    return precloture_service.calculer_precloture(
        db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        exercice=exercice,
    )
