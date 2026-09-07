import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  AlertCircle,
  Download,
  Eye,
  FileSpreadsheet,
  FileText,
  RefreshCw,
} from "lucide-react";

import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import {
  getRegistre,
  getRegistreOptions,
} from "../api/accountingApi";
import { AnomalyBadge } from "../components/AnomalyBadge";
import { downloadApiBlob } from "../api/client";

import type { Entreprise } from "../types/entreprise";
import type {
  Registre,
  RegistreOption,
} from "../types/registre";

const ACTIVE_ENTREPRISE_KEY = "comptaflow_active_entreprise_id";

const MOIS = [
  "Janvier",
  "Février",
  "Mars",
  "Avril",
  "Mai",
  "Juin",
  "Juillet",
  "Août",
  "Septembre",
  "Octobre",
  "Novembre",
  "Décembre",
];

const CATEGORY_LABELS: Record<string, string> = {
  achats: "Achats",
  ventes: "Ventes",
  fournisseurs: "Fournisseurs",
  clients: "Clients",
  banque: "Banque",
  cnss: "CNSS",
  tva: "TVA",
  impots: "Impôts",
  divers: "Divers",
};

function uniqueValues<T>(values: T[]): T[] {
  return [...new Set(values)];
}

function formatMoney(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "0,00 MAD";
  }

  const numberValue =
    typeof value === "number"
      ? value
      : Number.parseFloat(value);

  if (Number.isNaN(numberValue)) {
    return "0,00 MAD";
  }

  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "MAD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numberValue);
}

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(`${value}T00:00:00`);

  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString("fr-FR");
}

function getErrorMessage(error: unknown): string {
  if (!axios.isAxiosError(error)) {
    return "Une erreur inattendue s’est produite.";
  }

  if (!error.response) {
    return "Le backend est inaccessible. Vérifiez que Uvicorn est démarré.";
  }

  const detail = error.response.data?.detail;

  if (typeof detail === "string") {
    return `Erreur API ${error.response.status} : ${detail}`;
  }

  return `Erreur API ${error.response.status} pendant le chargement du registre.`;
}

function latestOption(options: RegistreOption[]): RegistreOption | null {
  return options[0] ?? null;
}

