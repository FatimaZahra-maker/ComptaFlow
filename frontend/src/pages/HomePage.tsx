import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, BarChart3, Bell, Bot, Building2, FileText, FolderUp, HelpCircle, Moon, PieChart, ShieldCheck, UserRound } from "lucide-react";
import { listChronoDocuments } from "../api/chronosApi";
import { useAuth } from "../context/AuthContext";
import "./HomePage.css";
import "./HomePageFix.css";

export function HomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [counters, setCounters] = useState({ unidentified: 0, toVerify: 0 });

  useEffect(() => {
    let active = true;
    listChronoDocuments().then((documents) => {
      if (!active) return;
      setCounters({
        unidentified: documents.filter((document) => !document.entreprise_id || document.entreprise_nom?.toLocaleLowerCase("fr").includes("à identifier")).length,
        toVerify: documents.filter((document) => document.statut_validation === "a_verifier" || document.statut === "erreur").length,
      });
    }).catch(() => active && setCounters({ unidentified: 0, toVerify: 0 }));
    return () => { active = false; };
  }, []);

  const fullName = useMemo(() => [user?.prenom, user?.nom].filter(Boolean).join(" ") || user?.email || "Utilisateur", [user]);
  const initials = [user?.prenom?.[0], user?.nom?.[0]].filter(Boolean).join("").toUpperCase() || "CF";

  return (
    <div className="home-shell">
      <header className="home-header">
        <button type="button" className="home-brand" onClick={() => navigate("/accueil")} aria-label="Accueil ComptaFlow">
          <span className="home-brand-mark">CF</span><span className="home-brand-name">COMPTAFLOW</span><span className="home-brand-divider" /><span className="home-brand-tagline">Votre comptabilité, simplifiée.</span>
        </button>
        <nav className="home-actions" aria-label="Actions rapides">
          <button type="button" onClick={() => navigate("/notifications")} aria-label="Notifications"><Bell /></button>
          <button type="button" onClick={() => navigate("/assistant")} aria-label="Aide"><HelpCircle /></button>
          <button type="button" aria-label="Mode sombre" title="Thème sombre bientôt disponible"><Moon /></button>
          <span className="home-user-divider" />
          <button type="button" className="home-user" onClick={() => navigate("/admin/utilisateurs")}><span className="home-avatar">{initials}</span><span><strong>{fullName}</strong><small>{user?.role?.replaceAll("_", " ")}</small></span></button>
        </nav>
      </header>
      <main className="home-main">
        <div className="home-orb home-orb-left" /><div className="home-orb home-orb-right" /><div className="home-dots home-dots-left" /><div className="home-dots home-dots-right" />
        <section className="home-content">
          <h1>Que souhaitez-vous faire aujourd’hui&nbsp;?</h1><span className="home-title-line" />
          <div className="home-choice-grid">
            <button type="button" className="home-choice-card" onClick={() => navigate("/upload")}>
              <span className="home-illustration" aria-hidden="true"><span className="home-illustration-halo" /><FileText className="home-paper home-paper-main" /><FileText className="home-paper home-paper-side" /><span className="home-folder"><FolderUp /></span></span>
              <span className="home-card-title">Importer<br />de nouveaux documents</span><span className="home-card-arrow"><ArrowRight /></span>
            </button>
            <div className="home-choice-wrap">
              <button type="button" className="home-choice-card" onClick={() => navigate("/entreprises/selection")} aria-describedby="company-card-description">
                <span className="home-illustration" aria-hidden="true"><span className="home-illustration-halo" /><BarChart3 className="home-chart home-chart-left" /><PieChart className="home-chart home-chart-right" /><span className="home-building"><Building2 /></span><span className="home-person"><UserRound /></span></span>
                <span className="home-card-title">Travailler sur<br />une entreprise</span><span className="home-card-arrow"><ArrowRight /></span>
              </button>
              <p id="company-card-description" role="tooltip" className="home-card-tooltip">Accédez au dossier d’une entreprise, consultez ses documents et suivez le traitement comptable.</p>
            </div>
          </div>
          <div className="home-secondary-actions">
            <button type="button" onClick={() => navigate("/chronos?non_identifies=1")}><ShieldCheck /> Documents à identifier <strong>{counters.unidentified}</strong></button>
            <button type="button" onClick={() => navigate("/chronos?a_verifier=1")}><FileText /> Documents à vérifier <strong>{counters.toVerify}</strong></button>
          </div>
        </section>
        <button type="button" className="home-assistant-button" onClick={() => navigate("/assistant")} aria-label="Ouvrir l’Assistant ComptaFlow"><Bot /></button>
      </main>
    </div>
  );
}
