import { useState, useEffect, useRef, type ReactNode } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { search } from "../api/searchApi";
import { getNotifications } from "../api/notificationsApi";
import { listEntreprises } from "../api/entreprisesApi";
import type { SearchResultItem } from "../types/search";
import type { Notification } from "../types/notification";
import type { Entreprise } from "../types/entreprise";
import { useAuth } from "../context/AuthContext";
import { ResizableSidebar } from "./ResizableSidebar";

const TYPE_LABELS: Record<string, string> = {
  entreprise: "Entreprise",
  document: "Document",
  ecriture: "Écriture",
};

const TYPE_COLORS: Record<string, string> = {
  entreprise: "bg-purple-100 text-purple-700",
  document: "bg-blue-100 text-blue-700",
  ecriture: "bg-green-100 text-green-700",
};

const NOTIF_TYPE_COLORS: Record<string, string> = {
  document_erreur: "bg-red-100 text-red-700",
  ecriture_anomalie: "bg-orange-100 text-orange-700",
  ecriture_a_verifier: "bg-orange-100 text-orange-700",
  document_nouveau: "bg-blue-100 text-blue-700",
};

const NOTIF_TYPE_ICONS: Record<string, string> = {
  document_erreur: "✕",
  ecriture_anomalie: "⚠",
  ecriture_a_verifier: "⚠",
  document_nouveau: "●",
};

interface NavItemExtended {
  label: string;
  icon: string;
  route: string;
  disponible?: boolean;
}

// disponible: false -- section visible dans la sidebar (comme la
// maquette) mais grisée et non cliquable : ce sont de vraies pages qui
// n'ont pas encore de backend/UI derrière (Clients et Fournisseurs,
// Rappels & Tâches, Rapports, Paramètres), à construire plus tard.
const NAV_ITEMS: NavItemExtended[] = [
  { label: "Tableau de bord", icon: "🏠", route: "/dashboard" },
  { label: "Documents", icon: "📄", route: "/upload" },
  { label: "Chronos", icon: "🕐", route: "/chronos" },
  { label: "Écritures", icon: "📑", route: "/registers" },
  { label: "Registres", icon: "📊", route: "/registres" },
  { label: "Clients et Fournisseurs", icon: "👥", route: "/tiers", disponible: false },
  { label: "Rappels & Tâches", icon: "🗓️", route: "/rappels", disponible: false },
  { label: "Notifications", icon: "🔔", route: "/notifications" },
  { label: "Rapports", icon: "📈", route: "/rapports", disponible: false },
  { label: "Utilisateurs", icon: "👤", route: "/admin/utilisateurs" },
  { label: "Paramètres", icon: "⚙️", route: "/parametres", disponible: false },
];

export const ACTIVE_ENTREPRISE_KEY = "comptaflow_active_entreprise_id";

const DEBOUNCE_MS = 300;
const NOTIF_POLL_MS = 15000;

