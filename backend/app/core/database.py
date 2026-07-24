"""
app/core/database.py

Crée l'engine SQLAlchemy (connexion au pool Postgres) et la fabrique de
sessions utilisée par chaque endpoint FastAPI via Depends(get_db).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """Classe de base pour TOUS les modèles (Cabinet, User, Document...)."""
    pass


engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency FastAPI : ouvre une session, la donne à l'endpoint,
    puis la ferme automatiquement (même en cas d'erreur).
    Usage dans une route : db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()