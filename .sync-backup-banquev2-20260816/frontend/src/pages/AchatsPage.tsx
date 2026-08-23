import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  useNavigate,
} from "react-router-dom";

import {
  ExternalLink,
  FileSearch,
  RefreshCw,
  Search,
} from "lucide-react";

import {
  listEntries,
} from "../api/accountingApi";

import {
  getDocumentFileUrl,
} from "../api/documentsApi";

import {
  listEntreprises,
} from "../api/entreprisesApi";

import {
  AnomalyBadge,
} from "../components/AnomalyBadge";

import type {
  Ecriture,
} from "../types/ecriture";

import type {
  Entreprise,
} from "../types/entreprise";


const ACTIVE_ENTREPRISE_KEY =
  "comptaflow_active_entreprise_id";


const MONTHS = [
  "Tous les mois",
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


const STATUS_LABELS:
Record<string, string> = {

  brouillon:
    "Brouillon",

  a_verifier:
    "À vérifier",

  valide:
    "Validée",

  rejete:
    "Rejetée",
};


const STATUS_CLASSES:
Record<string, string> = {

  brouillon:
    "bg-slate-100 text-slate-700",

  a_verifier:
    "bg-orange-100 text-orange-700",

  valide:
    "bg-green-100 text-green-700",

  rejete:
    "bg-red-100 text-red-700",
};


function readActiveCompanyId():
string {

  try {

    return (
      localStorage.getItem(
        ACTIVE_ENTREPRISE_KEY,
      )
      ?? ""
    );

  } catch {

    return "";
  }
}


function toNumber(
  value: string | null,
): number {

  const parsed = Number(
    value
    ?? 0
  );

  return (
    Number.isFinite(
      parsed
    )
      ? parsed
      : 0
  );
}


function formatMoney(
  value:
    string
    | number
    | null,
): string {

  const amount = (
    typeof value
    === "number"

      ? value

      : toNumber(
          value
        )
  );

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
  );
}


function formatDate(
  value: string | null,
): string {

  if (!value) {
    return "—";
  }

  const date = new Date(
    `${value}T00:00:00`
  );

  return (
    Number.isNaN(
      date.getTime()
    )

      ? value

      : date.toLocaleDateString(
          "fr-FR"
        )
  );
}


function formatRate(
  value: string | null,
): string {

  if (
    value === null
    || value === ""
  ) {

    return "—";
  }

  return `${value} %`;
}


