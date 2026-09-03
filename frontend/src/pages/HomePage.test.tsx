import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { HomePage } from "./HomePage";

const { chronosMock, navigateMock } = vi.hoisted(() => ({ chronosMock: vi.fn(), navigateMock: vi.fn() }));
vi.mock("../api/chronosApi", () => ({ listChronoDocuments: chronosMock }));
vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ user: { prenom: "Admin", nom: "Admin", email: "admin@example.test", role: "admin_cabinet" } }) }));
vi.mock("react-router-dom", async () => ({ ...(await vi.importActual<typeof import("react-router-dom")>("react-router-dom")), useNavigate: () => navigateMock }));

describe("HomePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    chronosMock.mockResolvedValue([
      { id: "1", entreprise_id: null, entreprise_nom: null, statut: "traite", statut_validation: null },
      { id: "2", entreprise_id: "e1", entreprise_nom: "ANZOBAT", statut: "traite", statut_validation: "a_verifier" },
    ]);
  });

  it("présente les deux parcours et les compteurs", async () => {
    render(<HomePage />);
    expect(screen.getByText(/Importer/)).toBeInTheDocument();
    expect(screen.getByText(/Travailler sur/)).toBeInTheDocument();
    expect(screen.getByRole("tooltip")).toHaveTextContent("Accédez au dossier d’une entreprise");
    await waitFor(() => expect(screen.getByText("Documents à identifier").parentElement).toHaveTextContent("1"));
  });

  it("ouvre la sélection d’entreprise", async () => {
    render(<HomePage />);
    await userEvent.click(screen.getByRole("button", { name: /Travailler sur/ }));
    expect(navigateMock).toHaveBeenCalledWith("/entreprises/selection");
  });
});
