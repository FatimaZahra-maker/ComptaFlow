// Types correspondant au schéma Pydantic SearchResultsOut
// (backend/app/schemas/search.py).

export interface SearchResultItem {
  type: "entreprise" | "document" | "ecriture";
  id: string;
  titre: string;
  sous_titre: string | null;
  route: string;
}

export interface SearchResults {
  query: string;
  resultats: SearchResultItem[];
}