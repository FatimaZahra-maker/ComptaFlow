import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";

// Importation des composants existants
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
import { RapportsPage } from "./pages/RapportsPage";
// SUPPRIMÉ : ParametresPage (déjà retiré précédemment)

// --- NOUVELLES IMPORTATIONS AJOUTÉES ---
import { AchatsPage } from "./pages/AchatsPage";
import { VentesPage } from "./pages/VentesPage";
import { RelevesBancairesPage } from "./pages/RelevesBancairesPage";

// SUPPRIMÉ : import { CnssPage } from "./pages/CnssPage";
// La page CNSS est retirée complètement du projet (menu + route),
// à la demande de l'utilisateur.

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* ---- ROUTE PUBLIQUE ---- */}
          <Route path="/login" element={<LoginPage />} />

          {/* ---- ROUTES PROTÉGÉES ---- */}
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
          <Route
            path="/admin/utilisateurs"
            element={
              <ProtectedRoute>
                <Layout><AdminUsersPage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/tva-mensuelle"
            element={
              <ProtectedRoute>
                <Layout><TvaMensuellePage /></Layout>
              </ProtectedRoute>
            }
          />
          <Route
            path="/rappels"
            element={
              <ProtectedRoute>
                <Layout><RappelsPage /></Layout>
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

          {/* --- NOUVELLES ROUTES POUR LES TABLEAUX --- */}
          <Route 
            path="/achats" 
            element={
              <ProtectedRoute>
                <Layout><AchatsPage /></Layout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/ventes" 
            element={
              <ProtectedRoute>
                <Layout><VentesPage /></Layout>
              </ProtectedRoute>
            } 
          />
          <Route 
            path="/banque" 
            element={
              <ProtectedRoute>
                <Layout><RelevesBancairesPage /></Layout>
              </ProtectedRoute>
            } 
          />

          {/* SUPPRIMÉ : route "/cnss" retirée avec la page */}

          {/* ---- ROUTE PAR DÉFAUT (CATCH-ALL) ---- */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}