import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";
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

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
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
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}