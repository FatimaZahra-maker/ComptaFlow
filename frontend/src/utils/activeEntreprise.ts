export const ACTIVE_ENTREPRISE_KEY = "comptaflow_active_entreprise_id";
export const ACTIVE_ENTREPRISE_EVENT = "entreprise-active-changed";

export function getActiveEntrepriseId(): string | null {
  try { return localStorage.getItem(ACTIVE_ENTREPRISE_KEY); } catch { return null; }
}

export function setActiveEntrepriseId(id: string | null): void {
  try {
    if (id) localStorage.setItem(ACTIVE_ENTREPRISE_KEY, id);
    else localStorage.removeItem(ACTIVE_ENTREPRISE_KEY);
  } catch {
    // Le changement reste propagé pour la session courante.
  }
  window.dispatchEvent(new CustomEvent(ACTIVE_ENTREPRISE_EVENT, { detail: id }));
}
