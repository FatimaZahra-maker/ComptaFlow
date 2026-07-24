"""
app/api/chronos.py

Vue "Chrono" — tableau comptable complet : joint Document + Entreprise
+ EcritureComptable (LEFT OUTER, un document peut ne pas encore avoir
d'écriture) pour que le frontend affiche tout en une seule requête :
fichier, entreprise, catégorie, montants HT/TVA/TTC, statut de
validation, suivi de saisie Topaze.

CORRECTIF (normalisation des filtres) : traite "toutes"/""/"all" comme
absence de filtre, quelle que soit la convention utilisée côté client.

Route /annees : retourne les années RÉELLEMENT présentes dans les
documents du cabinet -- évite qu'un filtre Année codé en dur côté
frontend exclue silencieusement des documents (ex: un modèle de
facture daté 2020 alors que seules 2024-2026 étaient proposées).
"""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.document import Document
from app.models.entreprise import Entreprise
from app.models.ecriture import EcritureComptable
from app.schemas.chrono import DocumentChronoOut

router = APIRouter(prefix="/chronos", tags=["chronos"])

_VALEURS_VIDES = {"", "toutes", "tous", "all", "none", "null"}


def _normaliser_filtre(valeur: str | None) -> str | None:
    """Traite 'toutes'/''/'all' (insensible à la casse) comme une
    absence de filtre -- sécurise contre n'importe quelle convention
    utilisée côté frontend pour représenter 'pas de filtre'."""
    if valeur is None:
        return None
    if valeur.strip().lower() in _VALEURS_VIDES:
        return None
    return valeur


@router.get("/documents", response_model=list[DocumentChronoOut])
def list_chrono_documents(
    entreprise_id: str | None = Query(default=None),
    categorie: str | None = Query(default=None),
    annee: int | None = Query(default=None),
    mois: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entreprise_id_normalise = _normaliser_filtre(entreprise_id)
    categorie_normalisee = _normaliser_filtre(categorie)

    query = (
        select(Document, Entreprise.nom, EcritureComptable)
        .join(Entreprise, Document.entreprise_id == Entreprise.id, isouter=True)
        .join(EcritureComptable, EcritureComptable.document_id == Document.id, isouter=True)
        .where(Document.cabinet_id == current_user.cabinet_id)
    )

    if entreprise_id_normalise is not None:
        try:
            entreprise_uuid = uuid.UUID(entreprise_id_normalise)
            query = query.where(Document.entreprise_id == entreprise_uuid)
        except ValueError:
            pass  # valeur non-UUID inattendue -- on ignore plutôt que de planter

    if categorie_normalisee is not None:
        query = query.where(Document.categorie == categorie_normalisee.lower())

    if annee is not None:
        query = query.where(Document.annee == annee)
    if mois is not None:
        query = query.where(Document.mois == mois)

    query = query.order_by(Document.created_at.desc())

    resultats = db.execute(query).all()

    sortie: list[DocumentChronoOut] = []
    for document, entreprise_nom, ecriture in resultats:
        item = DocumentChronoOut.model_validate(document)
        item.entreprise_nom = entreprise_nom
        if ecriture is not None:
            item.ecriture_id = ecriture.id
            item.numero_piece = ecriture.numero_piece
            item.date_piece = ecriture.date_piece
            item.tiers = ecriture.tiers
            item.montant_ht = ecriture.montant_ht
            item.taux_tva = ecriture.taux_tva.value if hasattr(ecriture.taux_tva, "value") else ecriture.taux_tva
            item.montant_tva = ecriture.montant_tva
            item.montant_ttc = ecriture.montant_ttc
            item.statut_validation = (
                ecriture.statut_validation.value
                if hasattr(ecriture.statut_validation, "value")
                else ecriture.statut_validation
            )
            item.anomalie_detectee = ecriture.anomalie_detectee
            item.anomalie_details = ecriture.anomalie_details
            item.saisie_topaze = ecriture.saisie_topaze
        sortie.append(item)
    return sortie


@router.get("/annees", response_model=list[int])
def list_annees_disponibles(
    entreprise_id: str | None = Query(default=None),
    categorie: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retourne la liste des années RÉELLEMENT présentes dans les documents
    du cabinet (triée décroissante) -- le filtre Année du frontend n'est
    ainsi jamais figé sur une liste codée en dur.
    """
    entreprise_id_normalise = _normaliser_filtre(entreprise_id)
    categorie_normalisee = _normaliser_filtre(categorie)

    query = (
        select(Document.annee)
        .where(Document.cabinet_id == current_user.cabinet_id, Document.annee.isnot(None))
        .distinct()
    )
    if entreprise_id_normalise is not None:
        try:
            query = query.where(Document.entreprise_id == uuid.UUID(entreprise_id_normalise))
        except ValueError:
            pass
    if categorie_normalisee is not None:
        query = query.where(Document.categorie == categorie_normalisee.lower())

    annees = [row[0] for row in db.execute(query).all()]
    return sorted(annees, reverse=True)