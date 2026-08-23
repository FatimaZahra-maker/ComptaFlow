"""
Configure l'unique cabinet actif comme SEGURIBAT.

Ce script :
- ne touche pas aux mots de passe ;
- ne supprime ni ne modifie les entreprises existantes ;
- ne renseigne aucun ICE arbitraire ;
- refuse d'agir s'il existe zéro ou plusieurs cabinets actifs.

Usage depuis le dossier backend/ :

    python scripts/configurer_cabinet_seguribat.py
"""

import sys
from pathlib import Path

# Permet l'import de "app" lorsque le script est lancé depuis backend/.
BACKEND_DIR = Path(__file__).resolve().parent.parent

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal

# IMPORTANT :
# On importe Cabinet depuis app.models et non directement depuis
# app.models.cabinet. app.models charge le registre complet des modèles
# SQLAlchemy, notamment MouvementBancaire, nécessaire à la relation
# Document.mouvements_bancaires.
from app.models import Cabinet


NOM_CABINET = "SEGURIBAT"


def main() -> None:
    db = SessionLocal()

    try:
        cabinets = (
            db.query(Cabinet)
            .filter(Cabinet.is_active.is_(True))
            .all()
        )

        if not cabinets:
            raise RuntimeError(
                "Aucun cabinet actif trouvé. "
                "Crée d'abord le cabinet via l'application."
            )

        if len(cabinets) != 1:
            noms = ", ".join(
                cabinet.nom
                for cabinet in cabinets
            )

            raise RuntimeError(
                "Plusieurs cabinets actifs existent. "
                "Modification automatique refusée. "
                f"Cabinets trouvés : {noms}"
            )

        cabinet = cabinets[0]
        ancien_nom = cabinet.nom

        if ancien_nom == NOM_CABINET:
            print(
                f"Cabinet déjà configuré : "
                f"{NOM_CABINET} ({cabinet.id})"
            )
            print(
                "Les entreprises existantes "
                "n'ont pas été modifiées."
            )
            return

        cabinet.nom = NOM_CABINET

        db.commit()
        db.refresh(cabinet)

        print(
            f"Cabinet configuré : "
            f"{ancien_nom} -> {cabinet.nom}"
        )
        print(
            f"ID cabinet : {cabinet.id}"
        )
        print(
            "Les entreprises existantes "
            "n'ont pas été modifiées."
        )

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
