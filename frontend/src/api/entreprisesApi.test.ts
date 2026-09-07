import { beforeEach, describe, expect, it, vi } from "vitest";

const getMock = vi.hoisted(() => vi.fn());
vi.mock("./client", () => ({ apiClient: { get: getMock } }));

import { listAvailableEntreprises } from "./entreprisesApi";

describe("listAvailableEntreprises", () => {
  beforeEach(() => getMock.mockReset());

  it("propose aussi les entreprises gérées sans données et exclut les dossiers OCR", async () => {
    getMock.mockImplementation((url?: string) => Promise.resolve({ data: url?.endsWith("/available")
      ? [{ id: "with-data", nom: "SEGURIBAT", ice: null, identifiant_fiscal: null, rc: null, is_active: true, creee_automatiquement: false, ecritures_validees: 2 }]
      : [
          { id: "empty", nom: "ANZOBAT", ice: null, identifiant_fiscal: null, rc: null, is_active: true, creee_automatiquement: false },
          { id: "with-data", nom: "SEGURIBAT", ice: null, identifiant_fiscal: null, rc: null, is_active: true, creee_automatiquement: false },
          { id: "ocr", nom: "Entreprise à identifier", ice: null, identifiant_fiscal: null, rc: null, is_active: true, creee_automatiquement: true },
          { id: "inactive", nom: "Ancienne société", ice: null, identifiant_fiscal: null, rc: null, is_active: false, creee_automatiquement: false },
        ] }));

    const result = await listAvailableEntreprises("banque");

    expect(result.map((item) => item.id)).toEqual(["empty", "with-data"]);
    expect(result.find((item) => item.id === "with-data")?.ecritures_validees).toBe(2);
    expect(getMock).toHaveBeenCalledTimes(2);
  });
});
