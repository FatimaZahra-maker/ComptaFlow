import { createContext, useContext, useState, useEffect, type ReactNode } from "react";
import { getCurrentUser } from "../api/authApi";
import type { User } from "../types/auth";

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  setToken: (token: string, remember?: boolean) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Au chargement de l'app : si un token existe déjà (rafraîchissement de
  // page), on essaie de récupérer l'utilisateur pour rester connecté.
  useEffect(() => {
    const token = localStorage.getItem("comptaflow_token") ?? sessionStorage.getItem("comptaflow_token");
    if (!token) {
      setIsLoading(false);
      return;
    }
    getCurrentUser()
      .then(setUser)
      .catch(() => {
        localStorage.removeItem("comptaflow_token");
        sessionStorage.removeItem("comptaflow_token");
      })
      .finally(() => setIsLoading(false));
  }, []);

  async function setToken(token: string, remember = true) {
    localStorage.removeItem("comptaflow_token");
    sessionStorage.removeItem("comptaflow_token");
    (remember ? localStorage : sessionStorage).setItem("comptaflow_token", token);
    try {
      setUser(await getCurrentUser());
    } catch (error) {
      localStorage.removeItem("comptaflow_token");
      sessionStorage.removeItem("comptaflow_token");
      throw error;
    }
  }

  function logout() {
    localStorage.removeItem("comptaflow_token");
    sessionStorage.removeItem("comptaflow_token");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, isLoading, setToken, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé dans un AuthProvider");
  return context;
}
