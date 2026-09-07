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
  Bot,
  Building2,
  BookOpen,
  BookOpenText,
  CalendarClock,
  CalendarCheck,
  ChevronDown,
  ClipboardCheck,
  Clock,
  FileStack,
  FileSearch,
  FileText,
  Home,
  History,
  Landmark,
  LogOut,
  Menu,
  MessageCircle,
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
import { getUnreadMessageCount } from "../api/messagesApi";
import { useAuth } from "../context/AuthContext";
import { AssistantWidget } from "./assistant/AssistantWidget";
import { BrandMark } from "./BrandMark";
import { ACTIVE_ENTREPRISE_EVENT, ACTIVE_ENTREPRISE_KEY, setActiveEntrepriseId } from "../utils/activeEntreprise";

import type { Entreprise } from "../types/entreprise";
import type { Notification } from "../types/notification";
import type { SearchResultItem } from "../types/search";

export { ACTIVE_ENTREPRISE_KEY } from "../utils/activeEntreprise";

const SEARCH_DELAY_MS = 300;
const NOTIFICATIONS_REFRESH_MS = 15_000;
const TASKS_REFRESH_MS = 30_000;

interface NavigationItem {
  label: string;
  route: string;
  icon: LucideIcon;
  roles?: string[];
  requiresCompany?: boolean;
}

interface NavigationGroup {
  title: string;
  items: NavigationItem[];
}

