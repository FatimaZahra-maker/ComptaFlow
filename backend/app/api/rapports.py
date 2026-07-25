"""
app/api/rapports.py

Routes de la page Rapports : consultation d'un rapport de synthèse
(JSON, pour affichage) et export PDF du même rapport.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_user_flexible
from app.models.user import User
from app.schemas.rapport import RapportOut
from app.services import rapport_service, export_service

router = APIRouter(prefix="/rapports", tags=["rapports"])


# Renvoie le rapport de synthèse calculé (affichage à l'écran).
@router.get("", response_model=RapportOut)
def get_rapport(
    entreprise_id: uuid.UUID = Query(...),
    annee: int = Query(...),
    mois: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return rapport_service.generer_rapport(db, current_user.cabinet_id, entreprise_id, annee, mois)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# Exporte le même rapport en PDF (lien <a href>, token en query param --
# même principe que les autres routes d'export du projet).
@router.get("/pdf")
def export_rapport_pdf(
    entreprise_id: uuid.UUID = Query(...),
    annee: int = Query(...),
    mois: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user_flexible),
):
    try:
        rapport = rapport_service.generer_rapport(db, current_user.cabinet_id, entreprise_id, annee, mois)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    contenu = export_service.generer_rapport_pdf(rapport)
    periode = f"{mois}_{annee}" if mois else str(annee)
    return Response(
        content=contenu,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="rapport_{periode}.pdf"'},
    )