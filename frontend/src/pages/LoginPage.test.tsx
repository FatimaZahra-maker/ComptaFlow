import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "./LoginPage";

const { loginMock, navigateMock, requestAccessMock, setTokenMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  navigateMock: vi.fn(),
  requestAccessMock: vi.fn(),
  setTokenMock: vi.fn(),
}));

vi.mock("../api/authApi", () => ({ login: loginMock }));
vi.mock("../api/messagesApi", () => ({ requestAccessRenewal: requestAccessMock }));
vi.mock("../context/AuthContext", () => ({
  useAuth: () => ({ setToken: setTokenMock }),
}));
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => navigateMock };
});

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loginMock.mockResolvedValue({ access_token: "test-token", token_type: "bearer" });
    requestAccessMock.mockResolvedValue("L’administrateur a reçu votre demande.");
    setTokenMock.mockResolvedValue(undefined);
  });

  it("affiche et masque le mot de passe", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);
    const password = screen.getByLabelText("Mot de passe") as HTMLInputElement;

    expect(password.type).toBe("password");
    await user.click(screen.getByRole("button", { name: "Afficher le mot de passe" }));
    expect(password.type).toBe("text");
    await user.click(screen.getByRole("button", { name: "Masquer le mot de passe" }));
    expect(password.type).toBe("password");
  });

  it("explique la procédure de récupération avec l'adresse saisie", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Adresse e-mail"), "fatima@example.test");
    await user.click(screen.getByRole("button", { name: /mot de passe oublié/i }));
    await user.type(screen.getByLabelText("Message pour l’administrateur"), "Merci de renouveler mon accès.");
    await user.click(screen.getByRole("button", { name: "Envoyer la demande à l’administrateur" }));

    await waitFor(() => expect(requestAccessMock).toHaveBeenCalledWith(
      "fatima@example.test",
      "Merci de renouveler mon accès.",
    ));
    expect(screen.getByRole("status")).toHaveTextContent("L’administrateur a reçu votre demande.");
  });

  it("connecte et conserve le jeton lorsque la mémorisation est cochée", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Adresse e-mail"), "fatima@example.test");
    await user.type(screen.getByLabelText("Mot de passe"), "mot-de-passe-test");
    await user.click(screen.getByRole("checkbox", { name: "Se souvenir de moi" }));
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(loginMock).toHaveBeenCalledWith({
      email: "fatima@example.test",
      password: "mot-de-passe-test",
    }));
    expect(setTokenMock).toHaveBeenCalledWith("test-token", true);
    expect(navigateMock).toHaveBeenCalledWith("/accueil", { replace: true });
  });

  it("utilise une session temporaire lorsque la mémorisation n'est pas cochée", async () => {
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Adresse e-mail"), "fatima@example.test");
    await user.type(screen.getByLabelText("Mot de passe"), "mot-de-passe-test");
    await user.click(screen.getByRole("button", { name: "Se connecter" }));

    await waitFor(() => expect(setTokenMock).toHaveBeenCalledWith("test-token", false));
  });
});
