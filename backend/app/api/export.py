"""
app/api/export.py

Routes d'export (Phase 9) : génère et renvoie un fichier Excel, CSV ou
PDF du registre comptable calculé pour une entreprise/catégorie/
année/mois donnés (mêmes filtres que GET /accounting/registers), plus
un export Topaze pour une écriture unique (bouton "Exporter Topaze" du
frontend, DocumentDetailPage.tsx).

Rien n'est écrit sur disque côté serveur -- le fichier est généré en
mémoire et streamé directement dans la réponse HTTP.

Utilise get_current_user_flexible (et non get_current_user) car ces
routes sont appelées via un lien <a href> depuis le frontend, qui ne
peut pas envoyer de header Authorization -- le token arrive donc en
query parameter ?token=...
"""
import io
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user_flexible
from app.models.user import User
from app.models.ecriture import EcritureComptable
from app.models.document import Document
from app.models.enums import StatutValidationEnum
from app.services import export_service

router = APIRouter(prefix="/export", tags=["export"])

_MEDIA_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


def _recuperer_lignes_et_totaux(
    db: Session, cabinet_id, entreprise_id: uuid.UUID, categorie: str, annee: int, mois: int
) -> tuple[list[EcritureComptable], dict[str, Decimal]]:
    """Reprend exactement la même logique de requête que
    GET /accounting/registers, pour ne jamais désynchroniser l'export
    de ce qui est affiché à l'écran."""
    query = (
        select(EcritureComptable)
        .join(Document, EcritureComptable.document_id == Document.id)
        .where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.entreprise_id == entreprise_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            Document.categorie == categorie,
            Document.annee == annee,
            Document.mois == mois,
        )
        .order_by(EcritureComptable.date_piece)
    )
    lignes = db.execute(query).scalars().all()

    totaux = {
        "total_ht": sum((l.montant_ht or Decimal("0.00") for l in lignes), Decimal("0.00")),
        "total_tva": sum((l.montant_tva or Decimal("0.00") for l in lignes), Decimal("0.00")),
        "total_ttc": sum((l.montant_ttc or Decimal("0.00") for l in lignes), Decimal("0.00")),
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
    return StreamingResponse(
        io.BytesIO(contenu),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=export_topaze_{ecriture.numero_piece or ecriture.id}.csv"},
    )


@router.get("/registers/{format}")
def export_registre(
    format: str,
    entreprise_id: uuid.UUID = Query(...),
    categorie: str = Query(...),
    annee: int = Query(...),
    mois: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    if format not in _MEDIA_TYPES:
        return Response(
            content=f"Format non supporté : {format}. Formats acceptés : xlsx, csv, pdf.",
            status_code=400,
        )

    lignes, totaux = _recuperer_lignes_et_totaux(
        db, current_user.cabinet_id, entreprise_id, categorie, annee, mois
    )
    titre = f"Registre {categorie} - {mois}/{annee}"

    if format == "xlsx":
        contenu = export_service.generer_excel(lignes, titre, totaux)
        nom_fichier = f"registre_{categorie}_{annee}_{mois}.xlsx"
    elif format == "csv":
        contenu = export_service.generer_csv(lignes, totaux)
        nom_fichier = f"registre_{categorie}_{annee}_{mois}.csv"
    else:  # pdf
        contenu = export_service.generer_pdf(lignes, titre, totaux)
        nom_fichier = f"registre_{categorie}_{annee}_{mois}.pdf"

    return Response(
        content=contenu,
        media_type=_MEDIA_TYPES[format],
        headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
    )