import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "./DashboardPage";

const { getDashboardMock, navigateMock } = vi.hoisted(() => ({
  getDashboardMock: vi.fn(),
  navigateMock: vi.fn(),
}));

vi.mock("../api/dashboardApi", () => ({ getDashboard: getDashboardMock }));
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

const dashboard = {
  total_documents: 8,
  documents_par_statut: {
    en_attente: 1, en_traitement: 1, traite: 2, valide: 4, erreur: 0,
  },
  total_ecritures: 15,
  ecritures_par_statut: {
    calcul_en_cours: 1,
    brouillon: 2,
    a_verifier: 3,
    prete_topaze: 4,
    saisie_topaze: 5,
    valide: 0,
    rejete: 0,
  },
  tva_collectee: "120.00",
  tva_deductible: "45.00",
  tva_nette: "75.00",
  total_entreprises: 2,
};

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getDashboardMock.mockResolvedValue(dashboard);
  });

  it("charge toutes les périodes par défaut et affiche les nouveaux statuts", async () => {
    render(<DashboardPage />);

    await waitFor(() => expect(getDashboardMock).toHaveBeenCalledWith(undefined, null));
    expect(await screen.findByText("Prêtes pour Topaze")).toBeInTheDocument();
    expect(screen.getByText("Saisies dans Topaze")).toBeInTheDocument();
    expect(screen.getByText("Calcul en cours")).toBeInTheDocument();
    expect(screen.getByText("75.00 MAD")).toBeInTheDocument();
  });

  it("recharge les indicateurs lorsqu'un mois est choisi", async () => {
    render(<DashboardPage />);
    await waitFor(() => expect(getDashboardMock).toHaveBeenCalledWith(undefined, null));

    fireEvent.change(screen.getByLabelText("Filtrer le tableau de bord par mois"), {
      target: { value: "2026-07" },
    });

    await waitFor(() => expect(getDashboardMock).toHaveBeenLastCalledWith("2026-07", null));
  });
});
