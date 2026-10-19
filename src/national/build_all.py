"""
Niveau 1 (France entière) : chaîne complète, des données brutes aux fichiers de l'application.

    python -m src.national.build_all

Prérequis : python src/ingest/download_all.py --only citiz gbfs gtfs stops_national insee securite ign
Durée mesurée (i5-1135G7, 8 Go) : ≈ 5 min ; pic mémoire ≈ 1,6 Go (détail : data/processed/national/mesures.json).
"""
from __future__ import annotations

import sys
import time

from src.national import access, app_files, cells, offer, ranking


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    t0 = time.perf_counter()
    for name, step in (("carreaux", cells.build_cells), ("offre", offer.build_offer),
                       ("accessibilité V1", access.build_access), ("agrégats", access.build_aggregates),
                       ("classement EPCI", ranking.build_ranking), ("fichiers appli", app_files.build_app_files)):
        print(f"\n=== {name} ===", flush=True)
        step()
    print(f"\nNiveau 1 terminé en {(time.perf_counter() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
