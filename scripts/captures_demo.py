"""
Captures de secours de l'application (plan B de la démo) : une image par vue et par onglet -> slides/img/demo/.

    pip install playwright            # une fois ; aucun navigateur n'est téléchargé (Chromium déjà présent)
    python -m scripts.captures_demo [--hors-ligne] [--sortie DOSSIER]

Lance l'appli (serveur Streamlit sans fenêtre, port 8599), mesure le temps jusqu'au premier affichage, puis
parcourt le scénario de docs/DEMO.md. Navigateur : variable CHROMIUM, sinon le Chromium de Playwright
(%LOCALAPPDATA%/ms-playwright), sinon Chrome ou Edge installés.
--hors-ligne : bloque tout accès Internet du navigateur (fonds de carte) pour vérifier que l'appli reste lisible.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = 8599
URL = f"http://localhost:{PORT}"
NANTES, GRENOBLE = "Nantes Métropole (recommandations)", "Grenoble (ville exemple)"


def chromium() -> str | None:
    if os.environ.get("CHROMIUM"):
        return os.environ["CHROMIUM"]
    pw = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    found = sorted(pw.glob("chromium-*/chrome-win*/chrome.exe"), reverse=True)
    for p in [*found, Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
              Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")]:
        if p.exists():
            return str(p)
    return None


def wait_server(timeout: float = 60) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(f"{URL}/_stcore/health", timeout=1)
            return
        except OSError:
            time.sleep(0.3)
    raise RuntimeError("le serveur Streamlit ne répond pas")


def idle(page, settle: float = 1.5) -> None:
    """Attend la fin de l'exécution du script Streamlit, puis le rendu des cartes."""
    page.wait_for_timeout(300)
    page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=120_000)
    page.wait_for_timeout(settle * 1000)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hors-ligne", action="store_true")
    ap.add_argument("--sortie", type=Path, default=ROOT / "slides" / "img" / "demo")
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright

    out = a.sortie
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    server = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app" / "app.py"),
                               "--server.port", str(PORT), "--server.headless", "true"],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        wait_server()
        print(f"serveur prêt : {time.perf_counter() - t0:.1f} s", flush=True)
        with sync_playwright() as p:
            exe = chromium()
            browser = p.chromium.launch(executable_path=exe) if exe else p.chromium.launch()
            page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1, locale="fr-FR")
            if a.hors_ligne:
                page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
            page.goto(URL)
            page.get_by_text("France entière · mobilité").wait_for(timeout=120_000)
            idle(page, 1)
            print(f"démarrage (serveur + première page) : {time.perf_counter() - t0:.1f} s", flush=True)
            page.wait_for_timeout(6000)                       # carte nationale : GeoJSON des départements

            def shot(name: str) -> None:
                page.evaluate("document.activeElement && document.activeElement.blur()")
                page.mouse.move(1590, 990)                    # pas d'infobulle ouverte sur la capture
                page.wait_for_timeout(400)
                page.screenshot(path=str(out / f"{name}.png"))
                print("  ->", out / f"{name}.png", flush=True)

            def tab(label: str) -> None:
                page.get_by_role("tab", name=label).click()
                idle(page, 3)

            def view(label: str) -> None:
                t = time.perf_counter()
                page.locator('[data-testid="stSidebar"]').get_by_text(label, exact=True).click()
                idle(page, 3)
                print(f"vue {label} : {time.perf_counter() - t:.1f} s", flush=True)

            shot("01_france")
            view(NANTES)
            shot("02_nantes_carte_acces")
            tab("2 · Offre et population desservie")
            shot("03_nantes_offre_desservie")
            tab("3 · Où investir ?")
            page.locator('[data-testid="stSidebar"]').get_by_role("button", name="Scénario démo").click()
            idle(page, 3)
            shot("04_nantes_ou_investir_500k")
            thumb = page.get_by_role("slider").first          # budget
            thumb.focus()
            for _ in range(10):                               # 500 000 € -> 1 000 000 € par pas de 50 000 €
                thumb.press("ArrowRight")
            idle(page, 3)
            shot("05_nantes_ou_investir_1M")
            page.get_by_text("Liste priorisée", exact=True).scroll_into_view_if_needed()
            idle(page, 1)
            shot("06_nantes_liste_priorisee")
            page.locator('[data-testid="stSidebar"]').get_by_role("button", name="Scénario démo").click()
            idle(page, 1)
            tab("4 · Validation")
            shot("07_validation")
            page.get_by_text("Validation par réseau", exact=False).first.scroll_into_view_if_needed()
            idle(page, 1)
            shot("08_validation_reseaux_shap")
            tab("5 · Méthode et limites")
            shot("09_methode")
            page.get_by_text("Pourquoi une station recommandée").first.scroll_into_view_if_needed()
            idle(page, 1)
            shot("10_methode_limites")
            view(GRENOBLE)
            tab("1 · Carte d'accès")
            shot("11_grenoble_carte_acces")
            browser.close()
    finally:
        server.terminate()
    print(f"captures dans {out} ({time.perf_counter() - t0:.0f} s)")


if __name__ == "__main__":
    main()
