"""
Comparatif des agglomérations candidates (docs/choix_ville.md) : présence Citiz, population et
exposition au vol / à la dégradation de véhicules (SSMSI, délinquance enregistrée par commune).

    python scripts/compare_cities.py

Taux pour 1 000 habitants par EPCI = Σ faits / Σ population × 1 000 (communes de l'EPCI, ADMIN EXPRESS 2026).
Exposition Citiz = moyenne des taux communaux pondérée par le nombre de stations Citiz de chaque commune.
Communes non diffusées par le SSMSI (« ndiff », petits effectifs) : estimation `complement_info_nombre` du SSMSI.
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.config import processed, raw  # noqa: E402
from src.ingest.archives import ign_gpkg  # noqa: E402

CANDIDATES = {"200040715": "Grenoble", "246700488": "Strasbourg", "243100518": "Toulouse",
              "200046977": "Lyon", "243300316": "Bordeaux"}
INDICATORS = {"Vols de véhicule": "vols_vehicule", "Vols dans les véhicules": "vols_dans_vehicule",
              "Vols d'accessoires sur véhicules": "vols_accessoires",
              "Destructions et dégradations volontaires": "degradations"}
YEARS = (2023, 2024, 2025)


def communes_by_epci() -> pd.DataFrame:
    c = gpd.read_file(ign_gpkg("admin_express"), layer="commune", columns=["code_insee", "codes_siren_des_epci"],
                      read_geometry=False)
    c["code_epci"] = c["codes_siren_des_epci"].fillna("").str.split(r"[/,; ]+")
    c = c.explode("code_epci")
    return c[c["code_epci"].isin(CANDIDATES)][["code_insee", "code_epci"]]


def crime(communes: pd.DataFrame) -> pd.DataFrame:
    d = pd.read_parquet(raw("securite", "delinquance_communale_2025.parquet"),
                        columns=["CODGEO_2026", "annee", "indicateur", "nombre", "est_diffuse", "insee_pop",
                                 "complement_info_nombre"])
    d = d[d["annee"].isin(YEARS) & d["indicateur"].isin(INDICATORS) & d["CODGEO_2026"].isin(communes["code_insee"])]
    d = d.assign(indicateur=d["indicateur"].astype(str).map(INDICATORS),
                 faits=d["nombre"].fillna(d["complement_info_nombre"]).fillna(0),
                 estime=d["est_diffuse"].eq("ndiff"))
    return d.merge(communes, left_on="CODGEO_2026", right_on="code_insee")


def main() -> pd.DataFrame:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    communes = communes_by_epci()
    d = crime(communes)
    stations = pd.read_csv(processed("citiz_stations.csv"), dtype=str)
    st_by_com = stations.groupby("code_insee").size().rename("stations")

    rows = []
    for epci, name in CANDIDATES.items():
        e = d[d["code_epci"] == epci]
        pop25 = e[(e.annee == 2025)].drop_duplicates("code_insee")["insee_pop"].sum()
        r = {"ville": name, "code_epci": epci, "population_ssmsi_2025": int(pop25),
             "part_faits_estimes_2025": round(float(e[(e.annee == 2025) & e.estime]["faits"].sum()
                                                    / max(1, e[e.annee == 2025]["faits"].sum())), 3)}
        for ind in INDICATORS.values():
            x = e[e.indicateur == ind]
            for label, years in (("2025", (2025,)), ("2023_2025", YEARS)):
                xs = x[x.annee.isin(years)]
                pop = xs.drop_duplicates(["code_insee", "annee"])["insee_pop"].sum()
                r[f"{ind}_{label}"] = round(1000 * xs["faits"].sum() / pop, 2)
            # exposition au droit des stations Citiz (taux communal 2023-2025 pondéré par les stations)
            xc = x.groupby("code_insee").apply(lambda g: 1000 * g.faits.sum() / g.drop_duplicates("annee").insee_pop.sum(),
                                               include_groups=False).rename("taux")
            w = st_by_com.reindex(xc.index).fillna(0)
            r[f"{ind}_expo_citiz"] = round(float((xc * w).sum() / w.sum()), 2) if w.sum() else None
        r["vols_total_vehicule_2023_2025"] = round(sum(r[f"{k}_2023_2025"] for k in ("vols_vehicule", "vols_dans_vehicule", "vols_accessoires")), 2)
        r["vols_total_expo_citiz"] = round(sum(r[f"{k}_expo_citiz"] for k in ("vols_vehicule", "vols_dans_vehicule", "vols_accessoires")), 2)
        rows.append(r)
    out = pd.DataFrame(rows)
    out.to_csv(processed("comparatif_villes_securite.csv"), index=False)
    cols = ["ville", "vols_vehicule_2023_2025", "vols_dans_vehicule_2023_2025", "vols_accessoires_2023_2025",
            "vols_total_vehicule_2023_2025", "degradations_2023_2025", "vols_total_expo_citiz", "degradations_expo_citiz",
            "vols_vehicule_2025", "degradations_2025", "part_faits_estimes_2025"]
    print(out[cols].to_string(index=False))
    return out


if __name__ == "__main__":
    main()
