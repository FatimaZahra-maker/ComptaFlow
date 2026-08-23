import { lazy, Suspense, type ReactNode } from "react";
import {
  BrowserRouter,
  Navigate,
  Route,
  Routes,
} from "react-router-dom";

import { Layout } from "./components/Layout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";

const AchatsPage = lazy(() => import("./pages/AchatsPage").then((m) => ({ default: m.AchatsPage })));
const AdminUsersPage = lazy(() => import("./pages/AdminUsersPage").then((m) => ({ default: m.AdminUsersPage })));
const ChronosPage = lazy(() => import("./pages/ChronosPage").then((m) => ({ default: m.ChronosPage })));
const CloturePage = lazy(() => import("./pages/CloturePage").then((m) => ({ default: m.CloturePage })));
const CpcPage = lazy(() => import("./pages/CpcPage").then((m) => ({ default: m.CpcPage })));
const GrandLivrePage = lazy(() => import("./pages/GrandLivrePage").then((m) => ({ default: m.GrandLivrePage })));
const BalancePage = lazy(() => import("./pages/BalancePage").then((m) => ({ default: m.BalancePage })));
const BilanPage = lazy(() => import("./pages/BilanPage").then((m) => ({ default: m.BilanPage })));
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const DocumentDetailPage = lazy(() => import("./pages/DocumentDetailPage").then((m) => ({ default: m.DocumentDetailPage })));
const LoginPage = lazy(() => import("./pages/LoginPage").then((m) => ({ default: m.LoginPage })));
const NotificationsPage = lazy(() => import("./pages/NotificationsPage").then((m) => ({ default: m.NotificationsPage })));
const RappelsPage = lazy(() => import("./pages/RappelsPage").then((m) => ({ default: m.RappelsPage })));
const RapportsPage = lazy(() => import("./pages/RapportsPage").then((m) => ({ default: m.RapportsPage })));
const RegistersPage = lazy(() => import("./pages/RegistersPage").then((m) => ({ default: m.RegistersPage })));
const RegistreComptablePage = lazy(() => import("./pages/RegistreComptablePage").then((m) => ({ default: m.RegistreComptablePage })));
const RelevesBancairesPage = lazy(() => import("./pages/RelevesBancairesPage").then((m) => ({ default: m.RelevesBancairesPage })));
const ComptesBancairesPage = lazy(() => import("./pages/ComptesBancairesPage").then((m) => ({ default: m.ComptesBancairesPage })));
const TvaMensuellePage = lazy(() => import("./pages/TvaMensuellePage").then((m) => ({ default: m.TvaMensuellePage })));
const UploadPage = lazy(() => import("./pages/UploadPage").then((m) => ({ default: m.UploadPage })));
const VentesPage = lazy(() => import("./pages/VentesPage").then((m) => ({ default: m.VentesPage })));
const PreCloturePage = lazy(() => import("./pages/PreCloturePage").then((m) => ({ default: m.PreCloturePage })));

function PrivatePage({ children }: { children: ReactNode }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Chargement…</div>}>
        <Routes>
          {/* Route publique */}
          <Route path="/login" element={<LoginPage />} />

          {/* La racine ouvre directement le tableau de bord. */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          <Route
            path="/dashboard"
            element={<PrivatePage><DashboardPage /></PrivatePage>}
          />

          {/* Documents : /upload reste l'URL historique du projet. */}
          <Route
            path="/upload"
            element={<PrivatePage><UploadPage /></PrivatePage>}
          />
          <Route path="/documents" element={<Navigate to="/upload" replace />} />
          <Route
            path="/documents/:id"
            element={<PrivatePage><DocumentDetailPage /></PrivatePage>}
          />

          <Route
            path="/chronos"
            element={<PrivatePage><ChronosPage /></PrivatePage>}
          />

          {/* Écritures et vues métier réelles. */}
          <Route
            path="/registers"
            element={<PrivatePage><RegistersPage /></PrivatePage>}
          />
          <Route path="/ecritures" element={<Navigate to="/registers" replace />} />
          <Route
            path="/achats"
            element={<PrivatePage><AchatsPage /></PrivatePage>}
          />
          <Route
            path="/ventes"
            element={<PrivatePage><VentesPage /></PrivatePage>}
          />
          <Route
            path="/banque"
            element={<PrivatePage><RelevesBancairesPage /></PrivatePage>}
          />
          <Route
            path="/comptes-bancaires"
            element={<PrivatePage><ComptesBancairesPage /></PrivatePage>}
          />
          <Route
            path="/registres"
            element={<PrivatePage><RegistreComptablePage /></PrivatePage>}
          />
          <Route
            path="/tva-mensuelle"
            element={<PrivatePage><TvaMensuellePage /></PrivatePage>}
          />
          <Route
            path="/grand-livre"
            element={<PrivatePage><GrandLivrePage /></PrivatePage>}
          />
          <Route
            path="/balance"
            element={<PrivatePage><BalancePage /></PrivatePage>}
          />
          <Route
            path="/cpc"
            element={<PrivatePage><CpcPage /></PrivatePage>}
          />
          <Route
            path="/bilan"
            element={<PrivatePage><BilanPage /></PrivatePage>}
          />
          <Route
            path="/cloture"
            element={<PrivatePage><CloturePage /></PrivatePage>}
          />
          <Route
            path="/controles"
            element={<PrivatePage><PreCloturePage /></PrivatePage>}
          />

          <Route
            path="/rappels"
            element={<PrivatePage><RappelsPage /></PrivatePage>}
          />
          <Route path="/taches" element={<Navigate to="/rappels" replace />} />
          <Route
            path="/notifications"
            element={<PrivatePage><NotificationsPage /></PrivatePage>}
          />
          <Route
            path="/rapports"
            element={<PrivatePage><RapportsPage /></PrivatePage>}
          />
          <Route
            path="/admin/utilisateurs"
            element={<PrivatePage><AdminUsersPage /></PrivatePage>}
          />
          <Route
            path="/utilisateurs"
            element={<Navigate to="/admin/utilisateurs" replace />}
          />

          {/* Toute URL inconnue revient sur une page fonctionnelle. */}
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  );
}
