r"""Import CSV du plan comptable d'une entreprise.

Exemple :
    python scripts/importer_plan_comptable_csv.py \
        --entreprise-id UUID \
        --fichier C:\chemin\plan_anzo.csv

Colonnes attendues :
numero_compte;libelle;famille_cgnc;type_usage;nature_comptable;tiers_nom;est_divers
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys
import uuid

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import SessionLocal
from app.models import Entreprise
from app.services.plan_comptable_service import creer_ou_mettre_a_jour_compte


def _vers_bool(valeur: object | None) -> bool:
    return str(valeur or "").strip().lower() in {"1", "true", "vrai", "oui", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entreprise-id", required=True)
    parser.add_argument("--fichier", required=True)
    args = parser.parse_args()

    entreprise_id = uuid.UUID(args.entreprise_id)
    chemin = Path(args.fichier)

    if not chemin.exists():
        raise FileNotFoundError(chemin)

    db = SessionLocal()

    try:
        entreprise = db.get(Entreprise, entreprise_id)
        if entreprise is None:
            raise RuntimeError("Entreprise introuvable.")

        texte = chemin.read_text(encoding="utf-8-sig")
        premiere_ligne = texte.splitlines()[0] if texte.splitlines() else ""
        separateur = ";" if premiere_ligne.count(";") >= premiere_ligne.count(",") else ","

        lecteur = csv.DictReader(texte.splitlines(), delimiter=separateur)
        crees = 0
        mis_a_jour = 0

        for numero_ligne, ligne in enumerate(lecteur, start=2):
            numero_compte = (ligne.get("numero_compte") or "").strip()
            libelle = (ligne.get("libelle") or "").strip()

            if not numero_compte or not libelle:
                print(f"Ligne {numero_ligne} ignorée : compte/libellé absent.")
                continue

            _, cree = creer_ou_mettre_a_jour_compte(
                db,
                cabinet_id=entreprise.cabinet_id,
                entreprise_id=entreprise.id,
                numero_compte=numero_compte,
                libelle=libelle,
                famille_cgnc=(ligne.get("famille_cgnc") or None),
                type_usage=(ligne.get("type_usage") or "autre"),
                nature_comptable=(ligne.get("nature_comptable") or None),
                tiers_nom=(ligne.get("tiers_nom") or None),
                est_divers=_vers_bool(ligne.get("est_divers")),
                is_active=True,
                source="import_csv",
            )

            if cree:
                crees += 1
            else:
                mis_a_jour += 1

        db.commit()
        print(f"Entreprise : {entreprise.nom}")
        print(f"Comptes créés : {crees}")
        print(f"Comptes mis à jour : {mis_a_jour}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
