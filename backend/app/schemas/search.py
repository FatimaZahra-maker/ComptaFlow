"""
app/schemas/search.py

Schéma de sortie de la recherche universelle (Phase 7). Une seule
requête peut toucher plusieurs types d'objets (entreprise, document,
écriture) -- chaque résultat est donc normalisé sous une forme commune
(SearchResultItem) avec un "type" pour que le frontend sache vers quelle
page naviguer au clic.
"""
import uuid

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    type: str          # "entreprise" | "document" | "ecriture"
    id: uuid.UUID
    titre: str          # ce qui s'affiche en gras (ex: nom entreprise, nom fichier, tiers)
    sous_titre: str | None = None  # complément (ex: ICE, catégorie, montant)
    route: str           # route frontend vers laquelle naviguer au clic


class SearchResultsOut(BaseModel):
    query: str
    resultats: list[SearchResultItem]