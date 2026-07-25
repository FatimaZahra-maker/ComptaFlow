export interface MouvementBancaire {
  id: string;
  document_id: string;
  entreprise_id: string;
  date_operation: string;
  libelle: string;
  reference?: string | null;
  type_mouvement: "DEBIT" | "CREDIT";
  montant: string | number;
  solde_apres_operation?: string | number | null;
}