const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    title: "Vue d'ensemble",
    items: [
      { label: "Accueil", route: "/accueil", icon: Home },
      { label: "Tableau de bord", route: "/dashboard", icon: BarChart3, requiresCompany: true },
      { label: "Documents", route: "/upload", icon: FileText },
      { label: "Documents à identifier", route: "/chronos?non_identifies=1", icon: FileSearch },
      { label: "Chronos", route: "/chronos", icon: Clock },
      { label: "Assistant", route: "/assistant", icon: Bot },
    ],
  },
  {
    title: "Gestion comptable",
    items: [
      { label: "Achats", route: "/achats", icon: ShoppingCart },
      { label: "Ventes", route: "/ventes", icon: TrendingUp },
      { label: "Banque", route: "/banque", icon: Landmark },
      { label: "Comptes bancaires", route: "/comptes-bancaires", icon: Landmark },
      { label: "Plan comptable", route: "/plan-comptable", icon: BookOpen },
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
      { label: "Messagerie", route: "/messagerie", icon: MessageCircle },
      { label: "Notifications", route: "/notifications", icon: Bell },
      { label: "Rapports", route: "/rapports", icon: BarChart3 },
      { label: "Utilisateurs", route: "/admin/utilisateurs", icon: UserCog, roles: ["admin_cabinet", "super_admin"] },
      { label: "Historique", route: "/admin/historique", icon: History, roles: ["admin_cabinet", "super_admin"] },
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
  const routePath = route.split("?")[0];
  if (routePath === "/upload") {
    return pathname === "/upload" || pathname === "/documents";
  }
  return pathname === routePath || pathname.startsWith(`${routePath}/`);
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
  const [messagesCount, setMessagesCount] = useState(0);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  const searchContainerRef = useRef<HTMLDivElement>(null);
  const notificationContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listEntreprises()
      .then(setCompanies)
      .catch(() => setCompanies([]));
  }, []);

  useEffect(() => {
    const synchronize = (event: Event) => setActiveCompanyId((event as CustomEvent<string | null>).detail ?? null);
    window.addEventListener(ACTIVE_ENTREPRISE_EVENT, synchronize);
    return () => window.removeEventListener(ACTIVE_ENTREPRISE_EVENT, synchronize);
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
    const refreshMessages = async () => {
      try {
        setMessagesCount(await getUnreadMessageCount());
      } catch {
        // Le polling réessaiera automatiquement.
      }
    };
    void refreshMessages();
    const timer = window.setInterval(refreshMessages, 10_000);
    return () => window.clearInterval(timer);
  }, []);

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
    setMobileNavOpen(false);
  }, [location.pathname]);

  function selectCompany(id: string | null) {
    setActiveCompanyId(id);
    setActiveEntrepriseId(id);
  }

  function selectSearchResult(item: SearchResultItem) {
    setSearchOpen(false);
    setQuery("");
    navigate(item.route);
  }

  if (location.pathname === "/accueil" || location.pathname === "/entreprises/selection") {
    return <div className="min-h-screen">{children}</div>;
  }

  const visibleGroups = NAVIGATION_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) =>
      (!item.requiresCompany || activeCompanyId) &&
      (!item.roles || (user && item.roles.includes(user.role))),
    ),
  })).filter((group) => group.items.length > 0);

  function navItem(item: NavigationItem, compact = false) {
    const Icon = item.icon;
    const active = isRouteActive(location.pathname, item.route);
    const badge = item.route === "/notifications"
      ? notifications.length
      : item.route === "/rappels"
        ? tasksCount
        : item.route === "/messagerie"
          ? messagesCount
          : 0;
    return (
      <button
        key={item.route}
        type="button"
        onClick={() => navigate(item.route)}
        className={`flex items-center gap-2 rounded-lg text-sm font-semibold transition ${compact ? "w-full px-3 py-2 text-left" : "px-3 py-2"} ${
          active ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"
        }`}
      >
        <Icon size={16} className="shrink-0" />
        <span className="truncate">{item.label}</span>
        {badge > 0 && <span className="ml-auto rounded-full bg-red-100 px-1.5 py-0.5 text-[10px] font-bold text-red-700">{badge > 99 ? "99+" : badge}</span>}
      </button>
    );
  }

  const accountingItems = visibleGroups.find((group) => group.title === "Gestion comptable")?.items ?? [];
  const overviewItems = visibleGroups.find((group) => group.title === "Vue d'ensemble")?.items ?? [];
  const organizationItems = visibleGroups.find((group) => group.title === "Organisation")?.items ?? [];
  const directRoutes = new Set(["/accueil", "/dashboard", "/upload", "/tva-mensuelle", "/banque", "/rapports"]);

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900">
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-[1800px] items-center gap-3 px-4 lg:px-6">
          <button type="button" onClick={() => navigate("/accueil")} className="mr-1 flex shrink-0 items-center gap-2.5" aria-label="Accueil ComptaFlow">
            <BrandMark className="h-10 w-11 shrink-0 drop-shadow-sm" />
            <span className="text-base font-bold tracking-tight text-slate-950 sm:text-lg">ComptaFlow</span>
          </button>

          <nav className="hidden items-center gap-0.5 xl:flex" aria-label="Navigation principale">
            {overviewItems.filter((item) => directRoutes.has(item.route)).map((item) => navItem(item))}
            {accountingItems.length > 0 && <div className="group relative">
              <button type="button" className={`flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold ${accountingItems.some((item) => isRouteActive(location.pathname, item.route)) ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"}`}>Comptabilité <ChevronDown size={14} /></button>
              <div className="invisible absolute left-0 top-full z-[100] mt-1 grid w-[430px] grid-cols-2 gap-1 rounded-xl border border-slate-200 bg-white p-2 opacity-0 shadow-xl transition group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
                {accountingItems.filter((item) => !directRoutes.has(item.route)).map((item) => navItem(item, true))}
              </div>
            </div>}
            {accountingItems.filter((item) => directRoutes.has(item.route)).map((item) => navItem(item))}
            <div className="group relative">
              <button type="button" className={`flex items-center gap-1 rounded-lg px-3 py-2 text-sm font-semibold ${[...overviewItems, ...organizationItems].filter((item) => !directRoutes.has(item.route)).some((item) => isRouteActive(location.pathname, item.route)) ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-950"}`}>Suivi <ChevronDown size={14} /></button>
              <div className="invisible absolute left-0 top-full z-[100] mt-1 grid w-[430px] grid-cols-2 gap-1 rounded-xl border border-slate-200 bg-white p-2 opacity-0 shadow-xl transition group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100">
                {[...overviewItems, ...organizationItems].filter((item) => !directRoutes.has(item.route)).map((item) => navItem(item, true))}
              </div>
            </div>
            {organizationItems.filter((item) => directRoutes.has(item.route)).map((item) => navItem(item))}
          </nav>

          <button type="button" onClick={() => setMobileNavOpen((open) => !open)} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 xl:hidden" aria-label="Afficher la navigation"><Menu size={21} /></button>

          <div className="ml-auto hidden min-w-0 max-w-[180px] items-center gap-2 lg:flex">
            <Building2 size={16} className="shrink-0 text-blue-600" />
            <select value={activeCompanyId ?? ""} onChange={(event) => selectCompany(event.target.value || null)} className="min-w-0 max-w-[155px] rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-2 text-xs font-semibold text-slate-700 outline-none focus:border-blue-500">
              <option value="">Toutes les entreprises</option>
              {companies.map((company) => <option key={company.id} value={company.id}>{company.nom}</option>)}
            </select>
          </div>

          <div
            ref={searchContainerRef}
            className="relative z-[100] hidden w-36 xl:block 2xl:w-full 2xl:max-w-xs"
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
              className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 pl-9 pr-9 text-sm outline-none transition focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-100"
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
                        className="flex w-full items-center gap-3 border-b border-slate-100 px-4 py-3 text-left last:border-0 hover:bg-blue-50"
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

          <div ref={notificationContainerRef} className="relative shrink-0">
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
                    className="w-full border-t px-4 py-3 text-center text-xs font-semibold text-blue-700 hover:bg-blue-50"
                  >
                    Voir toutes les notifications
                  </button>
                )}
              </div>
            )}
          </div>

          <div className="hidden min-w-0 text-right leading-tight 2xl:block">
            <p className="max-w-56 truncate text-sm font-semibold text-slate-800">
              {user?.email ?? "Cabinet"}
            </p>
            <p className="text-xs text-slate-400">{user?.role ?? ""}</p>
          </div>
          <button
            type="button"
            onClick={logout}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700 hover:bg-blue-200"
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
        </div>

        {mobileNavOpen && <nav className="max-h-[calc(100vh-64px)] overflow-y-auto border-t border-slate-200 bg-white p-3 xl:hidden" aria-label="Navigation mobile">
          <div className="mb-3 grid gap-2 sm:grid-cols-2 lg:hidden">
            <label className="text-xs font-semibold text-slate-500">Entreprise
              <select value={activeCompanyId ?? ""} onChange={(event) => selectCompany(event.target.value || null)} className="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700"><option value="">Toutes les entreprises</option>{companies.map((company) => <option key={company.id} value={company.id}>{company.nom}</option>)}</select>
            </label>
          </div>
          {visibleGroups.map((group) => <section key={group.title} className="mb-3"><p className="mb-1 px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400">{group.title}</p><div className="grid gap-1 sm:grid-cols-2 md:grid-cols-3">{group.items.map((item) => navItem(item, true))}</div></section>)}
          <button type="button" onClick={() => navigate("/upload")} className="mt-1 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white"><Plus size={15} />Importer un document</button>
        </nav>}
      </header>

      <main className="min-w-0">{children}</main>
      <AssistantWidget />
    </div>
  );
}
