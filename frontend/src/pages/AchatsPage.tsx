import { EntriesTablePage } from "../components/EntriesTablePage";

export function AchatsPage() {
  return (
    <EntriesTablePage
      title="Achats"
      description="Écritures d'achat issues des factures fournisseurs."
      typeEcriture="achat"
      emptyMessage="Aucune écriture d'achat ne correspond aux filtres."
    />
  );
}