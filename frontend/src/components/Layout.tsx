import { useState, useEffect, useRef, type ReactNode } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { search } from "../api/searchApi";
import { getNotifications } from "../api/notificationsApi";
import { listEntreprises } from "../api/entreprisesApi";
import { listTaches } from "../api/tachesApi";
import type { SearchResultItem } from "../types/search";
import type { Notification } from "../types/notification";
import type { Entreprise } from "../types/entreprise";
import { useAuth } from "../context/AuthContext";
import { ResizableSidebar } from "./ResizableSidebar";
import {
  Home,
  FileText,
  Clock,
  ShoppingCart,
  TrendingUp,
  Landmark,
  BookOpenText,
  FileStack,
  Receipt,
  CalendarClock,
  Bell,
  BarChart3,
  UserCog,
  Plus,
  Cloud,
  type LucideIcon,
} from "lucide-react";

/* ============================================================
   CONFIGURATION D'AFFICHAGE (labels, couleurs, icônes des badges)
   ============================================================ */
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

/* ============================================================
   MENU LATÉRAL — structure en groupes
   ------------------------------------------------------------
   AJOUTÉ : le menu est désormais un tableau de GROUPES (chacun
   avec un titre de section) plutôt qu'une liste plate d'items.
   Pour ajouter/retirer une page du menu, repérez le bon groupe
   ci-dessous et modifiez uniquement son tableau `items`.
   ============================================================ */
interface NavItemExtended {
  label: string;
  icon: LucideIcon;
  route: string;
  disponible?: boolean;
}

interface NavGroup {
  titre: string;
  items: NavItemExtended[];
}

const NAV_GROUPS: NavGroup[] = [
  // --- GROUPE 1 : VUE D'ENSEMBLE ---
  {
    titre: "Vue d'ensemble",
    items: [
      { label: "Tableau de bord", icon: Home, route: "/dashboard" },
      { label: "Documents", icon: FileText, route: "/upload" },
      { label: "Chronos", icon: Clock, route: "/chronos" },
    ],
  },
  // --- GROUPE 2 : GESTION COMPTABLE ---
  {
    titre: "Gestion comptable",
    items: [
      { label: "Achats", icon: ShoppingCart, route: "/achats" },
      { label: "Ventes", icon: TrendingUp, route: "/ventes" },
      { label: "Banque", icon: Landmark, route: "/banque" },
      { label: "Écritures", icon: BookOpenText, route: "/registers" },
      { label: "Registres", icon: FileStack, route: "/registres" },
      { label: "TVA mensuelle", icon: Receipt, route: "/tva-mensuelle" },
    ],
  },
  // --- GROUPE 3 : ORGANISATION ---
  {
    titre: "Organisation",
    items: [
      { label: "Rappels & Tâches", icon: CalendarClock, route: "/rappels" },
      { label: "Notifications", icon: Bell, route: "/notifications" },
      { label: "Rapports", icon: BarChart3, route: "/rapports" },
      { label: "Utilisateurs", icon: UserCog, route: "/admin/utilisateurs" },
    ],
  },
];

export const ACTIVE_ENTREPRISE_KEY = "comptaflow_active_entreprise_id";

const DEBOUNCE_MS = 300;
const NOTIF_POLL_MS = 15000;
const RAPPELS_POLL_MS = 30000;

