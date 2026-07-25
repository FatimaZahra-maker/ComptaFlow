import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";

// Importation des composants correspondant aux différentes pages de l'application
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
import { UploadPage } from "./pages/UploadPage";
import { RegistersPage } from "./pages/RegistersPage";
import { ChronosPage } from "./pages/ChronosPage";
import { DocumentDetailPage } from "./pages/DocumentDetailPage";
import { RegistreComptablePage } from "./pages/RegistreComptablePage";
import { DashboardPage } from "./pages/DashboardPage";
import { NotificationsPage } from "./pages/NotificationsPage";
import { AdminUsersPage } from "./pages/AdminUsersPage";
import { TvaMensuellePage } from "./pages/TvaMensuellePage";
import { RappelsPage } from "./pages/RappelsPage";

// Nouveaux imports ajoutés
import { ParametresPage } from "./pages/ParametresPage";
import { RapportsPage } from "./pages/RapportsPage";

export default function App() {
  return (
    // BrowserRouter gère l'historique de navigation et l'URL dans le navigateur
    <BrowserRouter>
      {/* AuthProvider englobe l'application pour fournir le contexte d'authentification à tous les composants enfants */}
      <AuthProvider>
        <Routes>
          {/* ---- ROUTE PUBLIQUE ---- */}
          {/* Accessible sans être connecté */}
          <Route path="/login" element={<LoginPage />} />

          {/* ---- ROUTES PROTÉGÉES ---- */}
          {/* Toutes ces routes nécessitent que l'utilisateur soit authentifié (géré par <ProtectedRoute>). 
              Si l'utilisateur est connecté, la page s'affiche à l'intérieur de la structure commune <Layout> (navbar, sidebar, etc.). */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout><HomePage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/upload"
            element={
              <ProtectedRoute>
                <Layout><UploadPage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/registers"
            element={
              <ProtectedRoute>
                <Layout><RegistersPage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/chronos"
            element={
              <ProtectedRoute>
                <Layout><ChronosPage /></Layout>
              </ProtectedRoute>
            }
          />
          
          {/* Route dynamique : ":id" permet de récupérer l'identifiant du document dans le composant DocumentDetailPage */}
          <Route
            path="/documents/:id"
            element={
              <ProtectedRoute>
                <Layout><DocumentDetailPage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/registres"
            element={
              <ProtectedRoute>
                <Layout><RegistreComptablePage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Layout><DashboardPage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/notifications"
            element={
              <ProtectedRoute>
                <Layout><NotificationsPage /></Layout>
              </ProtectedRoute>
            }
          />
          
          {/* Route réservée à l'administration */}
          <Route
            path="/admin/utilisateurs"
            element={
              <ProtectedRoute>
                <Layout><AdminUsersPage /></Layout>
              </ProtectedRoute>
            }
          />

          {/* Route pour consulter la ventilation mensuelle de la TVA */}
          <Route
            path="/tva-mensuelle"
            element={
              <ProtectedRoute>
                <Layout><TvaMensuellePage /></Layout>
              </ProtectedRoute>
            }
          />

          {/* Route pour les Rappels & Tâches */}
          <Route
            path="/rappels"
            element={
              <ProtectedRoute>
                <Layout><RappelsPage /></Layout>
              </ProtectedRoute>
            }
          />

          {/* --- NOUVELLES ROUTES --- */}
          <Route 
            path="/parametres" 
            element={
              <ProtectedRoute>
                <Layout><ParametresPage /></Layout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/rapports" 
            element={
              <ProtectedRoute>
                <Layout><RapportsPage /></Layout>
              </ProtectedRoute>
            } 
          />

          {/* ---- ROUTE PAR DÉFAUT (CATCH-ALL) ---- */}
          {/* Si l'utilisateur tente d'accéder à une URL qui n'est pas définie ci-dessus, il est automatiquement redirigé vers la racine "/" */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}