"""
Configure le cabinet actif unique comme SEGURIBAT.

Ce script ne touche ni aux mots de passe ni aux entreprises existantes.
Il ne renseigne pas d'ICE arbitraire : l'ICE peut ensuite être complété depuis
la page Paramètres si nécessaire.

Usage depuis backend/ :
    python scripts/configurer_cabinet_seguridad.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models.cabinet import Cabinet

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
                "Aucun cabinet actif trouvé. Crée d'abord le cabinet via l'application."
            )

        if len(cabinets) != 1:
            noms = ", ".join(cabinet.nom for cabinet in cabinets)
            raise RuntimeError(
                "Plusieurs cabinets actifs existent. Modification automatique refusée. "
                f"Cabinets trouvés : {noms}"
            )

        cabinet = cabinets[0]
        ancien_nom = cabinet.nom

        if ancien_nom == NOM_CABINET:
            print(f"Cabinet déjà configuré : {NOM_CABINET} ({cabinet.id})")
            return

        cabinet.nom = NOM_CABINET
        db.commit()
        db.refresh(cabinet)

        print(f"Cabinet configuré : {ancien_nom} -> {cabinet.nom}")
        print(f"ID cabinet : {cabinet.id}")
        print("Les entreprises existantes n'ont pas été modifiées.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
