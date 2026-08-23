import { EntriesTablePage } from "../components/EntriesTablePage";

export function VentesPage() {
  return (
    <EntriesTablePage
      title="Ventes"
      description="Écritures de vente issues des factures clients."
      typeEcriture="vente"
      emptyMessage="Aucune écriture de vente ne correspond aux filtres."
    />
  );
}