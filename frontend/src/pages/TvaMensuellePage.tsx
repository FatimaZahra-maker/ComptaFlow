import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { getTvaMensuelle, recalculerTvaV2 } from "../api/accountingApi";
import { chooseAvailableEntreprise, listAvailableEntreprises } from "../api/entreprisesApi";
import type { Entreprise } from "../types/entreprise";
import type { TvaAnnuelle, TvaMensuelle, TvaPeriodesAnnee } from "../types/registre";

const MOIS_LABELS = [
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

const CURRENT_YEAR = new Date().getFullYear();
const ANNEES = Array.from({ length: 5 }, (_, index) => CURRENT_YEAR - index);

function montant(value: string | number | null | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function formatMontant(value: string | number | null | undefined): string {
  return `${montant(value).toLocaleString("fr-MA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} MAD`;
}

function BadgeStatut({ item }: { item: TvaMensuelle }) {
  if (item.a_verifier) {
    return (
      <span className="inline-flex rounded-full bg-amber-100 px-2 py-1 text-xs font-medium text-amber-800">
        À vérifier
      </span>
    );
  }

  if (item.nombre_lignes_tva === 0) {
    return (
      <span className="inline-flex rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-600">
        Aucune TVA
      </span>
    );
  }

  return (
    <span className="inline-flex rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">
      Contrôlé
    </span>
  );
}

export function TvaMensuellePage() {
  const [entreprises, setEntreprises] = useState<Entreprise[]>([]);
  const [entrepriseId, setEntrepriseId] = useState("");
  const [annee, setAnnee] = useState(CURRENT_YEAR);
  const [donnees, setDonnees] = useState<TvaAnnuelle | null>(null);
  const [tvaV2, setTvaV2] = useState<TvaPeriodesAnnee | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [moisOuvert, setMoisOuvert] = useState<number | null>(null);

  useEffect(() => {
    setDonnees(null);
    setTvaV2(null);
    listAvailableEntreprises("tva", annee)
      .then((data) => {
        setEntreprises(data);
        setEntrepriseId((current) => chooseAvailableEntreprise(data, current));
      })
      .catch(() => setError("Impossible de charger les entreprises."));
  }, [annee]);

  const refresh = useCallback(async () => {
    if (!entrepriseId) return;

    setIsLoading(true);
    setError(null);
    try {
      const [data, periods] = await Promise.all([
        getTvaMensuelle({ entreprise_id: entrepriseId, annee }),
        recalculerTvaV2({ entreprise_id: entrepriseId, annee }),
      ]);
      setDonnees(data);
      setTvaV2(periods);
    } catch {
      setDonnees(null);
      setTvaV2(null);
      setError("Impossible de calculer la synthèse TVA comptable.");
    } finally {
      setIsLoading(false);
    }
  }, [entrepriseId, annee]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const maxValeur = useMemo(() => {
    if (!donnees) return 1;
    return Math.max(
      1,
      ...donnees.mensualites.flatMap((item) => [
        Math.abs(montant(item.tva_collectee)),
        Math.abs(montant(item.tva_deductible_charges)),
        Math.abs(montant(item.tva_deductible_immobilisations)),
      ]),
    );
  }, [donnees]);

  return (
    <div className="min-h-screen bg-gray-50 p-6 lg:p-8">
      <div className="mx-auto max-w-7xl">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">TVA comptable</h1>
            <p className="mt-1 text-sm text-gray-500">
              Calculée à partir des lignes Débit / Crédit validées du Grand Livre.
            </p>
          </div>

          <div className="flex flex-wrap gap-3 rounded-xl border bg-white p-3 shadow-sm">
            <select
              value={entrepriseId}
              onChange={(event) => setEntrepriseId(event.target.value)}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              <option value="">Sélectionner</option>
              {entreprises.map((entreprise) => (
                <option key={entreprise.id} value={entreprise.id}>
                  {entreprise.nom}
                </option>
              ))}
            </select>

            <select
              value={annee}
              onChange={(event) => setAnnee(Number(event.target.value))}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm"
            >
              {ANNEES.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </div>
        </div>

        {entreprises.length === 0 && (
          <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
            Aucune entreprise ne possède encore de données dans ce module.
          </div>
        )}

        {error && (
          <div className="mb-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {isLoading && (
          <div className="rounded-xl border bg-white p-6 text-sm text-gray-500 shadow-sm">
            Calcul de la TVA depuis le Grand Livre…
          </div>
        )}

        {donnees && !isLoading && (
          <>
            <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-medium text-amber-900">Synthèse comptable — pas encore une déclaration fiscale</p>
                  <p className="mt-1 text-sm text-amber-800">
                    Source : lignes comptables validées. {donnees.nombre_mois_a_verifier} mois à contrôler.
                  </p>
                </div>
                <span className="rounded-full bg-white px-3 py-1 text-xs font-medium text-amber-800 shadow-sm">
                  Validation comptable requise
                </span>
              </div>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-800">
                {donnees.limites.map((limite) => (
                  <li key={limite}>{limite}</li>
                ))}
              </ul>
            </div>

            <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-5">
              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">TVA collectée</p>
                <p className="mt-2 text-xl font-semibold text-gray-900">{formatMontant(donnees.total_tva_collectee)}</p>
                <p className="mt-1 text-xs text-gray-500">Famille 4455…</p>
              </div>

              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">TVA récup. charges</p>
                <p className="mt-2 text-xl font-semibold text-gray-900">{formatMontant(donnees.total_tva_deductible_charges)}</p>
                <p className="mt-1 text-xs text-gray-500">Famille 34552…</p>
              </div>

              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">TVA récup. immobilisations</p>
                <p className="mt-2 text-xl font-semibold text-gray-900">{formatMontant(donnees.total_tva_deductible_immobilisations)}</p>
                <p className="mt-1 text-xs text-gray-500">Famille 34551…</p>
              </div>

              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">TVA récupérable totale</p>
                <p className="mt-2 text-xl font-semibold text-gray-900">{formatMontant(donnees.total_tva_deductible)}</p>
              </div>

              <div className="rounded-xl border bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-gray-400">Solde technique annuel</p>
                <p className={`mt-2 text-xl font-semibold ${montant(donnees.total_tva_nette) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                  {formatMontant(donnees.total_tva_nette)}
                </p>
                <p className="mt-1 text-xs text-gray-500">Collectée − récupérable</p>
              </div>
            </div>

            {tvaV2 && (
              <div className="mb-6 overflow-hidden rounded-xl border bg-white shadow-sm">
                <div className="border-b px-5 py-4">
                  <h2 className="text-sm font-semibold text-gray-900">Périodes TVA V2</h2>
                  <p className="mt-1 text-xs text-gray-500">
                    Périodicité : {tvaV2.configuration?.periodicite ?? "non configurée"}. Les retenues sans règle explicite restent à vérifier.
                  </p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1180px] text-sm">
                    <thead className="border-b bg-gray-50 text-xs uppercase text-gray-500">
                      <tr>
                        <th className="p-3 text-left">Période</th>
                        <th className="p-3 text-right">Collectée</th>
                        <th className="p-3 text-right">Récup. charges</th>
                        <th className="p-3 text-right">Récup. immo.</th>
                        <th className="p-3 text-right">Crédit antérieur</th>
                        <th className="p-3 text-right">Régularisations</th>
                        <th className="p-3 text-right">TVA nette</th>
                        <th className="p-3 text-right">À payer</th>
                        <th className="p-3 text-right">Crédit à reporter</th>
                        <th className="p-3 text-center">Statut</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tvaV2.periodes.map((period) => (
                        <tr key={period.id} className="border-b last:border-0">
                          <td className="p-3 font-medium">{MOIS_LABELS[period.mois - 1]} {period.annee}</td>
                          <td className="p-3 text-right">{formatMontant(period.tva_collectee)}</td>
                          <td className="p-3 text-right">{formatMontant(period.tva_recuperable_charges)}</td>
                          <td className="p-3 text-right">{formatMontant(period.tva_recuperable_immobilisations)}</td>
                          <td className="p-3 text-right">{formatMontant(period.credit_anterieur)}</td>
                          <td className="p-3 text-right">{formatMontant(period.regularisations)}</td>
                          <td className="p-3 text-right font-semibold">{formatMontant(period.tva_nette)}</td>
                          <td className="p-3 text-right">{formatMontant(period.tva_a_payer)}</td>
                          <td className="p-3 text-right">{formatMontant(period.credit_a_reporter)}</td>
                          <td className="p-3 text-center">
                            <span className={`rounded-full px-2 py-1 text-xs ${period.a_verifier ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-700"}`}>
                              {period.a_verifier ? "À vérifier" : period.statut}
                            </span>
                            {period.anomalies.length > 0 && (
                              <p className="mt-1 max-w-[220px] text-[10px] text-amber-700">{period.anomalies.join(" · ")}</p>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="mb-6 rounded-xl border bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-900">Répartition mensuelle</h2>
                <div className="flex flex-wrap gap-3 text-xs text-gray-500">
                  <span>Collectée</span>
                  <span>Charges</span>
                  <span>Immobilisations</span>
                </div>
              </div>

              <div className="flex h-52 items-end gap-2 overflow-x-auto pb-2">
                {donnees.mensualites.map((item) => {
                  const collectee = Math.abs(montant(item.tva_collectee));
                  const charges = Math.abs(montant(item.tva_deductible_charges));
                  const immobilisations = Math.abs(montant(item.tva_deductible_immobilisations));

                  return (
                    <div key={item.mois} className="flex min-w-[54px] flex-1 flex-col items-center gap-2">
                      <div className="flex h-40 w-full items-end justify-center gap-1">
                        <div
                          className="w-1/3 rounded-t bg-blue-500"
                          style={{ height: `${(collectee / maxValeur) * 100}%` }}
                          title={`TVA collectée : ${formatMontant(item.tva_collectee)}`}
                        />
                        <div
                          className="w-1/3 rounded-t bg-violet-500"
                          style={{ height: `${(charges / maxValeur) * 100}%` }}
                          title={`TVA charges : ${formatMontant(item.tva_deductible_charges)}`}
                        />
                        <div
                          className="w-1/3 rounded-t bg-cyan-500"
                          style={{ height: `${(immobilisations / maxValeur) * 100}%` }}
                          title={`TVA immobilisations : ${formatMontant(item.tva_deductible_immobilisations)}`}
                        />
                      </div>
                      <span className="text-[11px] text-gray-500">{MOIS_LABELS[item.mois - 1].slice(0, 3)}</span>
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="overflow-hidden rounded-xl border bg-white shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1120px] text-sm">
                  <thead className="border-b bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
                    <tr>
                      <th className="p-3">Mois</th>
                      <th className="p-3 text-right">Collectée</th>
                      <th className="p-3 text-right">Récup. charges</th>
                      <th className="p-3 text-right">Récup. immo.</th>
                      <th className="p-3 text-right">Récup. totale</th>
                      <th className="p-3 text-right">Solde</th>
                      <th className="p-3 text-right">À payer*</th>
                      <th className="p-3 text-right">Crédit*</th>
                      <th className="p-3 text-center">Statut</th>
                      <th className="p-3 text-right">Détail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {donnees.mensualites.map((item) => (
                      <Fragment key={item.mois}>
                        <tr key={`month-${item.mois}`} className="border-b last:border-0">
                          <td className="p-3 font-medium text-gray-900">{MOIS_LABELS[item.mois - 1]}</td>
                          <td className="p-3 text-right">{formatMontant(item.tva_collectee)}</td>
                          <td className="p-3 text-right">{formatMontant(item.tva_deductible_charges)}</td>
                          <td className="p-3 text-right">{formatMontant(item.tva_deductible_immobilisations)}</td>
                          <td className="p-3 text-right font-medium">{formatMontant(item.tva_deductible)}</td>
                          <td className={`p-3 text-right font-semibold ${montant(item.tva_nette) >= 0 ? "text-emerald-700" : "text-red-600"}`}>
                            {formatMontant(item.tva_nette)}
                          </td>
                          <td className="p-3 text-right">{formatMontant(item.tva_a_payer)}</td>
                          <td className="p-3 text-right">{formatMontant(item.credit_tva)}</td>
                          <td className="p-3 text-center"><BadgeStatut item={item} /></td>
                          <td className="p-3 text-right">
                            <button
                              type="button"
                              onClick={() => setMoisOuvert((current) => current === item.mois ? null : item.mois)}
                              className="text-xs font-medium text-blue-600 hover:text-blue-800"
                            >
                              {moisOuvert === item.mois ? "Masquer" : "Voir"}
                            </button>
                          </td>
                        </tr>

                        {moisOuvert === item.mois && (
                          <tr key={`detail-${item.mois}`} className="border-b bg-gray-50/70">
                            <td colSpan={10} className="p-4">
                              <div className="grid gap-4 lg:grid-cols-2">
                                <div>
                                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Comptes TVA du mois</p>
                                  {item.comptes.length === 0 ? (
                                    <p className="text-sm text-gray-500">Aucune ligne TVA validée.</p>
                                  ) : (
                                    <div className="overflow-hidden rounded-lg border bg-white">
                                      <table className="w-full text-xs">
                                        <thead className="bg-gray-50 text-gray-500">
                                          <tr>
                                            <th className="p-2 text-left">Compte</th>
                                            <th className="p-2 text-left">Nature</th>
                                            <th className="p-2 text-right">Débit</th>
                                            <th className="p-2 text-right">Crédit</th>
                                            <th className="p-2 text-right">Net</th>
                                          </tr>
                                        </thead>
                                        <tbody>
                                          {item.comptes.map((compte) => (
                                            <tr key={`${item.mois}-${compte.compte}-${compte.nature}`} className="border-t">
                                              <td className="p-2 font-mono">{compte.compte}</td>
                                              <td className="p-2">{compte.nature}</td>
                                              <td className="p-2 text-right">{formatMontant(compte.debit)}</td>
                                              <td className="p-2 text-right">{formatMontant(compte.credit)}</td>
                                              <td className="p-2 text-right font-medium">{formatMontant(compte.montant_net)}</td>
                                            </tr>
                                          ))}
                                        </tbody>
                                      </table>
                                    </div>
                                  )}
                                </div>

                                <div>
                                  <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">Contrôles</p>
                                  <div className="rounded-lg border bg-white p-3 text-sm text-gray-600">
                                    <p>{item.nombre_ecritures} écriture(s) Achat/Vente validée(s).</p>
                                    <p>{item.nombre_lignes_tva} ligne(s) TVA dans le Grand Livre.</p>
                                    {item.raisons_verification.length > 0 ? (
                                      <ul className="mt-3 list-disc space-y-1 pl-5 text-amber-800">
                                        {item.raisons_verification.map((raison) => (
                                          <li key={raison}>{raison}</li>
                                        ))}
                                      </ul>
                                    ) : (
                                      <p className="mt-3 text-emerald-700">Aucune incohérence TVA détectée par les contrôles de cette V1.</p>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="border-t bg-gray-50 px-4 py-3 text-xs text-gray-500">
                * « À payer » et « Crédit » sont des positions techniques mensuelles, sans report automatique entre périodes.
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