export function RegistreComptablePage() {
  const navigate = useNavigate();

  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [options, setOptions] = useState<RegistreOption[]>([]);
  const [registre, setRegistre] = useState<Registre | null>(null);

  const [entrepriseId, setEntrepriseId] = useState("");
  const [categorie, setCategorie] = useState("");
  const [annee, setAnnee] = useState<number | null>(null);
  const [mois, setMois] = useState<number | null>(null);

  const [isInitializing, setIsInitializing] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const entrepriseIdRef = useRef(entrepriseId);
  entrepriseIdRef.current = entrepriseId;

  const applyOption = useCallback((option: RegistreOption) => {
    setEntrepriseId(option.entreprise_id);
    setCategorie(option.categorie);
    setAnnee(option.annee);
    setMois(option.mois);
  }, []);

  const loadOptions = useCallback(async () => {
    setIsInitializing(true);
    setError(null);

    try {
      const [entreprisesData, optionsData] = await Promise.all([
        listAvailableEntreprises("registres"),
        getRegistreOptions(),
      ]);

      setEntreprises(entreprisesData);
      setOptions(optionsData);

      const activeEntrepriseId = localStorage.getItem(ACTIVE_ENTREPRISE_KEY);
      const selectedEntrepriseId = chooseAvailableEntreprise(
        entreprisesData,
        entrepriseIdRef.current,
        activeEntrepriseId,
      );
      const selectedOption = latestOption(
        optionsData.filter((item) => item.entreprise_id === selectedEntrepriseId),
      );

      if (selectedOption) {
        applyOption(selectedOption);
      } else {
        setRegistre(null);
        setEntrepriseId(selectedEntrepriseId);
        setCategorie("");
        setAnnee(null);
        setMois(null);
      }
    } catch (loadError) {
      setError(getErrorMessage(loadError));
      setOptions([]);
      setRegistre(null);
    } finally {
      setIsInitializing(false);
    }
  }, [applyOption]);

  useEffect(() => {
    void loadOptions();
  }, [loadOptions]);

  const refresh = useCallback(async () => {
    if (!entrepriseId || !categorie || annee === null || mois === null) {
      setRegistre(null);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const data = await getRegistre({
        entreprise_id: entrepriseId,
        categorie,
        annee,
        mois,
      });

      setRegistre(data);
    } catch (refreshError) {
      setRegistre(null);
      setError(getErrorMessage(refreshError));
    } finally {
      setIsLoading(false);
    }
  }, [entrepriseId, categorie, annee, mois]);

  useEffect(() => {
    if (!isInitializing) {
      void refresh();
    }
  }, [isInitializing, refresh]);

  const entreprisesDisponibles = useMemo(() => {
    return entreprises;
  }, [entreprises]);

  const optionsEntreprise = useMemo(
    () => options.filter((item) => item.entreprise_id === entrepriseId),
    [options, entrepriseId],
  );

  const entrepriseSelectionnee = useMemo(
    () => entreprises.find((item) => item.id === entrepriseId) ?? null,
    [entreprises, entrepriseId],
  );

  const categoriesDisponibles = useMemo(
    () =>
      uniqueValues(
        options
          .filter((item) => item.entreprise_id === entrepriseId)
          .map((item) => item.categorie),
      ),
    [options, entrepriseId],
  );

  const anneesDisponibles = useMemo(
    () =>
      uniqueValues(
        options
          .filter(
            (item) =>
              item.entreprise_id === entrepriseId
              && item.categorie === categorie,
          )
          .map((item) => item.annee),
      ).sort((a, b) => b - a),
    [options, entrepriseId, categorie],
  );

  const moisDisponibles = useMemo(
    () =>
      uniqueValues(
        options
          .filter(
            (item) =>
              item.entreprise_id === entrepriseId
              && item.categorie === categorie
              && item.annee === annee,
          )
          .map((item) => item.mois),
      ).sort((a, b) => b - a),
    [options, entrepriseId, categorie, annee],
  );

  function handleEntrepriseChange(nextEntrepriseId: string) {
    const option = latestOption(
      options.filter((item) => item.entreprise_id === nextEntrepriseId),
    );

    if (option) {
      applyOption(option);
      localStorage.setItem(ACTIVE_ENTREPRISE_KEY, nextEntrepriseId);
      return;
    }

    setEntrepriseId(nextEntrepriseId);
    setCategorie("");
    setAnnee(null);
    setMois(null);
    setRegistre(null);
    localStorage.setItem(ACTIVE_ENTREPRISE_KEY, nextEntrepriseId);
  }

  function handleCategorieChange(nextCategorie: string) {
    const option = latestOption(
      options.filter(
        (item) =>
          item.entreprise_id === entrepriseId
          && item.categorie === nextCategorie,
      ),
    );

    if (option) {
      applyOption(option);
    }
  }

  function handleAnneeChange(nextAnnee: number) {
    const option = latestOption(
      options.filter(
        (item) =>
          item.entreprise_id === entrepriseId
          && item.categorie === categorie
          && item.annee === nextAnnee,
      ),
    );

    if (option) {
      applyOption(option);
    }
  }

  function handleExport(format: "xlsx" | "csv" | "pdf"): Promise<void> {
    const params = {
      entreprise_id: entrepriseId,
      categorie,
      annee: annee ?? undefined,
      mois: mois ?? undefined,
    };
    return downloadApiBlob(
      `/export/registers/${format}`,
      `registre_${categorie}_${annee}_${mois}.${format}`,
      params,
    );
  }

  const hasRows = Boolean(registre && registre.lignes.length > 0);

  return (
    <div className="min-h-screen bg-gray-50 p-5 lg:p-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-950">
              Registre comptable
            </h1>
            <p className="mt-1 text-sm text-gray-500">
              Les filtres affichés correspondent uniquement aux périodes qui
              contiennent au moins une écriture validée.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void loadOptions()}
            disabled={isInitializing || isLoading}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-semibold text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
          >
            <RefreshCw
              size={16}
              className={isInitializing || isLoading ? "animate-spin" : ""}
            />
            Actualiser
          </button>
        </div>

        {error && (
          <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!isInitializing && entreprises.length === 0 && !error && (
          <div className="rounded-xl border border-gray-200 bg-white p-5 text-sm text-gray-600">
            Aucune entreprise gérée et active n’est disponible dans ce cabinet.
          </div>
        )}

        {!isInitializing && options.length === 0 && entreprises.length > 0 && !error && (
          <section className="mb-5 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
            <label className="block max-w-md">
              <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                Entreprise
              </span>
              <select
                value={entrepriseId}
                onChange={(event) => handleEntrepriseChange(event.target.value)}
                className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100"
              >
                <option value="">Sélectionner</option>
                {entreprisesDisponibles.map((entreprise) => (
                  <option key={entreprise.id} value={entreprise.id}>
                    {entreprise.nom}
                  </option>
                ))}
              </select>
              {entrepriseSelectionnee && (
                <span className="mt-2 block text-xs text-gray-500">
                  {entrepriseSelectionnee.ecritures_brouillon ?? 0} brouillon(s) · {entrepriseSelectionnee.ecritures_a_verifier ?? 0} à vérifier · {entrepriseSelectionnee.ecritures_validees ?? 0} validée(s)
                </span>
              )}
            </label>
          </section>
        )}

        {!isInitializing && optionsEntreprise.length === 0 && entreprises.length > 0 && !error && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
            <div className="flex items-start gap-3">
              <AlertCircle size={20} className="mt-0.5 text-amber-700" />
              <div>
                <h2 className="font-bold text-amber-900">
                  Aucune écriture validée disponible
                </h2>
                <p className="mt-1 text-sm text-amber-800">
                  Les documents traités en statut « Brouillon » ou « À vérifier »
                  ne sont pas intégrés au registre comptable. Validez d’abord les
                  écritures concernées.
                </p>
                <button
                  type="button"
                  onClick={() => navigate("/registers")}
                  className="mt-4 rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-800"
                >
                  Ouvrir les écritures
                </button>
              </div>
            </div>
          </div>
        )}

        {options.length > 0 && (
          <>
            <section className="mb-6 rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Entreprise
                  </span>
                  <select
                    value={entrepriseId}
                    onChange={(event) => handleEntrepriseChange(event.target.value)}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100"
                  >
                    <option value="">Sélectionner</option>
                    {entreprisesDisponibles.map((entreprise) => (
                      <option key={entreprise.id} value={entreprise.id}>
                        {entreprise.nom}
                      </option>
                    ))}
                  </select>
                  {entrepriseSelectionnee && (
                    <span className="mt-2 block text-xs text-gray-500">
                      {entrepriseSelectionnee.ecritures_brouillon ?? 0} brouillon(s) · {entrepriseSelectionnee.ecritures_a_verifier ?? 0} à vérifier · {entrepriseSelectionnee.ecritures_validees ?? 0} validée(s)
                    </span>
                  )}
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Catégorie
                  </span>
                  <select
                    value={categorie}
                    onChange={(event) => handleCategorieChange(event.target.value)}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100"
                  >
                    {categoriesDisponibles.map((item) => (
                      <option key={item} value={item}>
                        {CATEGORY_LABELS[item] ?? item}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Année
                  </span>
                  <select
                    value={annee ?? ""}
                    onChange={(event) => handleAnneeChange(Number(event.target.value))}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100"
                  >
                    {anneesDisponibles.map((item) => (
                      <option key={item} value={item}>
                        {item}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-gray-500">
                    Mois
                  </span>
                  <select
                    value={mois ?? ""}
                    onChange={(event) => setMois(Number(event.target.value))}
                    className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100"
                  >
                    {moisDisponibles.map((item) => (
                      <option key={item} value={item}>
                        {MOIS[item - 1]}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </section>

            <section className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Écritures validées
                </p>
                <p className="mt-2 text-2xl font-bold text-gray-950">
                  {registre?.nombre ?? 0}
                </p>
              </div>

              <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Total HT
                </p>
                <p className="mt-2 text-2xl font-bold text-gray-950">
                  {formatMoney(registre?.total_ht)}
                </p>
              </div>

              <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Total TVA
                </p>
                <p className="mt-2 text-2xl font-bold text-gray-950">
                  {formatMoney(registre?.total_tva)}
                </p>
              </div>

              <div className="rounded-xl border border-gray-100 bg-white p-5 shadow-sm">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
                  Total TTC
                </p>
                <p className="mt-2 text-2xl font-bold text-gray-950">
                  {formatMoney(registre?.total_ttc)}
                </p>
              </div>
            </section>

            <section className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-100 px-5 py-4">
                <div>
                  <h2 className="font-bold text-gray-900">
                    Détail des écritures
                  </h2>
                  <p className="text-xs text-gray-500">
                    {categorie
                      ? CATEGORY_LABELS[categorie] ?? categorie
                      : "—"}
                    {mois ? ` • ${MOIS[mois - 1]}` : ""}
                    {annee ? ` ${annee}` : ""}
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  {hasRows ? (
                    <>
                      <button
                        type="button"
                        onClick={() => void handleExport("xlsx")}
                        className="inline-flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm font-semibold text-green-700 hover:bg-green-100"
                      >
                        <FileSpreadsheet size={16} />
                        Excel
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleExport("csv")}
                        className="inline-flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-semibold text-blue-700 hover:bg-blue-100"
                      >
                        <FileText size={16} />
                        CSV
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleExport("pdf")}
                        className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50"
                      >
                        <Download size={16} />
                        PDF
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-gray-400">
                      Export disponible dès qu’une écriture est affichée.
                    </span>
                  )}
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[980px] text-sm">
                  <thead>
                    <tr className="border-b bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                      <th className="px-4 py-3">Date</th>
                      <th className="px-4 py-3">Tiers</th>
                      <th className="px-4 py-3">N° pièce</th>
                      <th className="px-4 py-3 text-right">HT</th>
                      <th className="px-4 py-3 text-right">TVA</th>
                      <th className="px-4 py-3 text-right">TTC</th>
                      <th className="px-4 py-3 text-right">Document</th>
                    </tr>
                  </thead>

                  <tbody>
                    {isLoading && (
                      <tr>
                        <td colSpan={7} className="px-4 py-10 text-center text-gray-400">
                          <RefreshCw size={18} className="mr-2 inline animate-spin" />
                          Calcul du registre…
                        </td>
                      </tr>
                    )}

                    {!isLoading
                      && registre?.lignes.map((ligne) => (
                        <tr
                          key={ligne.id}
                          className="border-b border-gray-100 last:border-0 hover:bg-gray-50"
                        >
                          <td className="px-4 py-3">
                            {formatDate(ligne.date_piece)}
                          </td>
                          <td className="px-4 py-3">
                            <span className="font-medium text-gray-800">
                              {ligne.tiers ?? "—"}
                            </span>
                            <AnomalyBadge
                              detected={ligne.anomalie_detectee}
                              details={ligne.anomalie_details}
                            />
                          </td>
                          <td className="px-4 py-3 text-gray-600">
                            {ligne.numero_piece ?? "—"}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {formatMoney(ligne.montant_ht)}
                          </td>
                          <td className="px-4 py-3 text-right">
                            {formatMoney(ligne.montant_tva)}
                          </td>
                          <td className="px-4 py-3 text-right font-bold text-gray-900">
                            {formatMoney(ligne.montant_ttc)}
                          </td>
                          <td className="px-4 py-3 text-right">
                            <button
                              type="button"
                              onClick={() => navigate(`/documents/${ligne.document_id}`)}
                              className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold text-blue-700 hover:bg-blue-50"
                            >
                              <Eye size={14} />
                              Vérifier
                            </button>
                          </td>
                        </tr>
                      ))}

                    {!isLoading && registre?.lignes.length === 0 && (
                      <tr>
                        <td colSpan={7} className="px-4 py-10 text-center text-gray-400">
                          Aucune écriture validée pour cette combinaison de filtres.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
