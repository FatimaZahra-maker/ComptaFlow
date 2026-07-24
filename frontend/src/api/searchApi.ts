// Appel API pour la recherche universelle (GET /search, voir
// backend/app/api/search.py).
import { apiClient } from "./client";
import type { SearchResults } from "../types/search";

export async function search(query: string): Promise<SearchResults> {
  const response = await apiClient.get<SearchResults>("/search", { params: { q: query } });
  return response.data;
}