export function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  /* ============================================================
     ENTREPRISES (sélecteur en bas de la sidebar) — INCHANGÉ
     ============================================================ */
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

  /* ============================================================
     BARRE DE RECHERCHE (header)
     ============================================================ */
  const [query, setQuery] = useState("");
  const [resultats, setResultats] = useState<SearchResultItem[]>([]);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (query.trim().length < 2) {
      setResultats([]);
      setIsSearchOpen(false);
      setSearchError(null);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setIsSearching(true);
      setSearchError(null);
      try {
        const data = await search(query.trim());
        setResultats(data.resultats);
        setIsSearchOpen(true);
      } catch (error) {
        console.error("Erreur lors de la recherche universelle :", error);
        setResultats([]);
        setSearchError("La recherche a échoué. Vérifiez votre connexion et réessayez.");
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

  /* ============================================================
     NOTIFICATIONS (cloche du header)
     ============================================================ */
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isNotifOpen, setIsNotifOpen] = useState(false);
  const notifContainerRef = useRef<HTMLDivElement>(null);

  const refreshNotifications = async () => {
    try {
      const data = await getNotifications();
      setNotifications(data.notifications);
    } catch {
      // silencieux -- le prochain polling réessaiera en cas d'erreur réseau
    }
  };

  useEffect(() => {
    refreshNotifications();
    const interval = setInterval(refreshNotifications, NOTIF_POLL_MS);
    return () => clearInterval(interval);
  }, []);

  function handleSelectNotification(notification: Notification) {
    setIsNotifOpen(false);
    navigate(notification.route);
  }

  /* ============================================================
     BADGE "Rappels & Tâches" (nombre de tâches dans le menu)
     ============================================================ */
  const [rappelsCount, setRappelsCount] = useState(0);

  const refreshRappels = async () => {
    try {
      const taches = await listTaches();
      setRappelsCount(taches.length);
    } catch {
      // silencieux -- comme pour les notifications, on retente au prochain polling
    }
  };

  useEffect(() => {
    refreshRappels();
    const interval = setInterval(refreshRappels, RAPPELS_POLL_MS);
    return () => clearInterval(interval);
  }, []);

  /* ============================================================
     FERMETURE DES MENUS DÉROULANTS AU CLIC EXTÉRIEUR
     ============================================================ */
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

  /* ============================================================
     RENDU
     ============================================================ */
  return (
    <div className="min-h-screen flex bg-gray-50">
      <ResizableSidebar
        storageKey="main-nav"
        defaultWidth={240}
        minWidth={180}
        maxWidth={360}
        className="bg-gradient-to-b from-green-900 to-green-950 text-gray-300"
      >
        <div className="flex flex-col h-full">
          {/* ---------- LOGO ComptaFlow ---------- */}
          <div className="px-4 py-4 flex items-center gap-2 border-b border-white/10">
            <div className="w-7 h-7 rounded-lg bg-green-500 flex items-center justify-center shrink-0">
              <Cloud size={16} className="text-white" />
            </div>
            <span className="text-white font-semibold">ComptaFlow</span>
          </div>

          {/* ----------------------------------------------------
              MENU DE NAVIGATION — 3 groupes avec séparateurs
              Pour ajouter/enlever une page : modifier NAV_GROUPS
              plus haut, pas cette boucle de rendu.
              ---------------------------------------------------- */}
          <nav className="px-3 py-4 space-y-3 overflow-y-auto">
            {NAV_GROUPS.map((groupe) => (
              <div key={groupe.titre}>
                {/* Titre du groupe + ligne de séparation */}
                <p className="px-2 text-[10px] uppercase tracking-wide text-gray-500 mb-1">
                  {groupe.titre}
                </p>
                <div className="border-t border-white/10 mb-1.5" />

                {groupe.items.map((item) => {
                  const active = location.pathname === item.route;
                  const disponible = item.disponible !== false;
                  const Icon = item.icon;
                  const badgeCount =
                    item.route === "/notifications"
                      ? notifications.length
                      : item.route === "/rappels"
                      ? rappelsCount
                      : 0;

                  return (
                    <button
                      key={item.route}
                      onClick={() => disponible && navigate(item.route)}
                      disabled={!disponible}
                      title={!disponible ? "Bientôt disponible" : undefined}
                      className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition ${
                        !disponible
                          ? "text-gray-500 opacity-50 cursor-not-allowed"
                          : active
                          ? "bg-green-600 text-white shadow-sm"
                          : "text-gray-300 hover:bg-white/5 hover:text-white"
                      }`}
                    >
                      <Icon size={16} className="shrink-0" />
                      <span className="truncate">{item.label}</span>
                      {badgeCount > 0 && (
                        <span
                          className={`ml-auto text-[10px] rounded-full min-w-[16px] h-4 px-1 flex items-center justify-center ${
                            item.route === "/notifications"
                              ? "bg-red-500 text-white"
                              : "bg-white/15 text-white"
                          }`}
                        >
                          {badgeCount > 9 ? "9+" : badgeCount}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
          </nav>

          {/* ----------------------------------------------------
              SECTION ENTREPRISES (bas de la sidebar) — INCHANGÉE
              ---------------------------------------------------- */}
          <div className="px-3 pt-2 pb-4 mt-auto border-t border-white/10">
            <p className="px-2 text-[10px] uppercase tracking-wide text-gray-500 mb-1">Entreprises</p>

            <button
              onClick={() => selectEntreprise(null)}
              className={`w-full text-left px-2.5 py-1.5 rounded text-sm mb-0.5 font-medium ${
                activeEntrepriseId === null ? "text-green-400" : "text-gray-300 hover:bg-white/5"
              }`}
            >
              Toutes les entreprises
            </button>

            {entreprises.map((e) => (
              <button
                key={e.id}
                onClick={() => selectEntreprise(e.id)}
                className={`w-full text-left px-2.5 py-1.5 rounded text-sm mb-0.5 flex items-center justify-between gap-1.5 ${
                  activeEntrepriseId === e.id ? "bg-white/10 text-white" : "text-gray-300 hover:bg-white/5"
                }`}
              >
                <span className="truncate">{e.nom}</span>
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    e.creee_automatiquement ? "bg-orange-400" : "bg-green-400"
                  }`}
                  title={e.creee_automatiquement ? "Créée automatiquement, à vérifier" : "Active"}
                />
              </button>
            ))}

            <button
              onClick={() => navigate("/upload")}
              className="w-full flex items-center justify-center gap-1.5 mt-3 border border-green-700/60 text-green-300 rounded-lg py-2 text-xs font-medium hover:bg-green-800/40 transition-colors"
            >
              <Plus size={13} />
              Ajouter une entreprise
            </button>
          </div>
        </div>
      </ResizableSidebar>

      {/* ============================================================
          COLONNE PRINCIPALE (header + contenu de la page)
          ============================================================ */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-14 shrink-0 bg-white border-b flex items-center gap-4 px-6">
          {/* ---------- Barre de recherche ---------- */}
          <div ref={searchContainerRef} className="relative flex-1 max-w-md">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onFocus={() => (resultats.length > 0 || searchError) && setIsSearchOpen(true)}
              placeholder="Rechercher (facture, ICE, tiers...)"
              className="w-full border rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-green-200 focus:border-green-400"
            />
            {isSearchOpen && (
              <div className="absolute mt-1 w-full bg-white border rounded-lg shadow-lg max-h-96 overflow-auto z-20">
                {isSearching && <p className="p-3 text-sm text-gray-400">Recherche...</p>}
                {!isSearching && searchError && (
                  <p className="p-3 text-sm text-red-500">{searchError}</p>
                )}
                {!isSearching && !searchError && resultats.length === 0 && (
                  <p className="p-3 text-sm text-gray-400">Aucun résultat pour "{query}".</p>
                )}
                {!isSearching &&
                  !searchError &&
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

          {/* ---------- Cloche de notifications ---------- */}
          <div ref={notifContainerRef} className="relative shrink-0 ml-auto">
            <button
              onClick={() => setIsNotifOpen((open) => !open)}
              className="relative text-gray-500 hover:text-gray-700 px-1"
              title="Notifications"
            >
              <Bell size={19} />
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
                    onClick={() => {
                      setIsNotifOpen(false);
                      navigate("/notifications");
                    }}
                    className="w-full text-center px-3 py-2 text-xs text-green-700 hover:bg-gray-50 font-medium border-t"
                  >
                    Voir toutes les notifications →
                  </button>
                )}
              </div>
            )}
          </div>

          {/* ---------- Utilisateur connecté + déconnexion ---------- */}
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

        {/* ---------- Contenu de la page active ---------- */}
        <main className="flex-1 min-w-0 overflow-auto">{children}</main>
      </div>
    </div>
  );
}