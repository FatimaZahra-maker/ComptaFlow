"""API de consultation/diagnostic des cours Bank Al-Maghrib."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services import exchange_rate_service

router = APIRouter(prefix="/exchange-rates", tags=["exchange-rates"])


@router.get("/bam/preview")
def preview_bam_rate(
    date_cours: date = Query(...),
    devise: str = Query(..., min_length=2, max_length=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Teste la récupération du cours Achat/Vente BAM pour une date précise."""
    del current_user  # auth requise, aucune donnée d'un autre cabinet n'est lue.

    code = exchange_rate_service.normaliser_devise(devise)
    if code is None:
        raise HTTPException(status_code=422, detail="Devise non reconnue.")
    if code == "MAD":
        return {
            "date_cours": date_cours.isoformat(),
            "devise": "MAD",
            "unite_cotation": 1,
            "cours_achat": "1",
            "cours_vente": "1",
            "source": "non_requise",
            "depuis_cache": True,
        }

    try:
        result = exchange_rate_service.obtenir_taux_bam(db, date_cours, code)
    except exchange_rate_service.TauxChangeIndisponible as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "date_cours": result.date_cours.isoformat(),
        "devise": result.devise,
        "libelle_bam": result.libelle_bam,
        "unite_cotation": result.unite_cotation,
        "cours_achat": format(result.cours_achat, "f"),
        "cours_vente": format(result.cours_vente, "f"),
        "source": result.source,
        "source_url": result.source_url,
        "depuis_cache": result.depuis_cache,
    }
