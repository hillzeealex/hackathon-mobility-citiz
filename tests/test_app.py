"""L'application s'exécute sans erreur sur les données RÉELLES (France, Nantes avec recommandations, Grenoble)."""
import pytest
from streamlit.testing.v1 import AppTest

from app.data import ROOT, available, city_folder, has_reco

APP = str(ROOT / "app" / "app.py")
NANTES = "Nantes Métropole (recommandations)"
GRENOBLE = "Grenoble (ville exemple)"


def start(view: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    next(r for r in at.sidebar.radio if r.label == "Vue").set_value(view).run()
    return at


@pytest.mark.skipif(not (available(city_folder("nantes")) and has_reco(city_folder("nantes"))),
                    reason="données de Nantes absentes (python -m scripts.build_all --ville nantes)")
def test_nantes_all_tabs_greedy_then_ilp():
    at = start(NANTES)
    assert not at.exception, at.exception
    assert len(at.tabs) == 5
    assert not any("FACTICES" in w.value for w in at.warning)
    labels = [m.label for m in at.metric]
    assert "Habitants gagnés" in labels and "CO₂ évité (prudent)" in labels
    assert at.dataframe, "liste priorisée absente"
    next(r for r in at.radio if r.label == "Méthode").set_value("ilp").run()
    at.select_slider(key="budget").set_value(1_000_000).run()
    at.select_slider(key="equity").set_value(2.0).run()
    next(r for r in at.radio if r.label == "Échelle").set_value("Carreaux 200 m").run()
    next(r for r in at.radio if r.label == "Indicateur").set_value("Options pour 1 000 habitants (2SFCA)").run()
    assert not at.exception, at.exception


@pytest.mark.skipif(not available(city_folder("grenoble")), reason="données de Grenoble absentes")
def test_grenoble_map_and_validation():
    at = start(GRENOBLE)
    assert not at.exception, at.exception
    assert any("Nantes" in i.value for i in at.info)       # pas de recommandations à Grenoble
    assert at.dataframe                                    # tableaux de validation / population desservie


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


def metric(at: AppTest, label: str) -> str:
    return next(m.value for m in at.metric if m.label == label)


@pytest.mark.skipif(not (available(city_folder("nantes")) and has_reco(city_folder("nantes"))),
                    reason="données de Nantes absentes (python -m scripts.build_all --ville nantes)")
def test_nantes_demo_button_and_precomputed_matches_live():
    at = start(NANTES)
    pre = metric(at, "Habitants gagnés")      # 500 000 € : scénario précalculé
    assert any("précalculé" in c.value for c in at.caption)
    at.select_slider(key="equity").set_value(0.6).run()                             # autre équité : calcul en direct
    assert any("calculé en direct" in c.value for c in at.caption)
    at.select_slider(key="equity").set_value(0.5).run()
    at.select_slider(key="budget").set_value(750_000).run()
    next(b for b in at.sidebar.button if "Scénario démo" in b.label).click().run()
    assert at.select_slider(key="budget").value == 500_000 and metric(at, "Stations Citiz recommandées") == "12"
    assert metric(at, "Habitants gagnés") == pre
    assert not at.exception, at.exception
