import axios from "axios";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000")
  .replace(/\/$/, "");

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

// Attache automatiquement le token JWT (s'il existe) à chaque requête sortante
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("comptaflow_token") ?? sessionStorage.getItem("comptaflow_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Si le backend répond 401 (token expiré/invalide), on déconnecte
// automatiquement l'utilisateur plutôt que de le laisser sur une page cassée.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("comptaflow_token");
      sessionStorage.removeItem("comptaflow_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

export async function fetchApiBlob(
  url: string,
  params?: Record<string, string | number | undefined>,
): Promise<Blob> {
  const response = await apiClient.get<Blob>(url, { params, responseType: "blob" });
  return response.data;
}

export async function downloadApiBlob(
  url: string,
  filename: string,
  params?: Record<string, string | number | undefined>,
): Promise<void> {
  const blob = await fetchApiBlob(url, params);
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}
