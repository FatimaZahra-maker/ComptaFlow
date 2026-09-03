"""
app/tasks/ai_enrichment.py

Tâche Celery SÉPARÉE de process_document -- enrichit un document déjà
TRAITÉ avec les champs sémantiques IA (nom_entreprise, tiers, categorie)
en arrière-plan, SANS que le comptable attende ce résultat pour voir
son document.

Déclenchée en fin de process_document.py, en "fire and forget"
(.delay()) : le pipeline principal ne bloque jamais sur celle-ci.

Si cette tâche échoue ou timeout, le document garde les valeurs de la
Phase 1 (regex + heuristique + ML) -- aucune régression possible, juste
une opportunité d'amélioration manquée.
"""
import logging

from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.services import ai_service, workflow_comptable_service

logger = logging.getLogger("comptaflow.pipeline")


@celery_app.task(name="enrichir_document_ia", bind=True, max_retries=1)
def enrichir_document_ia(self, document_id: str):
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        if document is None or not document.texte_ocr:
            return
        workflow_comptable_service.verifier_document_modifiable(db, document)

        donnees = dict(document.donnees_extraites or {})
        type_document = donnees.get("type_document", "autre")

        resultat_ia = ai_service.enrichir_avec_ia(document.texte_ocr, type_document)

        if not resultat_ia:
            donnees["enrichissement_ia_statut"] = "echec"
            document.donnees_extraites = donnees
            db.commit()
            logger.info("Document %s | Enrichissement IA : aucun résultat exploitable", document_id)
            return

        conf = donnees.setdefault("confiance_par_champ", {})

        if "nom_entreprise" in resultat_ia:
            donnees["nom_entreprise"] = resultat_ia["nom_entreprise"]
            conf["nom_entreprise"] = resultat_ia["conf_nom_entreprise"]

        if "tiers" in resultat_ia:
            donnees["tiers"] = resultat_ia["tiers"]
            conf["tiers"] = resultat_ia["conf_tiers"]

        categorie_amelioree = "categorie" in resultat_ia
        if categorie_amelioree:
            donnees["categorie"] = resultat_ia["categorie"]
            conf["categorie"] = resultat_ia["conf_categorie"]

        donnees["enrichissement_ia_statut"] = "termine"
        document.donnees_extraites = donnees

        # Si la catégorie a changé, l'écriture comptable déjà créée
        # (type_ecriture dérivé de l'ancienne catégorie) doit être
        # resynchronisée -- sinon l'IA améliore le classement affiché
        # mais pas l'écriture comptable réelle.
        if categorie_amelioree:
            document.categorie = donnees["categorie"]
            ecriture = db.query(EcritureComptable).filter(
                EcritureComptable.document_id == document.id
            ).first()
            if ecriture is not None:
                from app.services.accounting_service import _determiner_type_ecriture
                ecriture.type_ecriture = _determiner_type_ecriture(donnees["categorie"])

        db.commit()
        logger.info("Document %s | Enrichissement IA terminé", document_id)

    except Exception as exc:
        db.rollback()
        logger.warning("Document %s | Enrichissement IA échoué (non bloquant) : %s", document_id, exc)

    finally:
        db.close()
