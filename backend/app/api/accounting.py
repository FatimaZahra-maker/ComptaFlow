"""API de consultation et de validation des données comptables.

Cette API alimente les pages Écritures, Achats, Ventes, Banque, Registres
et TVA mensuelle. Elle ne modifie pas le pipeline OCR/IA.
"""

import uuid
from decimal import Decimal

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
from app.models.user import User
from app.schemas.ecriture import EcritureOut, EcritureUpdate
from app.schemas.mouvement_bancaire import (
    MouvementBancaireListeOut,
    MouvementBancaireOut,
)
from app.schemas.registre import (
    RegistreOptionOut,
    RegistreOut,
    TvaAnnuelleOut,
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


@router.patch("/entries/{entry_id}/validate", response_model=EcritureOut)
def validate_entry(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_ROLES_VALIDATION)),
):
    entry = _get_entry_or_404(db, entry_id, current_user.cabinet_id)
    document = db.get(Document, entry.document_id)

    entry.statut_validation = StatutValidationEnum.VALIDE
    entry.validated_by = current_user.id
    if document is not None:
        document.statut = StatutDocumentEnum.VALIDE

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

    entry.statut_validation = StatutValidationEnum.REJETE
    entry.validated_by = current_user.id
    if document is not None:
        document.statut = StatutDocumentEnum.TRAITE

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
        select(MouvementBancaire, Document, Entreprise.nom)
        .join(Document, MouvementBancaire.document_id == Document.id)
        .join(Entreprise, MouvementBancaire.entreprise_id == Entreprise.id, isouter=True)
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
    for movement, document, entreprise_nom in rows:
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

        item = MouvementBancaireListeOut(
            **movement_data,
            entreprise_nom=entreprise_nom,
            nom_fichier_document=document.nom_fichier_original,
            statut_document=statut_document,
            annee=document.annee or movement.date_operation.year,
            mois=document.mois or movement.date_operation.month,
            saisie_topaze=bool(document.saisie_topaze),
        )
        output.append(item)

    return output


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
    annee: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    year_expression, month_expression = _period_expressions()

    rows = db.execute(
        select(
            month_expression.label("mois"),
            EcritureComptable.type_ecriture,
            EcritureComptable.montant_tva,
        )
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(
            EcritureComptable.cabinet_id == current_user.cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            year_expression == annee,
            month_expression.is_not(None),
        )
    ).all()

    by_month: dict[int, dict[str, Decimal | int]] = {
        number: {
            "collectee": Decimal("0.00"),
            "deductible": Decimal("0.00"),
            "nombre": 0,
        }
        for number in range(1, 13)
    }

    for month_number, entry_type, tax_amount in rows:
        month_int = int(month_number)
        value = tax_amount or Decimal("0.00")
        type_value = entry_type.value if hasattr(entry_type, "value") else str(entry_type)

        if type_value == TypeEcritureEnum.VENTE.value:
            by_month[month_int]["collectee"] += value
        elif type_value == TypeEcritureEnum.ACHAT.value:
            by_month[month_int]["deductible"] += value

        by_month[month_int]["nombre"] += 1

    monthly = [
        TvaMensuelle(
            mois=number,
            annee=annee,
            tva_collectee=str(by_month[number]["collectee"]),
            tva_deductible=str(by_month[number]["deductible"]),
            tva_nette=str(
                by_month[number]["collectee"] - by_month[number]["deductible"]
            ),
            nombre_ecritures=int(by_month[number]["nombre"]),
        )
        for number in range(1, 13)
    ]

    total_collected = sum(
        (Decimal(item.tva_collectee) for item in monthly),
        Decimal("0.00"),
    )
    total_deductible = sum(
        (Decimal(item.tva_deductible) for item in monthly),
        Decimal("0.00"),
    )

    return TvaAnnuelleOut(
        entreprise_id=entreprise_id,
        annee=annee,
        mensualites=monthly,
        total_tva_collectee=str(total_collected),
        total_tva_deductible=str(total_deductible),
        total_tva_nette=str(total_collected - total_deductible),
    )
