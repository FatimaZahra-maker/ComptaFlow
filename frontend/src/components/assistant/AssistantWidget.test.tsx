import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AssistantPage } from "../../pages/AssistantPage";
import { AssistantConversationProvider } from "./AssistantConversationContext";
import { AssistantWidget } from "./AssistantWidget";
import { assistantPositionStorageKey, clampAssistantPosition } from "./assistantWidgetPosition";

const askAssistant = vi.fn();
const currentUser = {
  id: "user-1", email: "fati@example.test", nom: "Radoui", prenom: "Fati",
  role: "collaborateur", cabinet_id: "cabinet-1",
};

vi.mock("../../context/AuthContext", () => ({
  useAuth: () => ({ user: currentUser }),
}));
vi.mock("../../api/assistantApi", () => ({
  askAssistant: (...args: unknown[]) => askAssistant(...args),
}));
vi.mock("../../api/entreprisesApi", () => ({
  listEntreprises: () => Promise.resolve([{ id: "company-1", nom: "ANZOBAT", ice: null, creee_automatiquement: false }]),
}));
vi.mock("../../api/client", () => ({ fetchApiBlob: vi.fn() }));

const companyResponse = {
  conversation_id: "11111111-1111-1111-1111-111111111111",
  response_type: "company_list",
  intent: "list_entreprises",
  message: "Vous avez accès à 1 entreprise.",
  filters: {},
  documents: [],
  companies: [{
    entreprise_id: "company-1", nom: "ANZOBAT", ice: "001122334455667",
    identifiant_fiscal: null, is_active: true,
    actions: [{ label: "Voir les documents", kind: "route", route: "/chronos?entreprise_id=company-1", api_path: null, filename: null }],
  }],
  payments: [], total_count: 1, aggregate: null, sources: [], warnings: [],
  clarification_question: null, context_document_id: null,
  data: [], suggestions: [], plan_summary: { domain: "entreprises", operation: "list" },
  page: 1, page_size: 10, has_more: false,
};

const dataResponse = {
  ...companyResponse,
  response_type: "data_list",
  intent: "taches",
  message: "12 résultats trouvés.",
  companies: [], total_count: 12, has_more: true,
  data: [{
    resource_type: "taches", resource_id: "task-1", title: "Déclarer la TVA",
    subtitle: "ANZOBAT", fields: { statut: "a_faire", priorite: "haute" }, actions: [],
  }],
  suggestions: ["Afficher les tâches en retard"],
  plan_summary: { domain: "taches", operation: "list", provider: "deterministic" },
};

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname}{location.search}</output>;
}

function renderWidget(path = "/dashboard") {
  return render(<MemoryRouter initialEntries={[path]}>
    <AssistantConversationProvider>
      <LocationProbe />
      <AssistantWidget />
    </AssistantConversationProvider>
  </MemoryRouter>);
}

describe("AssistantWidget", () => {
  beforeEach(() => {
    askAssistant.mockReset();
    askAssistant.mockResolvedValue(companyResponse);
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1200 });
    Object.defineProperty(window, "innerHeight", { configurable: true, value: 800 });
  });

  it("borne toujours la position à l'intérieur de la fenêtre", () => {
    expect(clampAssistantPosition({ x: -500, y: 900 }, 320, 500)).toEqual({ x: 12, y: 432 });
  });

  it("ouvre et réduit le panneau sans quitter la page", async () => {
    const user = userEvent.setup();
    renderWidget();
    await user.click(screen.getByRole("button", { name: "Ouvrir l'Assistant ComptaFlow" }));
    expect(screen.getByRole("dialog", { name: "Assistant ComptaFlow" })).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/dashboard");
    await user.click(screen.getByRole("button", { name: "Réduire l'Assistant" }));
    expect(screen.queryByRole("dialog", { name: "Assistant ComptaFlow" })).not.toBeInTheDocument();
  });

  it("distingue le glisser du clic, sauvegarde et restaure la position", async () => {
    localStorage.setItem(assistantPositionStorageKey(currentUser.id), JSON.stringify({ x: 100, y: 120 }));
    renderWidget();
    const button = await screen.findByTestId("assistant-floating-button");
    await waitFor(() => expect(button).toHaveStyle({ left: "100px", top: "120px" }));

    fireEvent.pointerDown(button, { button: 0, pointerId: 1, clientX: 100, clientY: 120 });
    fireEvent.pointerMove(button, { pointerId: 1, clientX: 260, clientY: 300 });
    fireEvent.pointerUp(button, { pointerId: 1, clientX: 260, clientY: 300 });
    fireEvent.click(button);

    expect(screen.queryByRole("dialog", { name: "Assistant ComptaFlow" })).not.toBeInTheDocument();
    const saved = JSON.parse(localStorage.getItem(assistantPositionStorageKey(currentUser.id)) ?? "{}");
    expect(saved.x).toBeGreaterThan(100);
    expect(saved.y).toBeGreaterThan(120);
  });

  it("rend les entreprises, navigue et conserve la conversation après fermeture", async () => {
    const user = userEvent.setup();
    renderWidget();
    await user.click(screen.getByRole("button", { name: "Ouvrir l'Assistant ComptaFlow" }));
    await user.type(screen.getByRole("textbox", { name: "Question pour l'Assistant" }), "quelle sont les entreprise existe ?");
    await user.click(screen.getByRole("button", { name: "Envoyer" }));

    const companyCard = await screen.findByTestId("assistant-company-card");
    expect(within(companyCard).getByText("ANZOBAT")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Voir les documents" }));
    expect(screen.getByTestId("location")).toHaveTextContent("/chronos?entreprise_id=company-1");
    await user.click(screen.getByRole("button", { name: "Réduire l'Assistant" }));
    await user.click(screen.getByRole("button", { name: "Ouvrir l'Assistant ComptaFlow" }));
    expect(screen.getByText("quelle sont les entreprise existe ?")).toBeInTheDocument();
    expect(within(screen.getByTestId("assistant-company-card")).getByText("ANZOBAT")).toBeInTheDocument();
  });

  it("affiche les cartes génériques, les suggestions et charge la page suivante", async () => {
    const user = userEvent.setup();
    askAssistant
      .mockResolvedValueOnce(dataResponse)
      .mockResolvedValueOnce({ ...dataResponse, page: 2, has_more: false, message: "2 résultats supplémentaires." });
    renderWidget();
    await user.click(screen.getByRole("button", { name: "Ouvrir l'Assistant ComptaFlow" }));
    await user.type(screen.getByRole("textbox", { name: "Question pour l'Assistant" }), "Liste les tâches");
    await user.click(screen.getByRole("button", { name: "Envoyer" }));
    expect(await screen.findByText("Déclarer la TVA")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Afficher les tâches en retard" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Voir plus de résultats" }));
    await waitFor(() => expect(askAssistant).toHaveBeenLastCalledWith(expect.objectContaining({ page: 2 })));
  });

  it("masque le cercle sur la page complète et conserve /assistant", () => {
    render(<MemoryRouter initialEntries={["/assistant"]}>
      <AssistantConversationProvider>
        <AssistantPage />
        <AssistantWidget />
      </AssistantConversationProvider>
    </MemoryRouter>);
    expect(screen.getByTestId("assistant-conversation-page")).toBeInTheDocument();
    expect(screen.queryByTestId("assistant-floating-button")).not.toBeInTheDocument();
  });
});

describe("visibilité sur la connexion", () => {
  it("masque le cercle sur /login", () => {
    renderWidget("/login");
    expect(screen.queryByTestId("assistant-floating-button")).not.toBeInTheDocument();
  });
});
