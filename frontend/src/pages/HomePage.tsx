import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

interface CarteNav {
  titre: string;
  description: string;
  route: string;
  disponible: boolean;
}

// CORRIGÉ : la carte "Notifications" pointait vers "/tasks", une route
// qui n'existe pas dans App.tsx (la vraie route est "/notifications").
// C'était la cause du "Bientôt disponible" et du lien mort.
// Elle est maintenant activée et pointe vers la bonne route.
const CARTES: CarteNav[] = [
  { titre: "Tableau de bord", description: "Vue d'ensemble et indicateurs", route: "/dashboard", disponible: true },
  { titre: "Chronos", description: "Entreprise / Année / Mois / Catégorie", route: "/chronos", disponible: true },
  { titre: "Écritures", description: "HT, TVA, TTC par facture", route: "/registers", disponible: true },
  { titre: "Registre comptable", description: "Totaux HT/TVA/TTC par catégorie et période", route: "/registres", disponible: true },
  { titre: "Notifications", description: "Alertes et tâches en attente", route: "/notifications", disponible: true },
  { titre: "Importer un document", description: "Upload et traitement", route: "/upload", disponible: true },
];

export function HomePage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  return (
    <div className="p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-2xl font-semibold mb-1">Bonjour, {user?.nom ?? "Cabinet"}</h1>
        <p className="text-gray-500 mb-6">Que voulez-vous consulter aujourd'hui ?</p>

        <div className="grid grid-cols-3 gap-4">
          {CARTES.map((carte) => (
            <button
              key={carte.titre}
              onClick={() => carte.disponible && navigate(carte.route)}
              disabled={!carte.disponible}
              className={`text-left border rounded-lg p-5 bg-white transition ${
                carte.disponible
                  ? "hover:shadow-md hover:border-green-300 cursor-pointer"
                  : "opacity-40 cursor-not-allowed"
              }`}
            >
              <p className="font-medium mb-1">{carte.titre}</p>
              <p className="text-sm text-gray-500">{carte.description}</p>
              {!carte.disponible && <p className="text-xs text-orange-500 mt-2">Bientôt disponible (MVC4)</p>}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}