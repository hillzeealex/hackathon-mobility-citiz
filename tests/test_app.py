"""L'application s'exécute sans erreur sur les données de démonstration (tous les onglets, glouton et ILP)."""
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

from app.data import DEMO, ROOT, available

APP = str(ROOT / "app" / "app.py")


@pytest.fixture(scope="module", autouse=True)
def demo_data():
    if not available(DEMO):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_demo_data.py")], check=True)


def start() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    if at.sidebar.radio and "démonstration" not in at.sidebar.radio[0].value:
        at.sidebar.radio[0].set_value("Données de démonstration (factices)").run()
    return at


def test_all_tabs_render_with_greedy():
    at = start()
    assert not at.exception, at.exception
    assert len(at.tabs) == 4
    labels = [m.label for m in at.metric]
    assert "Habitants nouvellement desservis" in labels and "CO₂ évité (estimation prudente)" in labels
    assert at.dataframe, "liste priorisée absente"


def test_ilp_and_controls():
    at = start()
    method = next(r for r in at.radio if r.label == "Méthode")
    method.set_value("ilp").run()
    assert not at.exception, at.exception
    at.slider[0].set_value(1_000_000).run()                 # budget
    at.slider[1].set_value(2.0).run()                       # équité
    assert not at.exception, at.exception
    scale = next(r for r in at.radio if r.label == "Échelle")
    scale.set_value("Carreaux 200 m").run()
    assert not at.exception, at.exception
