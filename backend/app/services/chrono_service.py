"""
app/services/chrono_service.py

Un chrono par entreprise, créé automatiquement à la première apparition
de cette entreprise (voir chrono.py : UniqueConstraint sur entreprise_id).
"""
import uuid
from sqlalchemy.orm import Session

from app.models.chrono import Chrono


def obtenir_ou_creer_chrono(db: Session, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID) -> Chrono:
    chrono = db.query(Chrono).filter_by(entreprise_id=entreprise_id).first()
    if chrono is None:
        chrono = Chrono(cabinet_id=cabinet_id, entreprise_id=entreprise_id)
        db.add(chrono)
        db.commit()
        db.refresh(chrono)
    return chrono