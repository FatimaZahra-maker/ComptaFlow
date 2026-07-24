import axios from "axios";

export const apiClient = axios.create({
  baseURL: "http://localhost:8000",
});

// Attache automatiquement le token JWT (s'il existe) à chaque requête sortante
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("comptaflow_token");
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
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);