export function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [activeEntrepriseId, setActiveEntrepriseId] = useState<string | null>(
    () => localStorage.getItem(ACTIVE_ENTREPRISE_KEY)
  );

  useEffect(() => {
    listEntreprises().then(setEntreprises);
  }, []);

  function selectEntreprise(id: string | null) {
    setActiveEntrepriseId(id);
    if (id) localStorage.setItem(ACTIVE_ENTREPRISE_KEY, id);
    else localStorage.removeItem(ACTIVE_ENTREPRISE_KEY);
    window.dispatchEvent(new CustomEvent("entreprise-active-changed", { detail: id }));
  }

  const [query, setQuery] = useState("");
  const [resultats, setResultats] = useState<SearchResultItem[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim().length < 2) {
      setResultats([]);
      setIsSearchOpen(false);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setIsSearching(true);
      try {
        const data = await search(query.trim());
        setResultats(data.resultats);
        setIsSearchOpen(true);
      } finally {
        setIsSearching(false);
      }
    }, DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [query]);

  function handleSelectResult(item: SearchResultItem) {
    setIsSearchOpen(false);
    setQuery("");
    navigate(item.route);
  }

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const notifContainerRef = useRef<HTMLDivElement>(null);

  const refreshNotifications = async () => {
    try {
      const data = await getNotifications();
      setNotifications(data.notifications);
    } catch {
      // silencieux -- le prochain polling réessaiera
    }
  };

  useEffect(() => {
    refreshNotifications();
    const interval = setInterval(refreshNotifications, NOTIF_POLL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (searchContainerRef.current && !searchContainerRef.current.contains(event.target as Node)) {
        setIsSearchOpen(false);
      }
      if (notifContainerRef.current && !notifContainerRef.current.contains(event.target as Node)) {
        setIsNotifOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleSelectNotification(notification: Notification) {
    setIsNotifOpen(false);
    navigate(notification.route);
  }

  return (
    <div className="min-h-screen flex bg-gray-50">
      <ResizableSidebar
        storageKey="main-nav"
        defaultWidth={240}
        minWidth={180}
        maxWidth={360}
        className="bg-[#0f1a3c] text-gray-300"
      >
        <div className="flex flex-col h-full">
          <div className="px-4 py-4 flex items-center gap-2 border-b border-white/10">
            <span className="text-xl">☁️</span>
            <span className="text-white font-semibold">ComptaFlow</span>
          </div>

          <nav className="px-3 py-4 space-y-0.5">
            <p className="px-2 text-[10px] uppercase tracking-wide text-gray-500 mb-1">Vue d'ensemble</p>
            {NAV_ITEMS.map((item) => {
              const active = location.pathname === item.route;
              const disponible = item.disponible !== false;
              return (
                <button
                  key={item.route}
                  onClick={() => disponible && navigate(item.route)}
                  disabled={!disponible}
                  title={!disponible ? "Bientôt disponible" : undefined}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded text-sm transition ${
                    !disponible
                      ? "text-gray-500 opacity-50 cursor-not-allowed"
                      : active
                      ? "bg-green-600/90 text-white"
                      : "text-gray-300 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  <span className="w-4 text-center">{item.icon}</span>
                  {item.label}
                  {item.route === "/notifications" && notifications.length > 0 && (
                    <span className="ml-auto bg-red-500 text-white text-[10px] rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center">
                      {notifications.length > 9 ? "9+" : notifications.length}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>

          <div className="px-3 pt-2 pb-4 mt-auto border-t border-white/10">
            <p className="px-2 text-[10px] uppercase tracking-wide text-gray-500 mb-1">Entreprises</p>
            <button
              onClick={() => selectEntreprise(null)}
              className={`w-full text-left px-2.5 py-1.5 rounded text-sm mb-0.5 ${
                activeEntrepriseId === null ? "bg-white/10 text-white" : "text-gray-300 hover:bg-white/5"
              }`}
            >
              Toutes
            </button>
            {entreprises.map((e) => (
              <button
                key={e.id}
                onClick={() => selectEntreprise(e.id)}
                className={`w-full text-left px-2.5 py-1.5 rounded text-sm mb-0.5 flex items-center gap-1.5 ${
                  activeEntrepriseId === e.id ? "bg-white/10 text-white" : "text-gray-300 hover:bg-white/5"
                }`}
              >
                <span className="truncate">{e.nom}</span>
                {e.creee_automatiquement && (
                  <span className="text-orange-400 text-xs shrink-0" title="Créée automatiquement, à vérifier">●</span>
                )}
              </button>
            ))}
            <button
              onClick={() => navigate("/upload")}
              className="w-full text-left px-2.5 py-1.5 rounded text-xs text-green-300 hover:bg-white/5 mt-1"
            >
              + Ajouter une entreprise
            </button>
          </div>
        </div>
      </ResizableSidebar>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 bg-white border-b flex items-center gap-4 px-6">
          <div ref={searchContainerRef} className="relative flex-1 max-w-md">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => resultats.length > 0 && setIsSearchOpen(true)}
              placeholder="Rechercher (facture, ICE, tiers...)"
              className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
            />
            {isSearchOpen && (
              <div className="absolute mt-1 w-full bg-white border rounded-lg shadow-lg max-h-96 overflow-auto z-20">
                {isSearching && <p className="p-3 text-sm text-gray-400">Recherche...</p>}
                {!isSearching && resultats.length === 0 && (
                  <p className="p-3 text-sm text-gray-400">Aucun résultat pour "{query}".</p>
                )}
                {!isSearching &&
                  resultats.map((item) => (
                    <button
                      key={`${item.type}-${item.id}`}
                      onClick={() => handleSelectResult(item)}
                      className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b last:border-0 flex items-center gap-2"
                    >
                      <span className={`text-xs px-1.5 py-0.5 rounded shrink-0 ${TYPE_COLORS[item.type]}`}>
                        {TYPE_LABELS[item.type]}
                      </span>
                      <span className="text-sm truncate">
                        <span className="font-medium">{item.titre}</span>
                        {item.sous_titre && <span className="text-gray-400"> · {item.sous_titre}</span>}
                      </span>
                    </button>
                  ))}
              </div>
            )}
          </div>

          <div ref={notifContainerRef} className="relative shrink-0 ml-auto">
            <button
              onClick={() => setIsNotifOpen((open) => !open)}
              className="relative text-gray-500 hover:text-gray-700 text-lg px-1"
              title="Notifications"
            >
              🔔
              {notifications.length > 0 && (
                <span className="absolute -top-1 -right-1 bg-red-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
                  {notifications.length > 9 ? "9+" : notifications.length}
                </span>
              )}
            </button>
            {isNotifOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-white border rounded-lg shadow-lg max-h-96 overflow-auto z-20">
                <div className="px-3 py-2 border-b">
                  <p className="text-sm font-medium">Notifications</p>
                </div>
                {notifications.length === 0 && <p className="p-3 text-sm text-gray-400">Aucune notification.</p>}
                {notifications.map((notification) => (
                  <button
                    key={notification.id}
                    onClick={() => handleSelectNotification(notification)}
                    className="w-full text-left px-3 py-2 hover:bg-gray-50 border-b last:border-0 flex items-start gap-2"
                  >
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded shrink-0 mt-0.5 ${
                        NOTIF_TYPE_COLORS[notification.type] ?? "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {NOTIF_TYPE_ICONS[notification.type] ?? "•"}
                    </span>
                    <span className="text-sm">
                      {notification.message}
                      {notification.entreprise_nom && (
                        <span className="block text-xs text-gray-400">{notification.entreprise_nom}</span>
                      )}
                    </span>
                  </button>
                ))}
                {notifications.length > 0 && (
                  <button
                    onClick={() => { setIsNotifOpen(false); navigate("/notifications"); }}
                    className="w-full text-center px-3 py-2 text-xs text-green-700 hover:bg-gray-50 font-medium border-t"
                  >
                    Voir toutes les notifications →
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="text-right leading-tight shrink-0">
            <p className="text-sm font-medium">{user?.email ?? "Cabinet"}</p>
            <p className="text-xs text-gray-400">{user?.role ?? ""}</p>
          </div>
          <button
            onClick={logout}
            className="w-8 h-8 rounded-full bg-green-100 text-green-700 text-xs font-semibold flex items-center justify-center shrink-0"
            title="Déconnexion"
          >
            {(user?.nom?.[0] ?? "U").toUpperCase()}
          </button>
        </header>

        <main className="flex-1 min-w-0 overflow-auto">{children}</main>
      </div>
    </div>
  );
}