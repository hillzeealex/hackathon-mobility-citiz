"""
Modèle « où Citiz s'installe » : LightGBM, classification par carreau -> data/processed/model/

    python -m src.model.train

Périmètre d'apprentissage : carreaux peuplés des EPCI où Citiz est présent (ailleurs, l'absence de station
reflète surtout l'absence de l'opérateur, pas un territoire défavorable).
Validation spatiale : un réseau régional Citiz entier est retiré à chaque pli (« leave-one-network-out ») ; chaque
carreau reçoit ainsi une prédiction faite SANS avoir vu son réseau (proba_oof).
Test à l'aveugle Grenoble : pli du réseau de Grenoble-Alpes-Métropole ; part des carreaux à station (et des stations)
dans le top 5 / 10 / 20 % des carreaux prédits, comparée à la baseline « densité seule » (densite_800m).
Sorties : predictions.parquet (tous les carreaux de métropole), validation.json, shap_importance.csv,
docs/figures/modele/*.png.
LIMITE : la cible est la présence actuelle de Citiz ; le modèle apprend où Citiz s'est installé, pas la demande pure.
"""
from __future__ import annotations

import json
import sys
import time

import lightgbm as lgb
import matplotlib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from src.common.config import ROOT
from src.model.features import FEATURES, model_path

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

PARAMS = dict(n_estimators=400, learning_rate=0.05, num_leaves=31, min_child_samples=100, subsample=0.8,
              subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=42, verbose=-1)
TOPS = (0.05, 0.10, 0.20)
GRENOBLE_EPCI = "200040715"
FIG = ROOT / "docs" / "figures" / "modele"


def capture(y: np.ndarray, score: np.ndarray, tops=TOPS) -> dict:
    """Part des positifs parmi les k % de carreaux les mieux notés (k = 5, 10, 20 %)."""
    order = np.argsort(-score, kind="stable")
    n = len(score)
    pos = y.sum()
    return {f"top_{int(t * 100)}pct": round(float(y[order[:max(1, int(round(t * n)))]].sum() / pos), 3) if pos else None
            for t in tops}


def scores(y: np.ndarray, p: np.ndarray) -> dict:
    ok = len(np.unique(y)) == 2
    return {"auc": round(float(roc_auc_score(y, p)), 3) if ok else None,
            "ap": round(float(average_precision_score(y, p)), 3) if ok else None,
            "taux_positifs": round(float(y.mean()), 4), **capture(y, p)}


def fit(X: pd.DataFrame, y: np.ndarray) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(**PARAMS).fit(X, y)


def station_capture(f_city: pd.DataFrame, score: np.ndarray, stations_xy: np.ndarray, tops=TOPS) -> dict:
    """Part des STATIONS dont le carreau (le plus proche) est dans le top k % des carreaux de la ville."""
    from scipy.spatial import cKDTree
    if len(stations_xy) == 0:
        return {}
    _, idx = cKDTree(f_city[["x", "y"]].to_numpy()).query(stations_xy)
    rank = pd.Series(score).rank(ascending=False, pct=True).to_numpy()
    return {f"top_{int(t * 100)}pct": round(float((rank[idx] <= t).mean()), 3) for t in tops}