export function AchatsPage() {

  const navigate = (
    useNavigate()
  );

  const currentYear = (
    new Date()
    .getFullYear()
  );


  const [
    companies,
    setCompanies,
  ] = useState<
    Entreprise[]
  >([]);


  const [
    companyId,
    setCompanyId,
  ] = useState(
    readActiveCompanyId
  );


  const [
    entries,
    setEntries,
  ] = useState<
    Ecriture[]
  >([]);


  const [
    search,
    setSearch,
  ] = useState(
    ""
  );


  const [
    year,
    setYear,
  ] = useState<
    number | ""
  >("");


  const [
    month,
    setMonth,
  ] = useState<
    number | ""
  >("");


  const [
    loading,
    setLoading,
  ] = useState(
    true
  );


  const [
    error,
    setError,
  ] = useState<
    string | null
  >(null);


  const selectedCompany = (
    useMemo(
      () => (
        companies.find(
          company =>
            company.id
            === companyId
        )
        ?? null
      ),
      [
        companies,
        companyId,
      ],
    )
  );


  const years = (
    useMemo(
      () => (
        Array.from(
          {
            length: 7,
          },
          (
            _,
            index,
          ) => (
            currentYear
            + 1
            - index
          ),
        )
      ),
      [
        currentYear,
      ],
    )
  );


  const totals = (
    useMemo(
      () => (
        entries.reduce(
          (
            accumulator,
            entry,
          ) => ({
            ttc:
              accumulator.ttc
              + toNumber(
                  entry.montant_ttc
                ),

            tva:
              accumulator.tva
              + toNumber(
                  entry.montant_tva
                ),

            ht:
              accumulator.ht
              + toNumber(
                  entry.montant_ht
                ),
          }),
          {
            ttc: 0,
            tva: 0,
            ht: 0,
          },
        )
      ),
      [
        entries,
      ],
    )
  );


  const refresh = (
    useCallback(
      async () => {

        if (!companyId) {

          setEntries(
            []
          );

          setLoading(
            false
          );

          setError(
            null
          );

          return;
        }


        setLoading(
          true
        );

        setError(
          null
        );


        try {

          const data = (
            await listEntries(
              {
                entreprise_id:
                  companyId,

                type_ecriture:
                  "achat",

                recherche:
                  search.trim()
                  || undefined,

                annee:
                  year === ""
                    ? undefined
                    : year,

                periodicite:
                  year === ""
                    ? undefined

                    : month === ""
                      ? "annuelle"
                      : "mensuelle",

                mois:
                  (
                    year !== ""
                    && month !== ""
                  )
                    ? month
                    : undefined,
              },
            )
          );


          setEntries(
            data
          );

        } catch {

          setEntries(
            []
          );

          setError(
            (
              "Impossible de charger "
              + "le journal d'achat."
            )
          );

        } finally {

          setLoading(
            false
          );
        }
      },
      [
        companyId,
        month,
        search,
        year,
      ],
    )
  );


  useEffect(
    () => {

      listEntreprises()
        .then(
          setCompanies
        )
        .catch(
          () => (
            setError(
              (
                "Impossible de charger "
                + "les entreprises."
              )
            )
          )
        );
    },
    [],
  );


  useEffect(
    () => {

      function handleActiveCompanyChanged(
        event: Event,
      ) {

        const customEvent =
          event as CustomEvent<
            string | null
          >;

        setCompanyId(
          customEvent.detail
          ?? ""
        );
      }


      window.addEventListener(
        "entreprise-active-changed",
        handleActiveCompanyChanged,
      );


      return () => {

        window.removeEventListener(
          "entreprise-active-changed",
          handleActiveCompanyChanged,
        );
      };
    },
    [],
  );


  useEffect(
    () => {

      const timer = (
        window.setTimeout(
          () => (
            void refresh()
          ),
          250,
        )
      );


      return () => (
        window.clearTimeout(
          timer
        )
      );
    },
    [
      refresh,
    ],
  );


  return (

    <div
      className="
        min-h-full
        bg-slate-50
        p-5
        lg:p-8
      "
    >

      <div
        className="
          mx-auto
          max-w-[1900px]
        "
      >

        {/* HEADER */}

        <div
          className="
            mb-6
            flex
            flex-wrap
            items-start
            justify-between
            gap-4
          "
        >

          <div>

            <h1
              className="
                text-2xl
                font-bold
                text-slate-900
              "
            >
              Journal d'achat
            </h1>


            <p
              className="
                mt-1
                text-sm
                text-slate-500
              "
            >

              Généré automatiquement
              à partir des factures
              d'achat de l'entreprise
              sélectionnée.

            </p>


            {
              selectedCompany
              && (

                <p
                  className="
                    mt-2
                    text-sm
                    font-semibold
                    text-green-700
                  "
                >

                  Entreprise :
                  {" "}
                  {
                    selectedCompany.nom
                  }

                </p>
              )
            }

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
              || !companyId
            }

            className="
              inline-flex
              items-center
              gap-2
              rounded-lg
              border
              bg-white
              px-4
              py-2
              text-sm
              font-semibold
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

        {
          error
          && (

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
          )
        }


        {/* FILTRES */}

        <section
          className="
            mb-5
            rounded-xl
            border
            border-slate-200
            bg-white
            p-4
            shadow-sm
          "
        >

          <div
            className="
              grid
              gap-3
              md:grid-cols-2
              xl:grid-cols-[1.4fr_260px_150px_180px]
            "
          >

            {/* SEARCH */}

            <div
              className="relative"
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
                  search
                }

                onChange={
                  event => (
                    setSearch(
                      event.target.value
                    )
                  )
                }

                placeholder="
                  Fournisseur, facture
                  ou fichier...
                "

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


            {/* ENTREPRISE */}

            <select
              value={
                companyId
              }

              onChange={
                event => (
                  setCompanyId(
                    event.target.value
                  )
                )
              }

              className="
                rounded-lg
                border
                border-slate-300
                px-3
                py-2.5
                text-sm
              "
            >

              <option value="">
                Choisir une entreprise
              </option>


              {
                companies.map(
                  company => (

                    <option
                      key={
                        company.id
                      }

                      value={
                        company.id
                      }
                    >

                      {
                        company.nom
                      }

                    </option>
                  )
                )
              }

            </select>


            {/* ANNEE */}

            <select
              value={
                year
              }

              onChange={
                event => {

                  setYear(
                    event.target.value
                      ? Number(
                          event.target.value
                        )
                      : ""
                  );

                  setMonth(
                    ""
                  );
                }
              }

              className="
                rounded-lg
                border
                border-slate-300
                px-3
                py-2.5
                text-sm
              "
            >

              <option value="">
                Toutes années
              </option>


              {
                years.map(
                  item => (

                    <option
                      key={
                        item
                      }

                      value={
                        item
                      }
                    >

                      {item}

                    </option>
                  )
                )
              }

            </select>


            {/* MOIS */}

            <select
              value={
                month
              }

              onChange={
                event => (
                  setMonth(
                    event.target.value
                      ? Number(
                          event.target.value
                        )
                      : ""
                  )
                )
              }

              disabled={
                year === ""
              }

              className="
                rounded-lg
                border
                border-slate-300
                px-3
                py-2.5
                text-sm
                disabled:bg-slate-100
                disabled:text-slate-400
              "
            >

              {
                MONTHS.map(
                  (
                    label,
                    index,
                  ) => (

                    <option
                      key={
                        label
                      }

                      value={
                        index === 0
                          ? ""
                          : index
                      }
                    >

                      {label}

                    </option>
                  )
                )
              }

            </select>

          </div>

        </section>


        {/* TOTAUX */}

        <div
          className="
            mb-5
            grid
            gap-4
            sm:grid-cols-2
            xl:grid-cols-4
          "
        >

          <div
            className="
              rounded-xl
              border
              border-slate-200
              bg-white
              p-4
              shadow-sm
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
              Factures
            </p>


            <p
              className="
                mt-2
                text-xl
                font-bold
                text-slate-900
              "
            >

              {
                entries.length
              }

            </p>

          </div>


          <div
            className="
              rounded-xl
              border
              border-slate-200
              bg-white
              p-4
              shadow-sm
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
              Total TTC
            </p>


            <p
              className="
                mt-2
                text-xl
                font-bold
                text-slate-900
              "
            >

              {
                formatMoney(
                  totals.ttc
                )
              }
              {" "}
              MAD

            </p>

          </div>


          <div
            className="
              rounded-xl
              border
              border-slate-200
              bg-white
              p-4
              shadow-sm
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
              Total TVA
            </p>


            <p
              className="
                mt-2
                text-xl
                font-bold
                text-slate-900
              "
            >

              {
                formatMoney(
                  totals.tva
                )
              }
              {" "}
              MAD

            </p>

          </div>


          <div
            className="
              rounded-xl
              border
              border-slate-200
              bg-white
              p-4
              shadow-sm
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
              Total HT
            </p>


            <p
              className="
                mt-2
                text-xl
                font-bold
                text-slate-900
              "
            >

              {
                formatMoney(
                  totals.ht
                )
              }
              {" "}
              MAD

            </p>

          </div>

        </div>


        {/* TABLEAU */}

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
            className="
              overflow-x-auto
            "
          >

            <table
              className="
                w-full
                min-w-[1900px]
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

                  <th className="px-3 py-3">
                    Date
                  </th>

                  <th className="px-3 py-3">
                    Compte fournisseur
                  </th>

                  <th className="px-3 py-3">
                    Fournisseur
                  </th>

                  <th
                    className="
                      px-3
                      py-3
                      text-right
                    "
                  >
                    TTC
                  </th>

                  <th className="px-3 py-3">
                    Taux TVA
                  </th>

                  <th className="px-3 py-3">
                    Compte TVA
                  </th>

                  <th
                    className="
                      px-3
                      py-3
                      text-right
                    "
                  >
                    TVA
                  </th>

                  <th className="px-3 py-3">
                    Compte HT
                  </th>

                  <th
                    className="
                      px-3
                      py-3
                      text-right
                    "
                  >
                    HT
                  </th>

                  <th className="px-3 py-3">
                    Libellé
                  </th>

                  <th className="px-3 py-3">
                    N° pièce
                  </th>

                  <th className="px-3 py-3">
                    Statut
                  </th>

                  <th className="px-3 py-3">
                    Facture
                  </th>

                </tr>

              </thead>


              <tbody>

                {/* CHARGEMENT */}

                {
                  loading
                  && (

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
                  )
                }


                {/* AUCUNE ENTREPRISE */}

                {
                  !loading
                  && !companyId
                  && (

                    <tr>

                      <td
                        colSpan={13}

                        className="
                          px-4
                          py-12
                          text-center
                          text-slate-500
                        "
                      >

                        Choisissez une entreprise
                        pour afficher son journal
                        d'achat.

                      </td>

                    </tr>
                  )
                }


                {/* LIGNES */}

                {
                  !loading
                  && companyId
                  && entries.map(
                    entry => (

                      <tr
                        key={
                          entry.id
                        }

                        className="
                          border-b
                          last:border-0
                          hover:bg-slate-50/70
                        "
                      >

                        {/* DATE */}

                        <td
                          className="
                            px-3
                            py-3
                          "
                        >

                          {
                            formatDate(
                              entry.date_piece
                            )
                          }

                        </td>


                        {/* COMPTE FOURNISSEUR */}

                        <td
                          className="
                            px-3
                            py-3
                            font-mono
                            text-xs
                            font-semibold
                          "
                        >

                          {
                            entry.compte_tiers
                            ?? "—"
                          }

                        </td>


                        {/* FOURNISSEUR */}

                        <td
                          className="
                            px-3
                            py-3
                            font-medium
                          "
                        >

                          {
                            entry.tiers
                            ?? "—"
                          }

                        </td>


                        {/* TTC */}

                        <td
                          className="
                            px-3
                            py-3
                            text-right
                            font-bold
                          "
                        >

                          {
                            formatMoney(
                              entry.montant_ttc
                            )
                          }

                        </td>


                        {/* TAUX */}

                        <td
                          className="
                            px-3
                            py-3
                          "
                        >

                          {
                            formatRate(
                              entry.taux_tva
                            )
                          }

                        </td>


                        {/* COMPTE TVA */}

                        <td
                          className="
                            px-3
                            py-3
                            font-mono
                            text-xs
                          "
                        >

                          {
                            entry.compte_tva
                            ?? "—"
                          }

                        </td>


                        {/* TVA */}

                        <td
                          className="
                            px-3
                            py-3
                            text-right
                          "
                        >

                          {
                            formatMoney(
                              entry.montant_tva
                            )
                          }

                        </td>


                        {/* COMPTE HT */}

                        <td
                          className="
                            px-3
                            py-3
                            font-mono
                            text-xs
                          "
                        >

                          {
                            entry.compte_ht
                            ?? "—"
                          }

                        </td>


                        {/* HT */}

                        <td
                          className="
                            px-3
                            py-3
                            text-right
                          "
                        >

                          {
                            formatMoney(
                              entry.montant_ht
                            )
                          }

                        </td>


                        {/* LIBELLE */}

                        <td
                          className="
                            px-3
                            py-3
                            font-medium
                          "
                        >

                          {
                            entry.libelle
                            ?? "—"
                          }

                        </td>


                        {/* NUMERO */}

                        <td
                          className="
                            px-3
                            py-3
                          "
                        >

                          {
                            entry.numero_piece
                            ?? "—"
                          }

                        </td>


                        {/* STATUT */}

                        <td
                          className="
                            px-3
                            py-3
                          "
                        >

                          <div
                            className="
                              flex
                              items-center
                              gap-2
                            "
                          >

                            <span
                              className={`
                                rounded-full
                                px-2.5
                                py-1
                                text-xs
                                font-semibold
                                ${
                                  STATUS_CLASSES[
                                    entry.statut_validation
                                  ]
                                }
                              `}
                            >

                              {
                                STATUS_LABELS[
                                  entry.statut_validation
                                ]
                              }

                            </span>


                            <AnomalyBadge
                              detected={
                                entry.anomalie_detectee
                              }

                              details={
                                entry.anomalie_details
                              }
                            />

                          </div>

                        </td>


                        {/* DOCUMENT */}

                        <td
                          className="
                            px-3
                            py-3
                          "
                        >

                          <div
                            className="
                              flex
                              gap-1
                              whitespace-nowrap
                            "
                          >

                            <button
                              type="button"

                              onClick={
                                () => (
                                  navigate(
                                    `/documents/${entry.document_id}`
                                  )
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
                                text-blue-700
                                hover:bg-blue-50
                              "
                            >

                              <FileSearch
                                size={14}
                              />

                              Voir

                            </button>


                            <a
                              href={
                                getDocumentFileUrl(
                                  entry.document_id
                                )
                              }

                              target="_blank"

                              rel="noreferrer"

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

                              PDF

                            </a>

                          </div>

                        </td>

                      </tr>
                    )
                  )
                }


                {/* AUCUNE FACTURE */}

                {
                  !loading
                  && companyId
                  && entries.length === 0
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

                        Aucune facture d'achat
                        pour cette entreprise
                        et cette période.

                      </td>

                    </tr>
                  )
                }

              </tbody>

            </table>

          </div>

        </div>

      </div>

    </div>
  );
}