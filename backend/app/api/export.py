"""Routes d'export Excel, CSV, PDF et Topaze."""

import io
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import Integer, cast, extract, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user_flexible
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import CategorieDocumentEnum, StatutValidationEnum
from app.models.user import User
from app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])

_MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv; charset=utf-8",
    "pdf": "application/pdf",
}


def _period_expressions():
    year_from_date = cast(extract("year", EcritureComptable.date_piece), Integer)
    month_from_date = cast(extract("month", EcritureComptable.date_piece), Integer)
    return (
        func.coalesce(Document.annee, year_from_date),
        func.coalesce(Document.mois, month_from_date),
    )


def _recuperer_lignes_et_totaux(
    db: Session,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    categorie: CategorieDocumentEnum,
    annee: int,
    mois: int,
) -> tuple[list[EcritureComptable], dict[str, Decimal]]:
    year_expression, month_expression = _period_expressions()

    lignes = list(
        db.execute(
            select(EcritureComptable)
            .join(Document, EcritureComptable.document_id == Document.id)
            .where(
                EcritureComptable.cabinet_id == cabinet_id,
                EcritureComptable.entreprise_id == entreprise_id,
                EcritureComptable.statut_validation
                == StatutValidationEnum.VALIDE,
                Document.categorie == categorie,
                year_expression == annee,
                month_expression == mois,
            )
            .order_by(EcritureComptable.date_piece, EcritureComptable.created_at)
        ).scalars().all()
    )

    totaux = {
        "total_ht": sum(
            (ligne.montant_ht or Decimal("0.00") for ligne in lignes),
            Decimal("0.00"),
        ),
        "total_tva": sum(
            (ligne.montant_tva or Decimal("0.00") for ligne in lignes),
            Decimal("0.00"),
        ),
        "total_ttc": sum(
            (ligne.montant_ttc or Decimal("0.00") for ligne in lignes),
            Decimal("0.00"),
        ),
    }
    return lignes, totaux


@router.get("/topaze/{ecriture_id}")
def exporter_topaze(
    ecriture_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    ecriture = db.query(EcritureComptable).filter(
        EcritureComptable.id == ecriture_id,
        EcritureComptable.cabinet_id == current_user.cabinet_id,
    ).first()

    if ecriture is None:
        raise HTTPException(status_code=404, detail="Écriture introuvable.")

    contenu = export_service.generer_export_topaze(ecriture)
    nom_piece = ecriture.numero_piece or str(ecriture.id)

    return StreamingResponse(
        io.BytesIO(contenu),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="export_topaze_{nom_piece}.csv"'
            )
        },
    )


@router.get("/registers/{format}")
def export_registre(
    format: str,
    entreprise_id: uuid.UUID = Query(...),
    categorie: CategorieDocumentEnum = Query(...),
    annee: int = Query(...),
    mois: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    normalized_format = format.lower()

    if normalized_format not in _MEDIA_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Format non supporté : {format}. "
                "Formats acceptés : xlsx, csv, pdf."
            ),
        )

    lignes, totaux = _recuperer_lignes_et_totaux(
        db=db,
        cabinet_id=current_user.cabinet_id,
        entreprise_id=entreprise_id,
        categorie=categorie,
        annee=annee,
        mois=mois,
    )

    categorie_value = categorie.value
    titre = f"Registre {categorie_value} - {mois:02d}/{annee}"
    suffixe = f"{categorie_value}_{annee}_{mois:02d}"

    if normalized_format == "xlsx":
        contenu = export_service.generer_excel(lignes, titre, totaux)
        nom_fichier = f"registre_{suffixe}.xlsx"
    elif normalized_format == "csv":
        contenu = export_service.generer_csv(lignes, totaux)
        nom_fichier = f"registre_{suffixe}.csv"
    else:
        contenu = export_service.generer_pdf(lignes, titre, totaux)
        nom_fichier = f"registre_{suffixe}.pdf"

    return Response(
        content=contenu,
        media_type=_MEDIA_TYPES[normalized_format],
        headers={
            "Content-Disposition": f'attachment; filename="{nom_fichier}"'
        },
    )