def train() -> dict:
    t0 = time.time()
    f = pd.read_parquet(model_path("features.parquet"))
    scope = f[f["reseau_citiz"].notna()].reset_index(drop=True)
    X, y, groups = scope[FEATURES], scope["cible_citiz_400m"].to_numpy(), scope["reseau_citiz"].to_numpy()

    # 1. Validation spatiale : un réseau Citiz retiré à chaque pli
    oof = np.full(len(scope), np.nan)
    per_net = {}
    for net in np.unique(groups):
        test = groups == net
        m = fit(X[~test], y[~test])
        oof[test] = m.predict_proba(X[test])[:, 1]
        per_net[net] = {"carreaux": int(test.sum()), "positifs": int(y[test].sum()), **scores(y[test], oof[test])}
    base = scope["densite_800m"].to_numpy()
    val = {"perimetre": {"carreaux": len(scope), "positifs": int(y.sum()), "reseaux": len(per_net),
                         "epci": int(scope["code_epci"].nunique())},
           "modele_oof": scores(y, oof), "baseline_densite": scores(y, base), "par_reseau": per_net}
    # capture calculée DANS chaque EPCI puis moyennée (décision locale : où dans la ville ?)
    loc = scope.assign(oof=oof, base=base).groupby("code_epci")
    big = [k for k, g in loc if g["cible_citiz_400m"].sum() >= 5]
    val["capture_moyenne_par_epci"] = {
        "epci": len(big),
        "modele": {k: round(float(np.mean([capture(g["cible_citiz_400m"].to_numpy(), g["oof"].to_numpy())[k]
                                            for n, g in loc if n in big])), 3) for k in capture(np.array([1]), np.array([1.0]))},
        "baseline_densite": {k: round(float(np.mean([capture(g["cible_citiz_400m"].to_numpy(), g["base"].to_numpy())[k]
                                                      for n, g in loc if n in big])), 3) for k in capture(np.array([1]), np.array([1.0]))}}

    # 2. Test à l'aveugle Grenoble (prédictions du pli qui exclut son réseau)
    gre = (scope["code_epci"] == GRENOBLE_EPCI).to_numpy()
    if gre.any():
        g = scope[gre].reset_index(drop=True)
        import geopandas as gpd
        off = gpd.read_parquet(ROOT / "data" / "processed" / "grenoble" / "offer.parquet")
        st = off[(off["type"] == "citiz") & off["dans_zone"]]
        st_xy = np.column_stack([st.geometry.x, st.geometry.y])
        val["test_aveugle_grenoble"] = {
            "reseau_exclu": str(g["reseau_citiz"].iloc[0]), "carreaux": int(gre.sum()), "carreaux_a_station": int(y[gre].sum()),
            "stations": len(st),
            "modele": {"carreaux": scores(y[gre], oof[gre]), "stations": station_capture(g, oof[gre], st_xy)},
            "baseline_densite": {"carreaux": scores(y[gre], base[gre]), "stations": station_capture(g, base[gre], st_xy)}}

    # 3. Modèle final (tout le périmètre) : prédictions pour toute la métropole + SHAP
    final = fit(X, y)
    pred = f[["idcar_200m", "code_insee", "code_epci", "reseau_citiz", "x", "y", "pop_calee", "cible_citiz_400m"]].copy()
    pred["proba"] = final.predict_proba(f[FEATURES])[:, 1]
    pred["proba_oof"] = pred["idcar_200m"].map(pd.Series(oof, index=scope["idcar_200m"]))   # sans avoir vu son réseau
    pred.to_parquet(model_path("predictions.parquet"), index=False)

    import shap
    sample = X.sample(min(20_000, len(X)), random_state=0)
    sv = shap.TreeExplainer(final).shap_values(sample)
    sv = sv[1] if isinstance(sv, list) else sv
    imp = pd.DataFrame({"variable": FEATURES, "shap_moyen_abs": np.abs(sv).mean(axis=0),
                        "importance_gain": final.booster_.feature_importance("gain")})
    imp = imp.sort_values("shap_moyen_abs", ascending=False)
    imp.to_csv(model_path("shap_importance.csv"), index=False)
    FIG.mkdir(parents=True, exist_ok=True)
    plt.figure()
    shap.summary_plot(sv, sample, show=False, max_display=15)
    plt.title("Contribution des variables (SHAP) à la probabilité d'une station Citiz à 400 m", fontsize=9)
    plt.tight_layout()
    plt.savefig(FIG / "shap_beeswarm.png", dpi=110)
    plt.close("all")
    fig, ax = plt.subplots(figsize=(7, 5))
    top = imp.head(15).iloc[::-1]
    ax.barh(top["variable"], top["shap_moyen_abs"], color="#e6007e")
    ax.set_xlabel("|SHAP| moyen (log-odds)")
    ax.set_title("Importance des variables (SHAP)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "shap_importance.png", dpi=110)
    plt.close(fig)

    val["importance_shap_top5"] = imp.head(5)["variable"].tolist()
    val["duree_s"] = round(time.time() - t0)
    val["limite"] = ("La cible est la présence actuelle de Citiz : le modèle apprend où Citiz s'est installé "
                     "(et ses choix passés), pas la demande pure.")
    model_path("validation.json").write_text(json.dumps(val, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in val.items() if k != "par_reseau"}, indent=1, ensure_ascii=False))
    return val


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    train()
