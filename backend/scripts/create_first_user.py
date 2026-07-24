"""
backend/scripts/create_first_user.py

Script de bootstrap : cree un cabinet de test + un premier utilisateur
Admin Cabinet, pour pouvoir tester /auth/login.
A lancer UNE SEULE FOIS (il ne recree rien si ca existe deja).

Usage (depuis backend/, avec l'env conda comptaflow active) :
    python scripts/create_first_user.py
"""
import sys
from pathlib import Path

# Permet d'importer le package "app" meme en lancant ce script
# depuis le sous-dossier scripts/.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.cabinet import Cabinet
from app.models.user import User
from app.models.enums import RoleEnum

db = SessionLocal()

try:
    cabinet = db.query(Cabinet).filter(Cabinet.nom == "Cabinet Test").first()
    if cabinet is None:
        cabinet = Cabinet(nom="Cabinet Test")
        db.add(cabinet)
        db.commit()
        db.refresh(cabinet)
        print(f"Cabinet cree : {cabinet.id}")
    else:
        print(f"Cabinet deja existant : {cabinet.id}")

    existing_user = db.query(User).filter(User.email == "admin@comptaflow-dev.ma").first()
    if existing_user is not None:
        print("L'utilisateur admin@comptaflow-dev.ma existe deja. Rien a faire.")
    else:
        user = User(
            cabinet_id=cabinet.id,
            email="admin@comptaflow-dev.ma",
            hashed_password=hash_password("MotDePasse123!"),
            nom="Admin",
            prenom="Test",
            role=RoleEnum.ADMIN_CABINET,
        )
        db.add(user)
        db.commit()
        print("Utilisateur cree : admin@comptaflow-dev.ma / MotDePasse123!")

finally:
    db.close()