import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import {
  BarChart3,
  Bell,
  Building2,
  BookOpen,
  BookOpenText,
  CalendarClock,
  CalendarCheck,
  ClipboardCheck,
  Cloud,
  Clock,
  FileStack,
  FileText,
  Home,
  Landmark,
  LogOut,
  Plus,
  Receipt,
  Scale,
  Search,
  ShoppingCart,
  TrendingUp,
  UserCog,
  X,
  type LucideIcon,
} from "lucide-react";

import { getNotifications } from "../api/notificationsApi";
import { search } from "../api/searchApi";
import { listEntreprises } from "../api/entreprisesApi";
import { listTaches } from "../api/tachesApi";
import { useAuth } from "../context/AuthContext";
import { ResizableSidebar } from "./ResizableSidebar";

import type { Entreprise } from "../types/entreprise";
import type { Notification } from "../types/notification";
import type { SearchResultItem } from "../types/search";

export const ACTIVE_ENTREPRISE_KEY = "comptaflow_active_entreprise_id";

const SEARCH_DELAY_MS = 300;
const NOTIFICATIONS_REFRESH_MS = 15_000;
const TASKS_REFRESH_MS = 30_000;

interface NavigationItem {
  label: string;
  route: string;
  icon: LucideIcon;
}

interface NavigationGroup {
  title: string;
  items: NavigationItem[];
}

const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    title: "Vue d'ensemble",
    items: [
      { label: "Tableau de bord", route: "/dashboard", icon: Home },
      { label: "Documents", route: "/upload", icon: FileText },
      { label: "Chronos", route: "/chronos", icon: Clock },
    ],
  },
  {
    title: "Gestion comptable",
    items: [
      { label: "Achats", route: "/achats", icon: ShoppingCart },
      { label: "Ventes", route: "/ventes", icon: TrendingUp },
      { label: "Banque", route: "/banque", icon: Landmark },
      { label: "Comptes bancaires", route: "/comptes-bancaires", icon: Landmark },
      { label: "Écritures", route: "/registers", icon: BookOpenText },
      { label: "Registres", route: "/registres", icon: FileStack },
      { label: "Grand Livre", route: "/grand-livre", icon: BookOpen },
      { label: "Balance", route: "/balance", icon: Scale },
      { label: "TVA mensuelle", route: "/tva-mensuelle", icon: Receipt },
      { label: "CPC", route: "/cpc", icon: BarChart3 },
      { label: "Bilan", route: "/bilan", icon: Building2 },
      { label: "Cloture", route: "/cloture", icon: CalendarCheck },
      { label: "Pré-clôture", route: "/controles", icon: ClipboardCheck },
    ],
  },
  {
    title: "Organisation",
    items: [
      { label: "Rappels & Tâches", route: "/rappels", icon: CalendarClock },
      { label: "Notifications", route: "/notifications", icon: Bell },
      { label: "Rapports", route: "/rapports", icon: BarChart3 },
      { label: "Utilisateurs", route: "/admin/utilisateurs", icon: UserCog },
    ],
  },
];

const SEARCH_TYPE_LABELS: Record<string, string> = {
  entreprise: "Entreprise",
  document: "Document",
  ecriture: "Écriture",
};

const SEARCH_TYPE_CLASSES: Record<string, string> = {
  entreprise: "bg-purple-100 text-purple-700",
  document: "bg-blue-100 text-blue-700",
  ecriture: "bg-green-100 text-green-700",
};

const NOTIFICATION_CLASSES: Record<string, string> = {
  document_erreur: "bg-red-100 text-red-700",
  ecriture_anomalie: "bg-orange-100 text-orange-700",
  ecriture_a_verifier: "bg-orange-100 text-orange-700",
  document_nouveau: "bg-blue-100 text-blue-700",
};

function getRequestError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (!error.response) return "Backend inaccessible. Vérifiez que Uvicorn est démarré.";
    return `Erreur API ${error.response.status}.`;
  }
  return "Erreur inattendue.";
}

