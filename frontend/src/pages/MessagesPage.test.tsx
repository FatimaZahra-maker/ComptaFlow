import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MessagesPage } from "./MessagesPage";

const { conversationMock, contactsMock, navigateMock, planMock, sendMock } = vi.hoisted(() => ({
  conversationMock: vi.fn(),
  contactsMock: vi.fn(),
  navigateMock: vi.fn(),
  planMock: vi.fn(),
  sendMock: vi.fn(),
}));

vi.mock("../api/messagesApi", () => ({
  getConversation: conversationMock,
  listMessageContacts: contactsMock,
  planMessageAsTask: planMock,
  sendCabinetMessage: sendMock,
}));
vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ user: { id: "admin-1", role: "admin_cabinet" } }),
}));
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

const contact = {
  id: "user-1", nom_complet: "Fatima Radoui", email: "fatima@example.com",
  role: "collaborateur", is_active: true, unread_count: 1,
};
const message = {
  id: "message-1", sender_id: "user-1", recipient_id: "admin-1",
  sender_name: "Fatima Radoui", recipient_name: "Admin Cabinet",
  contenu: "Préparer la déclaration de TVA.", message_type: "chat" as const,
  read_at: null, task_id: null, created_at: "2026-08-29T09:00:00Z", is_mine: false,
};

describe("MessagesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Element.prototype.scrollIntoView = vi.fn();
    contactsMock.mockResolvedValue([contact]);
    conversationMock.mockResolvedValue([message]);
    sendMock.mockResolvedValue({ ...message, id: "message-2", is_mine: true });
    planMock.mockResolvedValue({
      id: "task-1", entreprise_id: null, entreprise_nom: null,
      cree_par: "admin-1", assignee_a: "user-1", assignee_nom: "Fatima Radoui",
      titre: "Préparer la TVA", description: message.contenu,
      date_echeance: "2026-09-01", heure_echeance: "14:30:00",
      statut: "a_faire", priorite: "haute", recurrence: "aucune",
      created_at: "2026-08-29T09:00:00Z", est_en_retard: false,
    });
  });

  it("envoie un message au contact sélectionné", async () => {
    const user = userEvent.setup();
    render(<MessagesPage />);
    await screen.findByText("Préparer la déclaration de TVA.");

    await user.type(screen.getByLabelText("Votre message"), "La tâche est prise en charge.");
    await user.click(screen.getByRole("button", { name: "Envoyer le message" }));

    await waitFor(() => expect(sendMock).toHaveBeenCalledWith("user-1", "La tâche est prise en charge."));
  });

  it("convertit un message en tâche avec une date et une heure", async () => {
    const user = userEvent.setup();
    render(<MessagesPage />);
    await screen.findByText("Préparer la déclaration de TVA.");
    await user.click(screen.getByRole("button", { name: "Planifier comme tâche" }));

    const dateInput = screen.getByLabelText("Date");
    const timeInput = screen.getByLabelText("Heure");
    await user.clear(dateInput);
    await user.type(dateInput, "2026-09-01");
    await user.clear(timeInput);
    await user.type(timeInput, "14:30");
    await user.click(screen.getByRole("button", { name: "Créer la tâche" }));

    await waitFor(() => expect(planMock).toHaveBeenCalledWith("message-1", expect.objectContaining({
      date_echeance: "2026-09-01",
      heure_echeance: "14:30",
    })));
    expect(await screen.findByText(/Tâche planifiée le/)).toBeInTheDocument();
  });
});
