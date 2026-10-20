"""
Commande unique : reconstruit tout le zoom d'une ville, des données brutes aux sorties.

    python -m scripts.build_all --ville nantes
    python -m scripts.build_all --ville grenoble --sans-v2      # V1 seulement
    python -m scripts.build_all --ville nantes --v2             # force la V2 (extrait OSM de la région requis)

Étapes : zone -> population calée -> offre (GTFS de la ville, GBFS) -> accessibilité V1 [+ V2].
Sorties : data/processed/<ville>/ ; cartes : docs/figures/<ville>/.
Prérequis : données brutes (docs/RECUPERER_LES_DONNEES.md). Le niveau France entière se reconstruit à part :
python -m src.national.build_all.
"""
from __future__ import annotations

import argparse
import sys
import time

from src.common.config import cities, load_settings, set_city, study_area


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ville", required=True, choices=cities())
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--v2", dest="v2", action="store_true", default=None, help="calcule la V2 (réseau piéton)")
    g.add_argument("--sans-v2", dest="v2", action="store_false", help="V1 seulement")
    a = ap.parse_args(argv)
    set_city(a.ville)
    with_v2 = study_area().get("v2", False) if a.v2 is None else a.v2

    from src.features.build_access import build_access
    from src.ingest.offer import build_offer
    from src.ingest.population import build_population
    from src.ingest.zone import build_zone

    steps = [("zone", build_zone), ("population", build_population), ("offre", build_offer),
             (f"accessibilité V1{' + V2' if with_v2 else ''}", lambda: build_access(with_v2=with_v2))]
    t_all = time.perf_counter()
    print(f"=== {study_area()['name']} ({a.ville}) · jour type GTFS {load_settings()['offer']['typical_weekday']} ===",
          flush=True)
    for name, step in steps:
        t0 = time.perf_counter()
        print(f"\n--- {name} ---", flush=True)
        step()
        print(f"--- {name} : {time.perf_counter() - t0:.0f} s", flush=True)
    print(f"\n{a.ville} reconstruite en {time.perf_counter() - t_all:.0f} s -> data/processed/{a.ville}/")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
