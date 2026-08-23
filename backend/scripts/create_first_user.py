"""
backend/scripts/create_first_user.py

Script de bootstrap : cree un cabinet de test + un premier utilisateur
Admin Cabinet, pour pouvoir tester /auth/login.
A lancer UNE SEULE FOIS (il ne recree rien si ca existe deja).

Usage (depuis backend/, avec l'env conda comptaflow active) :
    python scripts/create_first_user.py
"""
import argparse
import getpass
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

def _lire_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Créer le premier administrateur ComptaFlow.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--cabinet", required=True, dest="cabinet_nom")
    parser.add_argument("--nom", required=True)
    parser.add_argument("--prenom", required=True)
    return parser.parse_args()


def main() -> None:
    args = _lire_arguments()
    password = getpass.getpass("Mot de passe administrateur : ")
    confirmation = getpass.getpass("Confirmer le mot de passe : ")
    if password != confirmation or len(password) < 12:
        raise SystemExit("Le mot de passe doit correspondre et contenir au moins 12 caractères.")

    db = SessionLocal()
    try:
        cabinet = db.query(Cabinet).filter(Cabinet.nom == args.cabinet_nom).first()
        if cabinet is None:
            cabinet = Cabinet(nom=args.cabinet_nom)
            db.add(cabinet)
            db.commit()
            db.refresh(cabinet)

        if db.query(User).filter(User.email == args.email).first() is not None:
            raise SystemExit("Un utilisateur avec cet email existe déjà.")

        db.add(User(
            cabinet_id=cabinet.id,
            email=args.email,
            hashed_password=hash_password(password),
            nom=args.nom,
            prenom=args.prenom,
            role=RoleEnum.ADMIN_CABINET,
        ))
        db.commit()
        print("Administrateur créé avec succès.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
