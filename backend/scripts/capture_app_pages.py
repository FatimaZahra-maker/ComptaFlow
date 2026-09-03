"""Audit visuel local des routes React et captures destinées au rapport.

Ce script ne connaît aucun mot de passe : il crée un jeton local temporaire
pour un administrateur actif de la base de développement, pilote Chrome via
son protocole DevTools, puis ferme le profil navigateur éphémère.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket
from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.enums import RoleEnum
from app.models.user import User


ROOT = Path(__file__).resolve().parents[2]
CAPTURES = ROOT / "captures"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
BASE_URL = "http://localhost:5173"
PORT = 9231

ROUTES = (
    "/accueil", "/entreprises/selection", "/dashboard", "/upload", "/chronos", "/achats", "/ventes",
    "/banque", "/comptes-bancaires", "/registers", "/registres",
    "/tva-mensuelle", "/grand-livre", "/balance", "/cpc", "/bilan",
    "/cloture", "/controles", "/rappels", "/messagerie",
    "/notifications", "/rapports", "/admin/utilisateurs",
    "/admin/historique", "/assistant",
)

SCREENSHOTS = {
    "/accueil": "accueil_parcours_principal.png",
    "/entreprises/selection": "selection_entreprise.png",
    "/rappels": "taches_planification.png",
    "/tva-mensuelle": "tva_preparation_topaze.png",
    "/admin/historique": "historique_audit.png",
    "/assistant": "assistant_comptaflow.png",
}


class DevTools:
    def __init__(self, endpoint: str) -> None:
        self.ws = websocket.create_connection(endpoint, timeout=20)
        self.sequence = 0

    def command(self, method: str, params: dict | None = None) -> dict:
        self.sequence += 1
        identifier = self.sequence
        self.ws.send(json.dumps({"id": identifier, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.ws.recv())
            if response.get("id") == identifier:
                if "error" in response:
                    raise RuntimeError(f"DevTools {method}: {response['error']}")
                return response.get("result", {})

    def close(self) -> None:
        self.ws.close()


def _temporary_admin_token() -> str:
    with SessionLocal() as db:
        users = list(db.execute(select(User).where(User.is_active.is_(True))).scalars())
        preferred = (RoleEnum.ADMIN_CABINET, RoleEnum.SUPER_ADMIN)
        user = next((item for role in preferred for item in users if item.role == role), None)
        if user is None:
            raise RuntimeError("Aucun administrateur actif n'est disponible pour l'audit local.")
        return create_access_token({"sub": str(user.id)})


def _wait_debugger() -> list[dict]:
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=1) as response:
                return json.load(response)
        except OSError:
            time.sleep(0.25)
    raise RuntimeError("Chrome DevTools n'a pas démarré.")


def _body_text(devtools: DevTools) -> str:
    result = devtools.command(
        "Runtime.evaluate",
        {"expression": "document.body ? document.body.innerText : ''", "returnByValue": True},
    )
    return str(result.get("result", {}).get("value", ""))


def main() -> int:
    if not CHROME.exists():
        raise RuntimeError(f"Chrome introuvable : {CHROME}")
    CAPTURES.mkdir(exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="comptaflow_visual_audit_"))
    process = subprocess.Popen(
        [
            str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars",
            "--remote-allow-origins=*", f"--remote-debugging-port={PORT}",
            f"--user-data-dir={profile}", "--window-size=1440,1000", "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    devtools: DevTools | None = None
    try:
        pages = _wait_debugger()
        page = next(item for item in pages if item.get("type") == "page")
        devtools = DevTools(page["webSocketDebuggerUrl"])
        devtools.command("Page.enable")
        devtools.command("Runtime.enable")
        devtools.command("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
        })
        devtools.command("Page.navigate", {"url": f"{BASE_URL}/login"})
        time.sleep(1.5)
        token = json.dumps(_temporary_admin_token())
        devtools.command("Runtime.evaluate", {
            "expression": f"localStorage.setItem('comptaflow_token', {token})",
        })

        failures: list[str] = []
        for route in ROUTES:
            devtools.command("Page.navigate", {"url": f"{BASE_URL}{route}"})
            time.sleep(1.4)
            body = _body_text(devtools)
            if "Backend inaccessible" in body or len(body.strip()) < 20:
                # Un rechargement Uvicorn/Vite peut couper une requête pendant
                # quelques millisecondes en développement. Un second essai
                # distingue ce cas transitoire d'une page réellement cassée.
                time.sleep(1.0)
                devtools.command("Page.navigate", {"url": f"{BASE_URL}{route}"})
                time.sleep(2.0)
                body = _body_text(devtools)
            if len(body.strip()) < 20:
                failures.append(f"{route}: contenu vide")
            if "Backend inaccessible" in body:
                failures.append(f"{route}: backend inaccessible")
            if route in SCREENSHOTS:
                # Les états comptables peuvent nécessiter un second aller-retour
                # API. La capture doit représenter le résultat, pas le squelette
                # de chargement, et toujours commencer en haut de la page.
                time.sleep(1.6)
                devtools.command("Runtime.evaluate", {"expression": "window.scrollTo(0, 0)"})
                time.sleep(0.2)
                result = devtools.command("Page.captureScreenshot", {
                    "format": "png", "captureBeyondViewport": False,
                })
                (CAPTURES / SCREENSHOTS[route]).write_bytes(base64.b64decode(result["data"]))
                if route == "/accueil":
                    devtools.command("Runtime.evaluate", {
                        "expression": "document.querySelector('[aria-describedby=company-card-description]')?.focus()",
                    })
                    time.sleep(0.3)
                    focused = devtools.command("Page.captureScreenshot", {
                        "format": "png", "captureBeyondViewport": False,
                    })
                    (CAPTURES / "accueil_focus_entreprise.png").write_bytes(
                        base64.b64decode(focused["data"])
                    )
            print(f"OK {route} ({len(body)} caractères)")

        if failures:
            print("ÉCHECS VISUELS")
            for failure in failures:
                print(f"- {failure}")
            return 1
        print(f"AUDIT VISUEL OK — {len(ROUTES)} routes, {len(SCREENSHOTS)} captures")
        return 0
    finally:
        if devtools is not None:
            devtools.close()
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