function isRouteActive(pathname: string, route: string): boolean {
  if (route === "/upload") {
    return pathname === "/upload" || pathname === "/documents";
  }
  return pathname === route || pathname.startsWith(`${route}/`);
}

export function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();

  const [companies, setCompanies] = useState<Entreprise[]>([]);
  const [activeCompanyId, setActiveCompanyId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(ACTIVE_ENTREPRISE_KEY);
    } catch {
      return null;
    }
  });

  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResultItem[]>([]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);

  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [tasksCount, setTasksCount] = useState(0);

  const searchContainerRef = useRef<HTMLDivElement>(null);
  const notificationContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listEntreprises()
      .then(setCompanies)
      .catch(() => setCompanies([]));
  }, []);

  const refreshNotifications = useCallback(async () => {
    try {
      const data = await getNotifications();
      setNotifications(data.notifications);
    } catch {
      // Le polling réessaiera automatiquement.
    }
  }, []);

  const refreshTasks = useCallback(async () => {
    try {
      const tasks = await listTaches();
      setTasksCount(tasks.length);
    } catch {
      // Le polling réessaiera automatiquement.
    }
  }, []);

  useEffect(() => {
    void refreshNotifications();
    const timer = window.setInterval(refreshNotifications, NOTIFICATIONS_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refreshNotifications]);

  useEffect(() => {
    void refreshTasks();
    const timer = window.setInterval(refreshTasks, TASKS_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [refreshTasks]);

  useEffect(() => {
    const term = query.trim();
    if (term.length < 2) {
      setSearchResults([]);
      setSearchError(null);
      setSearching(false);
      setSearchOpen(false);
      return;
    }

    let active = true;
    const timer = window.setTimeout(async () => {
      setSearching(true);
      setSearchError(null);
      setSearchOpen(true);

      try {
        const data = await search(term);
        if (!active) return;
        setSearchResults(Array.isArray(data.resultats) ? data.resultats : []);
      } catch (error) {
        if (!active) return;
        setSearchResults([]);
        setSearchError(getRequestError(error));
      } finally {
        if (active) setSearching(false);
      }
    }, SEARCH_DELAY_MS);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    function handleOutsideClick(event: MouseEvent) {
      const target = event.target as Node;
      if (searchContainerRef.current && !searchContainerRef.current.contains(target)) {
        setSearchOpen(false);
      }
      if (
        notificationContainerRef.current &&
        !notificationContainerRef.current.contains(target)
      ) {
        setNotificationsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  useEffect(() => {
    setSearchOpen(false);
    setNotificationsOpen(false);
  }, [location.pathname]);

  function selectCompany(id: string | null) {
    setActiveCompanyId(id);
    try {
      if (id) localStorage.setItem(ACTIVE_ENTREPRISE_KEY, id);
      else localStorage.removeItem(ACTIVE_ENTREPRISE_KEY);
    } catch {
      // Le filtre reste actif pour la session même sans localStorage.
    }
    window.dispatchEvent(
      new CustomEvent("entreprise-active-changed", { detail: id }),
    );
  }

  function selectSearchResult(item: SearchResultItem) {
    setSearchOpen(false);
    setQuery("");
    navigate(item.route);
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <ResizableSidebar
        storageKey="main-nav"
        defaultWidth={260}
        minWidth={210}
        maxWidth={360}
        className="bg-gradient-to-b from-green-900 to-green-950 text-green-50"
      >
        <div className="flex min-h-full flex-col">
          <div className="flex items-center gap-3 border-b border-white/10 px-5 py-5">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-green-500 shadow-lg shadow-green-950/20">
              <Cloud size={21} />
            </div>
            <div className="min-w-0">
              <p className="truncate text-lg font-bold text-white">ComptaFlow</p>
              <p className="text-[11px] text-green-200/70">Gestion comptable intelligente</p>
            </div>
          </div>

          <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-5">
            {NAVIGATION_GROUPS.map((group) => (
              <section key={group.title}>
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-green-200/50">
                  {group.title}
                </p>
                <div className="space-y-1">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = isRouteActive(location.pathname, item.route);
                    const badge = item.route === "/notifications"
                      ? notifications.length
                      : item.route === "/rappels"
                        ? tasksCount
                        : 0;

                    return (
                      <button
                        key={item.route}
                        type="button"
                        onClick={() => navigate(item.route)}
                        className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${
                          active
                            ? "bg-green-500 text-white shadow-lg shadow-green-950/20"
                            : "text-green-50/85 hover:bg-white/10 hover:text-white"
                        }`}
                      >
                        <Icon size={18} className="shrink-0" />
                        <span className="truncate">{item.label}</span>
                        {badge > 0 && (
                          <span className="ml-auto flex min-w-5 items-center justify-center rounded-full bg-white/20 px-1.5 py-0.5 text-[10px] text-white">
                            {badge > 99 ? "99+" : badge}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            ))}
          </nav>

          <div className="border-t border-white/10 p-3">
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-green-200/50">
              Entreprises
            </p>
            <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
              <button
                type="button"
                onClick={() => selectCompany(null)}
                className={`w-full rounded-lg px-3 py-2 text-left text-sm ${
                  activeCompanyId === null
                    ? "bg-white/15 text-white"
                    : "text-green-50/80 hover:bg-white/10"
                }`}
              >
                Toutes les entreprises
              </button>
              {companies.map((company) => (
                <button
                  key={company.id}
                  type="button"
                  onClick={() => selectCompany(company.id)}
                  className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${
                    activeCompanyId === company.id
                      ? "bg-white/15 text-white"
                      : "text-green-50/80 hover:bg-white/10"
                  }`}
                >
                  <span className="truncate">{company.nom}</span>
                  <span
                    className={`ml-auto h-2 w-2 shrink-0 rounded-full ${
                      company.creee_automatiquement ? "bg-orange-400" : "bg-green-400"
                    }`}
                  />
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => navigate("/upload")}
              className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-lg border border-green-600/70 px-3 py-2 text-xs font-semibold text-green-100 hover:bg-white/10"
            >
              <Plus size={14} /> Importer un document
            </button>
          </div>
        </div>
      </ResizableSidebar>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="relative z-50 flex h-16 shrink-0 items-center gap-4 overflow-visible border-b border-slate-200 bg-white px-5 lg:px-7">
          <div
            ref={searchContainerRef}
            className="relative z-[100] w-full max-w-2xl"
          >
            <Search
              size={18}
              className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onFocus={() => {
                if (query.trim().length >= 2) setSearchOpen(true);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") setSearchOpen(false);
              }}
              autoComplete="off"
              placeholder="Rechercher une facture, un ICE, un tiers..."
              className="w-full rounded-xl border border-slate-300 bg-slate-50 py-2.5 pl-10 pr-10 text-sm outline-none transition focus:border-green-500 focus:bg-white focus:ring-4 focus:ring-green-500/10"
            />
            {query && (
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setSearchOpen(false);
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700"
                title="Effacer"
              >
                <X size={16} />
              </button>
            )}

            {searchOpen && query.trim().length >= 2 && (
              <div className="absolute left-0 right-0 top-full z-[9999] mt-2 max-h-[420px] overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-2xl">
                {searching && (
                  <p className="p-4 text-sm text-slate-500">Recherche en cours...</p>
                )}
                {!searching && searchError && (
                  <p className="border-l-4 border-red-500 bg-red-50 p-4 text-sm text-red-700">
                    {searchError}
                  </p>
                )}
                {!searching && !searchError && searchResults.length === 0 && (
                  <p className="p-4 text-sm text-slate-500">
                    Aucun résultat pour « {query} ».
                  </p>
                )}
                {!searching && !searchError && searchResults.length > 0 && (
                  <>
                    <div className="border-b border-slate-100 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                      {searchResults.length} résultat(s)
                    </div>
                    {searchResults.map((item) => (
                      <button
                        key={`${item.type}-${item.id}`}
                        type="button"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => selectSearchResult(item)}
                        className="flex w-full items-center gap-3 border-b border-slate-100 px-4 py-3 text-left last:border-0 hover:bg-green-50"
                      >
                        <span className={`shrink-0 rounded-md px-2 py-1 text-xs font-semibold ${
                          SEARCH_TYPE_CLASSES[item.type] ?? "bg-slate-100 text-slate-700"
                        }`}>
                          {SEARCH_TYPE_LABELS[item.type] ?? item.type}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-semibold text-slate-800">
                            {item.titre}
                          </span>
                          {item.sous_titre && (
                            <span className="mt-0.5 block truncate text-xs text-slate-500">
                              {item.sous_titre}
                            </span>
                          )}
                        </span>
                      </button>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>

          <div ref={notificationContainerRef} className="relative ml-auto shrink-0">
            <button
              type="button"
              onClick={() => setNotificationsOpen((open) => !open)}
              className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              title="Notifications"
            >
              <Bell size={20} />
              {notifications.length > 0 && (
                <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
                  {notifications.length > 99 ? "99+" : notifications.length}
                </span>
              )}
            </button>

            {notificationsOpen && (
              <div className="absolute right-0 top-full z-[9999] mt-2 max-h-[420px] w-80 overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-2xl">
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <p className="text-sm font-bold text-slate-800">Notifications</p>
                  <span className="text-xs text-slate-400">{notifications.length}</span>
                </div>
                {notifications.length === 0 && (
                  <p className="p-4 text-sm text-slate-500">Aucune notification.</p>
                )}
                {notifications.map((notification) => (
                  <button
                    key={notification.id}
                    type="button"
                    onClick={() => {
                      setNotificationsOpen(false);
                      navigate(notification.route);
                    }}
                    className="flex w-full items-start gap-3 border-b border-slate-100 px-4 py-3 text-left last:border-0 hover:bg-slate-50"
                  >
                    <span className={`mt-0.5 rounded-md px-2 py-1 text-[10px] font-bold ${
                      NOTIFICATION_CLASSES[notification.type] ?? "bg-slate-100 text-slate-700"
                    }`}>
                      !
                    </span>
                    <span className="text-sm text-slate-700">
                      {notification.message}
                      {notification.entreprise_nom && (
                        <span className="mt-1 block text-xs text-slate-400">
                          {notification.entreprise_nom}
                        </span>
                      )}
                    </span>
                  </button>
                ))}
                {notifications.length > 0 && (
                  <button
                    type="button"
                    onClick={() => navigate("/notifications")}
                    className="w-full border-t px-4 py-3 text-center text-xs font-semibold text-green-700 hover:bg-green-50"
                  >
                    Voir toutes les notifications
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="hidden min-w-0 text-right leading-tight sm:block">
            <p className="max-w-56 truncate text-sm font-semibold text-slate-800">
              {user?.email ?? "Cabinet"}
            </p>
            <p className="text-xs text-slate-400">{user?.role ?? ""}</p>
          </div>
          <button
            type="button"
            onClick={logout}
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-100 text-sm font-bold text-green-700 hover:bg-green-200"
            title="Déconnexion"
          >
            {(user?.nom?.[0] ?? user?.email?.[0] ?? "U").toUpperCase()}
          </button>
          <button
            type="button"
            onClick={logout}
            className="hidden rounded-lg p-2 text-slate-400 hover:bg-red-50 hover:text-red-600 lg:block"
            title="Se déconnecter"
          >
            <LogOut size={18} />
          </button>
        </header>

        <main className="min-w-0 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
}
