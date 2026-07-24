"""
app/api/search.py

Route de recherche universelle (Phase 7) : une seule barre de recherche
qui interroge en parallèle Entreprises, Documents et Écritures, et
renvoie une liste unifiée de résultats.

Champs recherchés (tous existants dans le schéma actuel, aucun champ
inventé) :
- Entreprise.nom, Entreprise.ice
- Document.nom_fichier_original, Document.texte_ocr
- EcritureComptable.tiers, EcritureComptable.numero_piece

Tout est filtré sur cabinet_id (règle de sécurité du projet).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, or_

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.entreprise import Entreprise
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.schemas.search import SearchResultItem, SearchResultsOut

router = APIRouter(prefix="/search", tags=["search"])

MAX_RESULTATS_PAR_TYPE = 10
LONGUEUR_MIN_REQUETE = 2


@router.get("", response_model=SearchResultsOut)
def search(
    q: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resultats: list[SearchResultItem] = []
    terme = q.strip()

    # Une requête trop courte (1 caractère) produirait trop de bruit
    # sur du texte OCR entier -- on renvoie une liste vide plutôt que
    # de scanner inutilement toute la base.
    if len(terme) < LONGUEUR_MIN_REQUETE:
        return SearchResultsOut(query=q, resultats=[])

    motif = f"%{terme}%"

    # --- Entreprises : nom ou ICE ---
    entreprises = db.execute(
        select(Entreprise)
        .where(
            Entreprise.cabinet_id == current_user.cabinet_id,
            or_(Entreprise.nom.ilike(motif), Entreprise.ice.ilike(motif)),
        )
        .limit(MAX_RESULTATS_PAR_TYPE)
    ).scalars().all()
    for entreprise in entreprises:
        resultats.append(SearchResultItem(
            type="entreprise",
            id=entreprise.id,
            titre=entreprise.nom,
            sous_titre=f"ICE : {entreprise.ice}" if entreprise.ice else None,
            route="/chronos",
        ))

    # --- Documents : nom de fichier ou texte OCR ---
    documents = db.execute(
        select(Document)
        .where(
            Document.cabinet_id == current_user.cabinet_id,
            or_(Document.nom_fichier_original.ilike(motif), Document.texte_ocr.ilike(motif)),
        )
        .limit(MAX_RESULTATS_PAR_TYPE)
    ).scalars().all()
    for document in documents:
        resultats.append(SearchResultItem(
            type="document",
            id=document.id,
            titre=document.nom_fichier_original,
            sous_titre=document.categorie.value if document.categorie else document.statut.value,
            route=f"/documents/{document.id}",
        ))

    # --- Écritures : tiers ou numéro de pièce ---
    ecritures = db.execute(
        select(EcritureComptable)
        .where(
            EcritureComptable.cabinet_id == current_user.cabinet_id,
            or_(EcritureComptable.tiers.ilike(motif), EcritureComptable.numero_piece.ilike(motif)),
        )
        .limit(MAX_RESULTATS_PAR_TYPE)
    ).scalars().all()
    for ecriture in ecritures:
        resultats.append(SearchResultItem(
            type="ecriture",
            id=ecriture.id,
            titre=ecriture.tiers or "Tiers inconnu",
            sous_titre=f"{ecriture.numero_piece or '—'} · {ecriture.montant_ttc} MAD",
            route=f"/documents/{ecriture.document_id}",
        ))

    return SearchResultsOut(query=q, resultats=resultats)