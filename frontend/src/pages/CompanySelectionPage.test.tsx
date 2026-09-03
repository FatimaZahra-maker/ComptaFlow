import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CompanySelectionPage } from "./CompanySelectionPage";

const { companiesMock, navigateMock } = vi.hoisted(() => ({ companiesMock: vi.fn(), navigateMock: vi.fn() }));
vi.mock("../api/entreprisesApi", () => ({ listEntreprises: companiesMock }));
vi.mock("react-router-dom", async () => ({ ...(await vi.importActual<typeof import("react-router-dom")>("react-router-dom")), useNavigate: () => navigateMock }));

describe("CompanySelectionPage", () => {
  beforeEach(() => {
    vi.clearAllMocks(); localStorage.clear();
    companiesMock.mockResolvedValue([
      { id: "company-1", nom: "ANZOBAT SARL", ice: "001122", identifiant_fiscal: "445566", rc: "7788", is_active: true, creee_automatiquement: false },
      { id: "placeholder", nom: "Entreprise à identifier", ice: null, identifiant_fiscal: null, rc: null, is_active: true, creee_automatiquement: true },
    ]);
  });

  it("recherche et sélectionne uniquement une entreprise confirmée", async () => {
    render(<CompanySelectionPage />);
    const search = screen.getByPlaceholderText(/ANZO/);
    await waitFor(() => expect(screen.getByText("ANZOBAT SARL")).toBeInTheDocument());
    expect(screen.queryByText("Entreprise à identifier")).not.toBeInTheDocument();
    await userEvent.type(search, "ANZO");
    await userEvent.click(screen.getByRole("button", { name: /ANZOBAT SARL/ }));
    expect(localStorage.getItem("comptaflow_active_entreprise_id")).toBe("company-1");
    expect(navigateMock).toHaveBeenCalledWith("/dashboard?entreprise_id=company-1");
  });
});
