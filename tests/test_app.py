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
    next(r for r in at.sidebar.radio if r.label == "Niveau d'analyse").set_value("Zoom agglomération").run()
    src = next(r for r in at.sidebar.radio if r.label == "Jeu de données")
    if "démonstration" not in src.value:
        src.set_value("Données de démonstration (factices)").run()
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


@pytest.mark.skipif(not (ROOT / "data" / "processed" / "national" / "app" / "epci.parquet").exists(),
                    reason="fichiers nationaux absents")
def test_national_view_all_controls():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert not at.exception, at.exception
    next(r for r in at.radio if r.label == "Échelle").set_value("EPCI").run()
    next(s for s in at.selectbox if s.label == "Indicateur").set_value("score_potentiel_citiz").run()
    assert not at.exception, at.exception
    for dep in ("38", "973", "974"):                      # métropole, sans Filosofi, DROM avec Filosofi
        next(s for s in at.selectbox if s.label == "Département").set_value(dep).run()
        next(r for r in at.radio if r.label == "Détail").set_value("Carreaux 200 m (≥ 11 ménages)").run()
        assert not at.exception, (dep, at.exception)
