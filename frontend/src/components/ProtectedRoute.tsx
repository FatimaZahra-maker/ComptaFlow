import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, isLoading } = useAuth();

  if (isLoading) return <div className="p-8 text-gray-500">Chargement...</div>;
  if (!user) return <Navigate to="/login" replace />;

  return <>{children}</>;
}