"""Répare la synchronisation Documents -> Écritures comptables.

À exécuter depuis le dossier backend :

    python scripts\repair_accounting_entries.py

Le script ne relance ni OCR ni IA. Il utilise uniquement les données déjà
stockées dans ``documents.donnees_extraites`` pour :

- créer l'écriture manquante d'un document traité ;
- corriger les écritures classées ``autre`` alors que le document est un achat
  ou une vente ;
- supprimer les doublons d'écriture liés au même document ;
- préserver le statut de validation et la case Saisie Topaze des écritures
  déjà existantes ;
- ignorer les relevés bancaires, gérés par ``mouvements_bancaires``.
"""
from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import TypeEcritureEnum
from app.services.accounting_service import creer_ecriture_depuis_document


def _enum_value(value: object | None) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value)).strip().lower()


def _is_bank_document(document: Document) -> bool:
    data = document.donnees_extraites if isinstance(document.donnees_extraites, dict) else {}
    category = _enum_value(data.get("categorie") or data.get("categorie_document") or document.categorie)
    document_type = _enum_value(data.get("type_document"))
    return category in {"banque", "releve_bancaire"} or document_type == "releve_bancaire"


def main() -> None:
    print()
    print("=" * 76)
    print(" COMPTAFLOW — RÉPARATION DOCUMENTS / ÉCRITURES COMPTABLES")
    print("=" * 76)

    analysed = 0
    created = 0
    updated = 0
    unchanged = 0
    skipped_bank = 0
    skipped_no_company = 0
    errors = 0

    with SessionLocal() as db:
        documents = list(
            db.execute(select(Document).order_by(Document.created_at.asc()))
            .scalars()
            .all()
        )

    print(f"Documents trouvés : {len(documents)}\n")

    for detached_document in documents:
        analysed += 1

        if _is_bank_document(detached_document):
            skipped_bank += 1
            print(f"[BANQUE IGNORÉE] {detached_document.nom_fichier_original}")
            continue

        if detached_document.entreprise_id is None:
            skipped_no_company += 1
            print(f"[SANS ENTREPRISE] {detached_document.nom_fichier_original}")
            continue

        try:
            with SessionLocal() as db:
                document = db.get(Document, detached_document.id)
                if document is None:
                    errors += 1
                    print(f"[INTROUVABLE] {detached_document.id}")
                    continue

                existing = list(
                    db.execute(
                        select(EcritureComptable)
                        .where(EcritureComptable.document_id == document.id)
                        .order_by(EcritureComptable.created_at.asc())
                    )
                    .scalars()
                    .all()
                )

                previous = None
                if existing:
                    first = existing[0]
                    previous = {
                        "type": first.type_ecriture,
                        "statut_validation": first.statut_validation,
                        "validated_by": first.validated_by,
                        "saisie_topaze": first.saisie_topaze,
                    }

                repaired = creer_ecriture_depuis_document(db, document)

                # Ce script répare la synchronisation ; il ne doit pas annuler
                # une validation humaine ni décocher une saisie Topaze existante.
                if previous is not None:
                    repaired.statut_validation = previous["statut_validation"]
                    repaired.validated_by = previous["validated_by"]
                    repaired.saisie_topaze = previous["saisie_topaze"]
                    db.commit()
                    db.refresh(repaired)

                if previous is None:
                    created += 1
                    action = "CRÉÉE"
                elif previous["type"] != repaired.type_ecriture or len(existing) > 1:
                    updated += 1
                    action = "CORRIGÉE"
                else:
                    unchanged += 1
                    action = "OK"

                type_value = _enum_value(repaired.type_ecriture)
                print(
                    f"[{action}] {document.nom_fichier_original} -> "
                    f"{type_value} | entreprise={document.entreprise_id}"
                )

        except Exception as exc:
            errors += 1
            print(
                f"[ERREUR] {detached_document.nom_fichier_original} : "
                f"{type(exc).__name__}: {exc}"
            )

    print()
    print("=" * 76)
    print(" RÉSUMÉ")
    print("=" * 76)
    print(f"Documents analysés              : {analysed}")
    print(f"Écritures créées                : {created}")
    print(f"Écritures corrigées             : {updated}")
    print(f"Écritures déjà correctes        : {unchanged}")
    print(f"Relevés bancaires ignorés       : {skipped_bank}")
    print(f"Documents sans entreprise       : {skipped_no_company}")
    print(f"Erreurs                         : {errors}")
    print()

    if errors == 0:
        print("Réparation terminée. Actualisez Achats, Ventes et Écritures avec Ctrl+F5.")
    else:
        print("Réparation terminée avec des erreurs. Consultez les lignes [ERREUR].")


if __name__ == "__main__":
    main()
