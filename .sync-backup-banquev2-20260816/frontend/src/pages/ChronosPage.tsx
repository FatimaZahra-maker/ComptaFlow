import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ChangeEvent,
  type MouseEvent,
  type ReactNode,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import axios from "axios";

import {
  Building2,
  ExternalLink,
  FileSearch,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  X,
} from "lucide-react";


import {
  listAnneesDisponibles,
  listChronoDocuments,
} from "../api/chronosApi";


import {
  deleteDocument,
  getDocumentFileUrl,
  retraiterDocument,
  toggleDocumentSaisie,
} from "../api/documentsApi";


import {
  createEntreprise,
  listEntreprises,
} from "../api/entreprisesApi";


import {
  AnomalyBadge,
} from "../components/AnomalyBadge";


import {
  ResizableSidebar,
} from "../components/ResizableSidebar";


import type {
  DocumentChrono,
} from "../types/chrono";


import type {
  Entreprise,
} from "../types/entreprise";


// ============================================================
// CATÉGORIES
// ============================================================

const CATEGORIES = [
  "achats",
  "ventes",
  "banque",
  "cnss",
  "tva",
  "impots",
  "clients",
  "fournisseurs",
  "divers",
];


// ============================================================
// MOIS
// ============================================================

const MONTHS = [
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


// ============================================================
// STATUT DOCUMENT
// ============================================================

const DOCUMENT_STATUS_LABELS: Record<
  string,
  string
> = {
  en_attente: "En attente",
  en_traitement: "En traitement",
  traite: "Traité",
  valide: "Validé",
  erreur: "Erreur",
};


const DOCUMENT_STATUS_CLASSES: Record<
  string,
  string
> = {
  en_attente: "text-slate-500",
  en_traitement: "text-amber-600",
  traite: "text-green-600",
  valide: "text-emerald-700",
  erreur: "text-red-600",
};


// ============================================================
// VALIDATION
// ============================================================

const VALIDATION_LABELS: Record<
  string,
  string
> = {
  brouillon: "Brouillon",
  a_verifier: "À vérifier",
  valide: "Validé",
  rejete: "Rejeté",
};


const VALIDATION_CLASSES: Record<
  string,
  string
> = {
  brouillon: "bg-slate-100 text-slate-700",
  a_verifier: "bg-orange-100 text-orange-700",
  valide: "bg-green-100 text-green-700",
  rejete: "bg-red-100 text-red-700",
};


// ============================================================
// FORMAT MONTANT
// ============================================================

function formatMoney(
  value: string | number | null,
): string {

  if (
    value === null
    || value === ""
  ) {
    return "—";
  }


  const amount = Number(
    value
  );


  if (
    !Number.isFinite(
      amount
    )
  ) {
    return "—";
  }


  return (
    new Intl.NumberFormat(
      "fr-FR",
      {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      },
    ).format(
      amount
    )
    + " MAD"
  );
}


// ============================================================
// FORMAT DATE
// ============================================================

function formatDate(
  value: string | null,
): string {

  if (!value) {
    return "—";
  }


  const date = new Date(
    `${value}T00:00:00`
  );


  return Number.isNaN(
    date.getTime()
  )
    ? value
    : date.toLocaleDateString(
        "fr-FR"
      );
}


// ============================================================
// ERREURS API
// ============================================================

function getErrorMessage(
  error: unknown,
  fallback: string,
): string {

  if (
    axios.isAxiosError(
      error
    )
  ) {

    const detail = (
      error.response?.data?.detail
    );


    if (
      typeof detail === "string"
    ) {
      return detail;
    }


    if (
      !error.response
    ) {
      return (
        "Backend inaccessible. "
        + "Vérifiez Uvicorn."
      );
    }


    return (
      `${fallback} `
      + `(API ${error.response.status}).`
    );
  }


  return fallback;
}


// ============================================================
// PAGE CHRONOS
// ============================================================

export function ChronosPage() {

  const navigate = useNavigate();


  // ----------------------------------------------------------
  // DONNÉES
  // ----------------------------------------------------------

  const [
    companies,
    setCompanies,
  ] = useState<Entreprise[]>(
    []
  );


  const [
    documents,
    setDocuments,
  ] = useState<DocumentChrono[]>(
    []
  );


  const [
    availableYears,
    setAvailableYears,
  ] = useState<number[]>(
    []
  );


  // ----------------------------------------------------------
  // FILTRES
  // ----------------------------------------------------------

  const [
    companyId,
    setCompanyId,
  ] = useState<string | null>(
    null
  );


  const [
    category,
    setCategory,
  ] = useState<string | null>(
    null
  );


  const [
    year,
    setYear,
  ] = useState<number | null>(
    null
  );


  const [
    month,
    setMonth,
  ] = useState<number | null>(
    null
  );


  const [
    searchTerm,
    setSearchTerm,
  ] = useState(
    ""
  );


  // ----------------------------------------------------------
  // ÉTAT PAGE
  // ----------------------------------------------------------

  const [
    loading,
    setLoading,
  ] = useState(
    true
  );


  const [
    currentAction,
    setCurrentAction,
  ] = useState<string | null>(
    null
  );


  const [
    error,
    setError,
  ] = useState<string | null>(
    null
  );


  const [
    success,
    setSuccess,
  ] = useState<string | null>(
    null
  );


  // ----------------------------------------------------------
  // MODALE AJOUT ENTREPRISE
  // ----------------------------------------------------------

  const [
    addCompanyOpen,
    setAddCompanyOpen,
  ] = useState(
    false
  );


  const [
    newCompanyName,
    setNewCompanyName,
  ] = useState(
    ""
  );


  const [
    creatingCompany,
    setCreatingCompany,
  ] = useState(
    false
  );


  // ==========================================================
  // CHARGER ENTREPRISES
  // ==========================================================

  const loadCompanies = useCallback(
    async () => {

      try {

        const data = (
          await listEntreprises()
        );


        setCompanies(
          data
        );

      } catch {

        setCompanies(
          []
        );


        setError(
          "Impossible de charger les entreprises."
        );
      }
    },
    [],
  );


  useEffect(
    () => {

      void loadCompanies();

    },
    [
      loadCompanies,
    ],
  );


  // ==========================================================
  // ANNÉES DISPONIBLES
  // ==========================================================

  useEffect(
    () => {

      let active = true;


      listAnneesDisponibles(
        {
          entreprise_id:
            companyId
            ?? undefined,

          categorie:
            category
            ?? undefined,
        }
      )
        .then(
          (
            years
          ) => {

            if (!active) {
              return;
            }


            setAvailableYears(
              years
            );


            if (
              year !== null
              && !years.includes(
                year
              )
            ) {
              setYear(
                null
              );
            }
          }
        )
        .catch(
          () => {

            if (
              active
            ) {
              setAvailableYears(
                []
              );
            }
          }
        );


      return () => {
        active = false;
      };

    },
    [
      category,
      companyId,
      year,
    ],
  );


  // ==========================================================
  // CHARGER DOCUMENTS
  // ==========================================================

  const refresh = useCallback(
    async () => {

      setLoading(
        true
      );


      setError(
        null
      );


      try {

        const data = (
          await listChronoDocuments(
            {
              entreprise_id:
                companyId
                ?? undefined,

              categorie:
                category
                ?? undefined,

              annee:
                year
                ?? undefined,

              mois:
                month
                ?? undefined,
            }
          )
        );


        setDocuments(
          data
        );

      } catch (
        requestError
      ) {

        setDocuments(
          []
        );


        setError(
          getErrorMessage(
            requestError,
            "Impossible de charger le Chronos",
          )
        );

      } finally {

        setLoading(
          false
        );
      }
    },
    [
      category,
      companyId,
      month,
      year,
    ],
  );


  useEffect(
    () => {

      void refresh();

    },
    [
      refresh,
    ],
  );


  // ==========================================================
  // RECHERCHE LOCALE
  // ==========================================================

  const visibleDocuments = useMemo(
    () => {

      const term = (
        searchTerm
          .trim()
          .toLocaleLowerCase(
            "fr"
          )
      );


      if (
        !term
      ) {
        return documents;
      }


      return documents.filter(
        (
          document
        ) => {

          const values = [
            document.nom_fichier_original,
            document.entreprise_nom,
            document.numero_piece,
            document.tiers,
            document.categorie,
          ];


          return values.some(
            (
              value
            ) => (
              value
                ?.toLocaleLowerCase(
                  "fr"
                )
                .includes(
                  term
                )
            )
          );
        }
      );
    },
    [
      documents,
      searchTerm,
    ],
  );


  // ==========================================================
  // AJOUT ENTREPRISE
  // ==========================================================

  async function handleCreateCompany() {

    const nom = (
      newCompanyName.trim()
    );


    if (
      nom.length < 2
    ) {

      setError(
        "Saisissez le nom de l'entreprise."
      );

      return;
    }


    setCreatingCompany(
      true
    );


    setError(
      null
    );


    setSuccess(
      null
    );


    try {

      const entreprise = (
        await createEntreprise(
          nom
        )
      );


      await loadCompanies();


      // On sélectionne directement la nouvelle entreprise
      // dans le filtre Chronos.
      setCompanyId(
        entreprise.id
      );


      setNewCompanyName(
        ""
      );


      setAddCompanyOpen(
        false
      );


      setSuccess(
        `Entreprise « ${entreprise.nom} » ajoutée. `
        + "Vous pouvez maintenant retraiter ses documents."
      );


      // Événement disponible pour les autres composants
      // qui voudront se rafraîchir plus tard.
      window.dispatchEvent(
        new CustomEvent(
          "entreprises-changed"
        )
      );

    } catch (
      requestError
    ) {

      setError(
        getErrorMessage(
          requestError,
          "Impossible d'ajouter l'entreprise",
        )
      );

    } finally {

      setCreatingCompany(
        false
      );
    }
  }


  // ==========================================================
  // SAISIE TOPAZE
  // ==========================================================

  async function handleToggleSaisie(
    event: ChangeEvent<HTMLInputElement>,
    documentId: string,
  ) {

    event.stopPropagation();


    setCurrentAction(
      `saisie-${documentId}`
    );


    setError(
      null
    );


    setSuccess(
      null
    );


    try {

      const result = (
        await toggleDocumentSaisie(
          documentId
        )
      );


      setDocuments(
        (
          current
        ) => (
          current.map(
            (
              document
            ) => (

              document.id
              === documentId

                ? {
                    ...document,

                    saisie_topaze:
                      result.saisie_topaze,
                  }

                : document
            )
          )
        )
      );


      setSuccess(
        "Statut de saisie mis à jour."
      );

    } catch (
      requestError
    ) {

      setError(
        getErrorMessage(
          requestError,
          "La mise à jour de la saisie a échoué",
        )
      );

    } finally {

      setCurrentAction(
        null
      );
    }
  }


  // ==========================================================
  // RETRAITEMENT
  // ==========================================================

  async function handleRetraiter(
    event: MouseEvent<HTMLButtonElement>,
    documentId: string,
  ) {

    event.stopPropagation();


    const confirmed = window.confirm(
      "Relancer le traitement du document ? "
      + "Les anciennes données extraites seront remplacées."
    );


    if (
      !confirmed
    ) {
      return;
    }


    setCurrentAction(
      `retraiter-${documentId}`
    );


    setError(
      null
    );


    setSuccess(
      null
    );


    try {

      await retraiterDocument(
        documentId
      );


      await refresh();


      setSuccess(
        "Le retraitement a été lancé."
      );

    } catch (
      requestError
    ) {

      setError(
        getErrorMessage(
          requestError,
          "Le retraitement a échoué",
        )
      );

    } finally {

      setCurrentAction(
        null
      );
    }
  }


  // ==========================================================
  // SUPPRESSION
  // ==========================================================

  async function handleDelete(
    event: MouseEvent<HTMLButtonElement>,
    document: DocumentChrono,
  ) {

    event.stopPropagation();


    const confirmed = window.confirm(
      `Supprimer définitivement « `
      + `${document.nom_fichier_original} » ?\n\n`
      + "Le document, son fichier, ses écritures "
      + "et ses mouvements bancaires seront supprimés."
    );


    if (
      !confirmed
    ) {
      return;
    }


    setCurrentAction(
      `delete-${document.id}`
    );


    setError(
      null
    );


    setSuccess(
      null
    );


    try {

      await deleteDocument(
        document.id
      );


      setDocuments(
        (
          current
        ) => (
          current.filter(
            (
              item
            ) => (
              item.id
              !== document.id
            )
          )
        )
      );


      setSuccess(
        "Document supprimé. "
        + "Le même fichier peut maintenant être réimporté."
      );

    } catch (
      requestError
    ) {

      setError(
        getErrorMessage(
          requestError,
          "La suppression définitive a échoué",
        )
      );

    } finally {

      setCurrentAction(
        null
      );
    }
  }


  // ==========================================================
  // AFFICHAGE
  // ==========================================================

  return (

    <div
      className="flex min-h-full bg-slate-50"
    >

      {/* =====================================================
          BARRE DE FILTRES GAUCHE
      ===================================================== */}

      <ResizableSidebar
        storageKey="chronos-filters"
        defaultWidth={230}
        minWidth={190}
        maxWidth={380}
        className="border-r border-slate-200 bg-white"
      >

        <div
          className="space-y-6 p-4"
        >

          {/* =================================================
              ENTREPRISES
          ================================================= */}

          <FilterSection
            title="Entreprises"

            action={

              <button
                type="button"

                onClick={
                  () => {

                    setError(
                      null
                    );

                    setSuccess(
                      null
                    );

                    setAddCompanyOpen(
                      true
                    );
                  }
                }

                className="
                  inline-flex
                  items-center
                  gap-1
                  rounded-md
                  px-2
                  py-1
                  text-[11px]
                  font-semibold
                  text-green-700
                  hover:bg-green-50
                "

                title="Ajouter une entreprise suivie"
              >

                <Plus
                  size={13}
                />

                Ajouter

              </button>
            }
          >

            <FilterButton
              active={
                companyId === null
              }

              onClick={
                () => (
                  setCompanyId(
                    null
                  )
                )
              }
            >

              Toutes

            </FilterButton>


            {companies.map(
              (
                company
              ) => (

                <FilterButton
                  key={
                    company.id
                  }

                  active={
                    companyId
                    === company.id
                  }

                  onClick={
                    () => (
                      setCompanyId(
                        company.id
                      )
                    )
                  }
                >

                  {company.nom}

                </FilterButton>
              )
            )}

          </FilterSection>


          {/* =================================================
              CATÉGORIES
          ================================================= */}

          <FilterSection
            title="Catégories"
          >

            <FilterButton
              active={
                category === null
              }

              onClick={
                () => (
                  setCategory(
                    null
                  )
                )
              }
            >
              Toutes
            </FilterButton>


            {CATEGORIES.map(
              (
                item
              ) => (

                <FilterButton
                  key={
                    item
                  }

                  active={
                    category
                    === item
                  }

                  onClick={
                    () => (
                      setCategory(
                        item
                      )
                    )
                  }
                >

                  <span
                    className="capitalize"
                  >
                    {item}
                  </span>

                </FilterButton>
              )
            )}

          </FilterSection>


          {/* =================================================
              ANNÉE
          ================================================= */}

          <FilterSection
            title="Année"
          >

            <FilterButton
              active={
                year === null
              }

              onClick={
                () => (
                  setYear(
                    null
                  )
                )
              }
            >
              Toutes
            </FilterButton>


            {availableYears.map(
              (
                item
              ) => (

                <FilterButton
                  key={
                    item
                  }

                  active={
                    year === item
                  }

                  onClick={
                    () => (
                      setYear(
                        item
                      )
                    )
                  }
                >
                  {item}
                </FilterButton>
              )
            )}


            {availableYears.length === 0 && (

              <p
                className="px-2 text-xs text-slate-400"
              >
                Aucune année disponible
              </p>

            )}

          </FilterSection>


          {/* =================================================
              MOIS
          ================================================= */}

          <FilterSection
            title="Mois"
          >

            <FilterButton
              active={
                month === null
              }

              onClick={
                () => (
                  setMonth(
                    null
                  )
                )
              }
            >
              Tous
            </FilterButton>


            {MONTHS.map(
              (
                label,
                index,
              ) => (

                <FilterButton
                  key={
                    label
                  }

                  active={
                    month
                    === index + 1
                  }

                  onClick={
                    () => (
                      setMonth(
                        index + 1
                      )
                    )
                  }
                >
                  {label}
                </FilterButton>
              )
            )}

          </FilterSection>

        </div>

      </ResizableSidebar>


      {/* =====================================================
          CONTENU
      ===================================================== */}

      <main
        className="min-w-0 flex-1 p-5 lg:p-7"
      >

        {/* TITRE */}

        <div
          className="
            mb-5
            flex
            flex-wrap
            items-start
            justify-between
            gap-3
          "
        >

          <div>

            <h1
              className="text-2xl font-bold text-slate-900"
            >
              Chronos — Tableau comptable
            </h1>


            <p
              className="mt-1 text-sm text-slate-500"
            >
              Cliquez sur une ligne pour vérifier le document
              et ses données extraites.
            </p>

          </div>


          <button
            type="button"

            onClick={
              () => (
                void refresh()
              )
            }

            disabled={
              loading
            }

            className="
              inline-flex
              items-center
              gap-2
              rounded-lg
              border
              border-slate-200
              bg-white
              px-4
              py-2
              text-sm
              font-semibold
              text-slate-700
              hover:bg-slate-50
              disabled:opacity-50
            "
          >

            <RefreshCw
              size={16}

              className={
                loading
                  ? "animate-spin"
                  : ""
              }
            />

            Actualiser

          </button>

        </div>


        {/* ERREUR */}

        {error && (

          <div
            className="
              mb-4
              rounded-lg
              border
              border-red-200
              bg-red-50
              px-4
              py-3
              text-sm
              text-red-700
            "
          >
            {error}
          </div>

        )}


        {/* SUCCÈS */}

        {success && (

          <div
            className="
              mb-4
              rounded-lg
              border
              border-green-200
              bg-green-50
              px-4
              py-3
              text-sm
              text-green-700
            "
          >
            {success}
          </div>

        )}


        {/* RECHERCHE */}

        <div
          className="
            mb-4
            flex
            flex-wrap
            items-center
            justify-between
            gap-3
            rounded-xl
            border
            border-slate-200
            bg-white
            p-4
            shadow-sm
          "
        >

          <div
            className="relative w-full max-w-lg"
          >

            <Search
              className="
                absolute
                left-3
                top-1/2
                -translate-y-1/2
                text-slate-400
              "

              size={17}
            />


            <input
              type="search"

              value={
                searchTerm
              }

              onChange={
                (
                  event
                ) => (
                  setSearchTerm(
                    event.target.value
                  )
                )
              }

              placeholder="Rechercher dans le tableau..."

              className="
                w-full
                rounded-lg
                border
                border-slate-300
                py-2.5
                pl-10
                pr-3
                text-sm
                outline-none
                focus:border-green-500
                focus:ring-4
                focus:ring-green-500/10
              "
            />

          </div>


          <span
            className="text-sm text-slate-500"
          >
            {visibleDocuments.length} document(s)
          </span>

        </div>


        {/* ===================================================
            TABLE
        =================================================== */}

        <div
          className="
            overflow-hidden
            rounded-xl
            border
            border-slate-200
            bg-white
            shadow-sm
          "
        >

          <div
            className="overflow-x-auto"
          >

            <table
              className="
                w-full
                min-w-[1550px]
                text-sm
              "
            >

              <thead
                className="
                  border-b
                  bg-slate-50
                  text-left
                  text-xs
                  uppercase
                  tracking-wide
                  text-slate-500
                "
              >

                <tr>

                  <th className="px-4 py-3">
                    Fichier
                  </th>

                  <th className="px-4 py-3">
                    Entreprise
                  </th>

                  <th className="px-4 py-3">
                    Catégorie
                  </th>

                  <th className="px-4 py-3">
                    N° facture
                  </th>

                  <th className="px-4 py-3">
                    Date
                  </th>

                  <th className="px-4 py-3">
                    Tiers
                  </th>

                  <th className="px-4 py-3 text-right">
                    HT
                  </th>

                  <th className="px-4 py-3 text-right">
                    TVA
                  </th>

                  <th className="px-4 py-3 text-right">
                    TTC
                  </th>

                  <th className="px-4 py-3">
                    Statut doc.
                  </th>

                  <th className="px-4 py-3">
                    Validation
                  </th>

                  <th className="px-4 py-3 text-center">
                    Saisie
                  </th>

                  <th className="px-4 py-3">
                    Actions
                  </th>

                </tr>

              </thead>


              <tbody>

                {/* CHARGEMENT */}

                {loading && (

                  <tr>

                    <td
                      colSpan={13}

                      className="
                        px-4
                        py-10
                        text-center
                        text-slate-400
                      "
                    >
                      Chargement...
                    </td>

                  </tr>

                )}


                {/* DOCUMENTS */}

                {!loading
                  && visibleDocuments.map(
                    (
                      document
                    ) => (

                      <tr
                        key={
                          document.id
                        }

                        onClick={
                          () => (
                            navigate(
                              `/documents/${document.id}`
                            )
                          )
                        }

                        className="
                          cursor-pointer
                          border-b
                          last:border-0
                          hover:bg-green-50/40
                        "
                      >

                        {/* FICHIER */}

                        <td
                          className="
                            max-w-[180px]
                            truncate
                            px-4
                            py-3
                            font-semibold
                            text-slate-800
                          "

                          title={
                            document.nom_fichier_original
                          }
                        >
                          {document.nom_fichier_original}
                        </td>


                        {/* ENTREPRISE */}

                        <td
                          className="px-4 py-3"
                        >
                          {document.entreprise_nom ?? "—"}
                        </td>


                        {/* CATÉGORIE */}

                        <td
                          className="px-4 py-3 capitalize"
                        >
                          {document.categorie ?? "—"}
                        </td>


                        {/* NUMÉRO */}

                        <td
                          className="px-4 py-3"
                        >
                          {document.numero_piece ?? "—"}
                        </td>


                        {/* DATE */}

                        <td
                          className="px-4 py-3"
                        >
                          {formatDate(
                            document.date_piece
                          )}
                        </td>


                        {/* TIERS */}

                        <td
                          className="px-4 py-3"
                        >
                          {document.tiers ?? "—"}
                        </td>


                        {/* HT */}

                        <td
                          className="px-4 py-3 text-right"
                        >
                          {formatMoney(
                            document.montant_ht
                          )}
                        </td>


                        {/* TVA */}

                        <td
                          className="px-4 py-3 text-right"
                        >

                          {formatMoney(
                            document.montant_tva
                          )}


                          {document.taux_tva && (

                            <span
                              className="ml-1 text-xs text-slate-400"
                            >
                              ({document.taux_tva}%)
                            </span>

                          )}

                        </td>


                        {/* TTC */}

                        <td
                          className="px-4 py-3 text-right font-bold"
                        >
                          {formatMoney(
                            document.montant_ttc
                          )}
                        </td>


                        {/* STATUT */}

                        <td
                          className={`
                            px-4
                            py-3
                            font-semibold
                            ${
                              DOCUMENT_STATUS_CLASSES[
                                document.statut
                              ]
                              ?? ""
                            }
                          `}
                        >
                          {
                            DOCUMENT_STATUS_LABELS[
                              document.statut
                            ]
                            ?? document.statut
                          }
                        </td>


                        {/* VALIDATION */}

                        <td
                          className="px-4 py-3"
                        >

                          {document.statut_validation
                            ? (

                              <div
                                className="flex items-center gap-2"
                              >

                                <span
                                  className={`
                                    rounded-full
                                    px-2.5
                                    py-1
                                    text-xs
                                    font-semibold
                                    ${
                                      VALIDATION_CLASSES[
                                        document.statut_validation
                                      ]
                                      ?? "bg-slate-100"
                                    }
                                  `}
                                >

                                  {
                                    VALIDATION_LABELS[
                                      document.statut_validation
                                    ]
                                    ?? document.statut_validation
                                  }

                                </span>


                                <AnomalyBadge
                                  detected={
                                    document.anomalie_detectee
                                  }

                                  details={
                                    document.anomalie_details
                                  }
                                />

                              </div>

                            )
                            : (

                              <span
                                className="text-slate-300"
                              >
                                —
                              </span>

                            )
                          }

                        </td>


                        {/* SAISIE */}

                        <td
                          className="px-4 py-3 text-center"
                        >

                          <input
                            type="checkbox"

                            checked={
                              document.saisie_topaze
                            }

                            disabled={
                              currentAction
                              === `saisie-${document.id}`
                            }

                            onChange={
                              (
                                event
                              ) => (
                                void handleToggleSaisie(
                                  event,
                                  document.id,
                                )
                              )
                            }

                            onClick={
                              (
                                event
                              ) => (
                                event.stopPropagation()
                              )
                            }

                            className="
                              h-4
                              w-4
                              accent-green-600
                            "

                            title={
                              document.categorie
                              === "banque"

                                ? "Relevé saisi"

                                : "Facture saisie dans Topaze"
                            }
                          />

                        </td>


                        {/* ACTIONS */}

                        <td
                          className="px-4 py-3"
                        >

                          <div
                            className="
                              flex
                              items-center
                              gap-1
                              whitespace-nowrap
                            "
                          >

                            {/* VÉRIFIER */}

                            <button
                              type="button"

                              onClick={
                                (
                                  event
                                ) => {

                                  event.stopPropagation();

                                  navigate(
                                    `/documents/${document.id}`
                                  );
                                }
                              }

                              className="
                                inline-flex
                                items-center
                                gap-1
                                rounded-md
                                px-2
                                py-1.5
                                text-xs
                                font-semibold
                                text-blue-700
                                hover:bg-blue-50
                              "
                            >

                              <FileSearch
                                size={14}
                              />

                              Vérifier

                            </button>


                            {/* FICHIER */}

                            <a
                              href={
                                getDocumentFileUrl(
                                  document.id
                                )
                              }

                              target="_blank"

                              rel="noreferrer"

                              onClick={
                                (
                                  event
                                ) => (
                                  event.stopPropagation()
                                )
                              }

                              className="
                                inline-flex
                                items-center
                                gap-1
                                rounded-md
                                px-2
                                py-1.5
                                text-xs
                                font-semibold
                                text-slate-600
                                hover:bg-slate-100
                              "
                            >

                              <ExternalLink
                                size={14}
                              />

                              Fichier

                            </a>


                            {/* RETRAITER */}

                            <button
                              type="button"

                              onClick={
                                (
                                  event
                                ) => (
                                  void handleRetraiter(
                                    event,
                                    document.id,
                                  )
                                )
                              }

                              disabled={
                                currentAction
                                === `retraiter-${document.id}`
                              }

                              className="
                                inline-flex
                                items-center
                                gap-1
                                rounded-md
                                px-2
                                py-1.5
                                text-xs
                                font-semibold
                                text-green-700
                                hover:bg-green-50
                                disabled:opacity-50
                              "
                            >

                              <RefreshCw
                                size={14}

                                className={
                                  currentAction
                                  === `retraiter-${document.id}`

                                    ? "animate-spin"

                                    : ""
                                }
                              />

                              Retraiter

                            </button>


                            {/* SUPPRIMER */}

                            <button
                              type="button"

                              onClick={
                                (
                                  event
                                ) => (
                                  void handleDelete(
                                    event,
                                    document,
                                  )
                                )
                              }

                              disabled={
                                currentAction
                                === `delete-${document.id}`
                              }

                              className="
                                inline-flex
                                items-center
                                gap-1
                                rounded-md
                                px-2
                                py-1.5
                                text-xs
                                font-semibold
                                text-red-600
                                hover:bg-red-50
                                disabled:opacity-50
                              "
                            >

                              <Trash2
                                size={14}
                              />

                              Supprimer

                            </button>

                          </div>

                        </td>

                      </tr>

                    )
                  )
                }


                {/* VIDE */}

                {!loading
                  && visibleDocuments.length === 0
                  && (

                    <tr>

                      <td
                        colSpan={13}

                        className="
                          px-4
                          py-12
                          text-center
                          text-slate-400
                        "
                      >
                        Aucun document pour ces filtres.
                      </td>

                    </tr>

                  )
                }

              </tbody>

            </table>

          </div>

        </div>

      </main>


      {/* =====================================================
          MODALE AJOUT ENTREPRISE
      ===================================================== */}

      {addCompanyOpen && (

        <div
          className="
            fixed
            inset-0
            z-[9999]
            flex
            items-center
            justify-center
            bg-slate-950/40
            p-4
            backdrop-blur-[1px]
          "

          onMouseDown={
            (
              event
            ) => {

              if (
                event.target
                === event.currentTarget

                && !creatingCompany
              ) {

                setAddCompanyOpen(
                  false
                );
              }
            }
          }
        >

          <div
            className="
              w-full
              max-w-md
              overflow-hidden
              rounded-2xl
              border
              border-slate-200
              bg-white
              shadow-2xl
            "
          >

            {/* EN-TÊTE MODALE */}

            <div
              className="
                flex
                items-start
                justify-between
                border-b
                border-slate-100
                px-5
                py-4
              "
            >

              <div
                className="flex items-center gap-3"
              >

                <div
                  className="
                    flex
                    h-10
                    w-10
                    items-center
                    justify-center
                    rounded-xl
                    bg-green-100
                    text-green-700
                  "
                >
                  <Building2
                    size={20}
                  />
                </div>


                <div>

                  <h2
                    className="text-base font-bold text-slate-900"
                  >
                    Ajouter une entreprise
                  </h2>


                  <p
                    className="mt-0.5 text-xs text-slate-500"
                  >
                    Ajoutez uniquement une société dont
                    le cabinet gère la comptabilité.
                  </p>

                </div>

              </div>


              <button
                type="button"

                onClick={
                  () => (
                    setAddCompanyOpen(
                      false
                    )
                  )
                }

                disabled={
                  creatingCompany
                }

                className="
                  rounded-lg
                  p-2
                  text-slate-400
                  hover:bg-slate-100
                  hover:text-slate-700
                  disabled:opacity-50
                "

                title="Fermer"
              >
                <X
                  size={18}
                />
              </button>

            </div>


            {/* FORMULAIRE */}

            <form
              className="p-5"

              onSubmit={
                (
                  event
                ) => {

                  event.preventDefault();

                  void handleCreateCompany();
                }
              }
            >

              <label
                htmlFor="new-company-name"

                className="
                  mb-2
                  block
                  text-sm
                  font-semibold
                  text-slate-700
                "
              >

                Nom de l'entreprise

                <span
                  className="text-red-500"
                >
                  {" "}*
                </span>

              </label>


              <input
                id="new-company-name"

                type="text"

                value={
                  newCompanyName
                }

                onChange={
                  (
                    event
                  ) => (
                    setNewCompanyName(
                      event.target.value
                    )
                  )
                }

                autoFocus

                maxLength={255}

                placeholder="Ex. ANZOBAT"

                className="
                  w-full
                  rounded-xl
                  border
                  border-slate-300
                  px-3.5
                  py-2.5
                  text-sm
                  outline-none
                  transition
                  focus:border-green-500
                  focus:ring-4
                  focus:ring-green-500/10
                "
              />


              <p
                className="mt-2 text-xs text-slate-400"
              >
                Pour commencer, le nom suffit.
                ICE, IF et RC pourront être enrichis plus tard.
              </p>


              <div
                className="
                  mt-5
                  flex
                  justify-end
                  gap-2
                "
              >

                {/* ANNULER */}

                <button
                  type="button"

                  onClick={
                    () => (
                      setAddCompanyOpen(
                        false
                      )
                    )
                  }

                  disabled={
                    creatingCompany
                  }

                  className="
                    rounded-lg
                    border
                    border-slate-200
                    bg-white
                    px-4
                    py-2
                    text-sm
                    font-semibold
                    text-slate-700
                    hover:bg-slate-50
                    disabled:opacity-50
                  "
                >
                  Annuler
                </button>


                {/* AJOUTER */}

                <button
                  type="submit"

                  disabled={
                    creatingCompany
                    || newCompanyName
                      .trim()
                      .length < 2
                  }

                  className="
                    inline-flex
                    items-center
                    gap-2
                    rounded-lg
                    bg-green-600
                    px-4
                    py-2
                    text-sm
                    font-semibold
                    text-white
                    hover:bg-green-700
                    disabled:cursor-not-allowed
                    disabled:opacity-50
                  "
                >

                  {creatingCompany
                    ? (

                      <>

                        <RefreshCw
                          size={15}
                          className="animate-spin"
                        />

                        Ajout...

                      </>

                    )
                    : (

                      <>

                        <Plus
                          size={15}
                        />

                        Ajouter

                      </>

                    )
                  }

                </button>

              </div>

            </form>

          </div>

        </div>

      )}

    </div>
  );
}


// ============================================================
// SECTION FILTRE
// ============================================================

function FilterSection(
  {
    title,
    children,
    action,
  }: {
    title: string;
    children: ReactNode;
    action?: ReactNode;
  },
) {

  return (

    <section>

      <div
        className="
          mb-2
          flex
          items-center
          justify-between
          gap-2
          px-2
        "
      >

        <p
          className="
            text-xs
            font-semibold
            uppercase
            tracking-wide
            text-slate-400
          "
        >
          {title}
        </p>


        {action}

      </div>


      <div
        className="space-y-1"
      >
        {children}
      </div>

    </section>
  );
}


// ============================================================
// BOUTON FILTRE
// ============================================================

function FilterButton(
  {
    active,
    onClick,
    children,
  }: {
    active: boolean;
    onClick: () => void;
    children: ReactNode;
  },
) {

  return (

    <button
      type="button"

      onClick={
        onClick
      }

      className={`
        block
        w-full
        rounded-lg
        px-3
        py-2
        text-left
        text-sm
        transition

        ${
          active

            ? "bg-green-100 font-semibold text-green-800"

            : "text-slate-700 hover:bg-slate-50"
        }
      `}
    >
      {children}
    </button>
  );
}