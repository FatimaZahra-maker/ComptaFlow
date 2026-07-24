import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getNotifications, getNotificationsStats } from "../api/notificationsApi";
import type { Notification, NotificationsStats } from "../types/notification";

const TYPE_LABELS: Record<string, string> = {
  document_erreur: "Documents en erreur",
  ecriture_anomalie: "Anomalies détectées",
  ecriture_a_verifier: "Écritures à vérifier",
  document_nouveau: "Nouveaux documents",
};

const TYPE_COLORS: Record<string, string> = {
  document_erreur: "#dc2626",
  ecriture_anomalie: "#ea580c",
  ecriture_a_verifier: "#f59e0b",
  document_nouveau: "#2563eb",
};

const TYPE_ICONS: Record<string, string> = {
  document_erreur: "✕",
  ecriture_anomalie: "⚠",
  ecriture_a_verifier: "⚠",
  document_nouveau: "●",
};

function BarChart({ data }: { data: { label: string; value: number; color: string }[] }) {
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="space-y-3">
      {data.map((d) => (
        <div key={d.label}>
          <div className="flex justify-between text-xs text-gray-500 mb-1">
            <span>{d.label}</span>
            <span className="font-medium">{d.value}</span>
          </div>
          <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{ width: `${(d.value / max) * 100}%`, backgroundColor: d.color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

export function NotificationsPage() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [stats, setStats] = useState<NotificationsStats | null>(null);
  const [filtreType, setFiltreType] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    Promise.all([getNotifications(), getNotificationsStats()])
      .then(([notifs, s]) => {
        setNotifications(notifs.notifications);
        setStats(s);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const notificationsFiltrees = filtreType
    ? notifications.filter((n) => n.type === filtreType)
    : notifications;

  if (isLoading) {
    return <div className="p-8 text-gray-500">Chargement...</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-xl font-semibold mb-1">Centre de notifications</h1>
        <p className="text-sm text-gray-500 mb-6">
          {notifications.length} alerte(s) active(s) sur l'ensemble du cabinet.
        </p>

        <div className="grid grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-lg shadow-sm p-5">
            <h2 className="font-medium text-sm mb-4">Répartition par type d'alerte</h2>
            {stats && stats.par_type.length > 0 ? (
              <BarChart
                data={stats.par_type.map((t) => ({
                  label: TYPE_LABELS[t.type] ?? t.type,
                  value: t.total,
                  color: TYPE_COLORS[t.type] ?? "#6b7280",
                }))}
              />
            ) : (
              <p className="text-sm text-gray-400">Aucune alerte à afficher.</p>
            )}
          </div>

          <div className="bg-white rounded-lg shadow-sm p-5">
            <h2 className="font-medium text-sm mb-4">Entreprises les plus concernées</h2>
            {stats && stats.par_entreprise.length > 0 ? (
              <div className="space-y-2">
                {stats.par_entreprise.slice(0, 8).map((e) => (
                  <div key={e.entreprise_id ?? "inconnue"} className="flex items-center justify-between text-sm py-1.5 border-b last:border-0">
                    <span className="text-gray-700">{e.entreprise_nom}</span>
                    <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full text-xs font-medium">
                      {e.total}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">Aucune donnée.</p>
            )}
          </div>
        </div>

        <div className="flex gap-2 mb-4 flex-wrap">
          <button
            onClick={() => setFiltreType(null)}
            className={`text-xs px-3 py-1.5 rounded-full border ${
              filtreType === null ? "bg-gray-800 text-white border-gray-800" : "bg-white hover:bg-gray-50"
            }`}
          >
            Toutes ({notifications.length})
          </button>
          {stats?.par_type.map((t) => (
            <button
              key={t.type}
              onClick={() => setFiltreType(t.type)}
              className={`text-xs px-3 py-1.5 rounded-full border ${
                filtreType === t.type ? "text-white border-transparent" : "bg-white hover:bg-gray-50"
              }`}
              style={filtreType === t.type ? { backgroundColor: TYPE_COLORS[t.type] } : {}}
            >
              {TYPE_LABELS[t.type] ?? t.type} ({t.total})
            </button>
          ))}
        </div>

        <div className="bg-white rounded-lg shadow-sm divide-y">
          {notificationsFiltrees.length === 0 && (
            <p className="p-6 text-center text-gray-400 text-sm">Aucune notification pour ce filtre.</p>
          )}
          {notificationsFiltrees.map((n) => (
            <button
              key={n.id}
              onClick={() => navigate(n.route)}
              className="w-full text-left px-5 py-3 hover:bg-gray-50 flex items-start gap-3"
            >
              <span
                className="text-sm shrink-0 mt-0.5 w-6 h-6 rounded-full flex items-center justify-center text-white text-xs"
                style={{ backgroundColor: TYPE_COLORS[n.type] ?? "#6b7280" }}
              >
                {TYPE_ICONS[n.type] ?? "•"}
              </span>
              <span className="flex-1">
                <span className="text-sm text-gray-800 block">{n.message}</span>
                <span className="text-xs text-gray-400">
                  {n.entreprise_nom ? `${n.entreprise_nom} · ` : ""}
                  {new Date(n.created_at).toLocaleString("fr-FR")}
                </span>
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}