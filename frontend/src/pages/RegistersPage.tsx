import { EntriesTablePage } from "../components/EntriesTablePage";

export function RegistersPage() {
  return (
    <EntriesTablePage
      title="Écritures comptables"
      description="Contrôlez, validez, rejetez et suivez la saisie des écritures extraites."
      emptyMessage="Aucune écriture comptable n'a encore été générée."
    />
  );
}