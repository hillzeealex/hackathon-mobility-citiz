#!/usr/bin/env python3
"""
Hackathon Mobility (Epitech x Citiz) - téléchargement de TOUTES les données ouvertes du sujet.

Uniquement la bibliothèque standard Python (3.9+) : aucune installation requise.

Usage :
    python download_all.py                      # tout télécharger (≈ 8-10 Go avec OSM France)
    python download_all.py --osm region --osm-region grand-est   # OSM d'une seule région (plus léger)
    python download_all.py --only citiz gbfs insee               # seulement certaines catégories
    python download_all.py --gtfs-filter strasbourg lyon         # GTFS filtrés par mot-clé
    python download_all.py --list                                # affiche les catégories

Le script reprend là où il s'est arrêté : un fichier déjà téléchargé n'est pas re-téléchargé.
Il génère aussi data/raw/manifest.csv et docs/sources.md (livrable demandé par le sujet).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import json
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UA = "Mozilla/5.0 (hackathon-mobility-epitech data downloader)"
TDG_API = "https://transport.data.gouv.fr/api/datasets"

# --------------------------------------------------------------------------------------
# Sources statiques (liens directs vérifiés le 19/10/2026)
# --------------------------------------------------------------------------------------
STATIC = {
    "stops_national": [
        ("Arrêts de transport en France (agrégat national GTFS, non dédoublonné) - data.gouv.fr",
         "https://www.data.gouv.fr/api/1/datasets/r/69cf54c6-6591-4920-b1d6-2a5292964606",
         "stops_national/arrets_transport_france.csv"),
    ],
    "gbfs_catalog": [
        ("Catalogue mondial des flux GBFS - MobilityData",
         "https://raw.githubusercontent.com/MobilityData/gbfs/master/systems.csv",
         "gbfs_catalog/systems.csv"),
    ],
    "insee": [
        ("INSEE Filosofi 2021 - population et revenus par carreau de 200 m (GeoPackage)",
         "https://www.insee.fr/fr/statistiques/fichier/8735162/Filosofi2021_carreaux_200m_gpkg.zip",
         "insee/filosofi2021_carreaux_200m_gpkg.zip"),
        ("INSEE Omphale - projections de population 2021-2070 par département et région (tous scénarios)",
         "https://www.insee.fr/fr/statistiques/fichier/6652134/projdepreg_2021-2070_excel.zip",
         "insee/projections_omphale_2021_2070.zip"),
        ("INSEE Recensement 2023 - Logement par IRIS (dont motorisation des ménages) - France hors Mayotte",
         "https://www.insee.fr/fr/statistiques/fichier/9061333/base_ic_logement_2023_xlsx.zip",
         "insee/base_ic_logement_2023_iris.zip"),
        ("INSEE Recensement 2023 - Logement par IRIS, DOM (Parquet)",
         "https://api.insee.fr/melodi/file/DS_RP_LOGEMENT_DOM_PRINC_IRIS_2023/PARQUET",
         "insee/logement_dom_iris_2023.parquet"),
        ("INSEE BPE 2025 - équipements géolocalisés (commerces, santé, écoles...)",
         "https://www.insee.fr/fr/statistiques/fichier/8217525/BPE25.parquet",
         "insee/bpe25.parquet"),
    ],
}

# Collections IGN (flux Atom data.geopf.fr) : le script choisit la dernière édition France entière
IGN = {
    "admin_express": ("IGN ADMIN EXPRESS COG - limites administratives (communes, EPCI, départements)",
                      "ADMIN-EXPRESS-COG"),
    "iris": ("IGN CONTOURS IRIS - découpage IRIS", "CONTOURS-IRIS"),
}

GEOFABRIK = "https://download.geofabrik.de/europe/france"

CATEGORIES = ["citiz", "gbfs", "gtfs", "stops_national", "gbfs_catalog", "insee", "ign", "osm"]

# --------------------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------------------
_lock = threading.Lock()
MANIFEST: list[dict] = []


def log(msg: str) -> None:
    with _lock:
        print(msg, flush=True)


def slug(s: str, maxlen: int = 80) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")
    return s[:maxlen] or "x"


def http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_json(url: str, timeout: int = 60):
    return json.loads(http_get(url, timeout).decode("utf-8"))


def human(n: float) -> str:
    for u in ["o", "Ko", "Mo", "Go"]:
        if n < 1024:
            return f"{n:.0f} {u}"
        n /= 1024
    return f"{n:.1f} To"


def download(url: str, dest: Path, label: str, category: str, retries: int = 3,
             timeout: int = 120) -> bool:
    """Téléchargement en streaming, reprise si fichier déjà présent, écriture atomique."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    status = "ok"
    if dest.exists() and dest.stat().st_size > 0:
        status = "deja_present"
    else:
        tmp = dest.with_suffix(dest.suffix + ".part")
        for attempt in range(1, retries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as f:
                    shutil.copyfileobj(r, f, length=1024 * 1024)
                tmp.replace(dest)
                break
            except Exception as e:  # noqa: BLE001
                if attempt == retries:
                    status = f"erreur: {type(e).__name__}: {e}"[:200]
                    tmp.unlink(missing_ok=True)
                else:
                    time.sleep(2 * attempt)
    size = dest.stat().st_size if dest.exists() else 0
    with _lock:
        MANIFEST.append({"categorie": category, "source": label, "url": url,
                         "fichier": str(dest), "taille": size, "statut": status,
                         "date": dt.datetime.now().isoformat(timespec="seconds")})
    tag = "OK " if status in ("ok", "deja_present") else "ERR"
    log(f"  [{tag}] {category:<14} {human(size):>8}  {dest.name}  {'' if tag == 'OK ' else status}")
    return tag == "OK "


# --------------------------------------------------------------------------------------
# transport.data.gouv.fr
# --------------------------------------------------------------------------------------
def tdg_catalog(out: Path) -> list[dict]:
    log("-> Catalogue transport.data.gouv.fr ...")
    data = get_json(TDG_API, timeout=180)
    (out / "transport_data_gouv").mkdir(parents=True, exist_ok=True)
    (out / "transport_data_gouv" / "catalogue_datasets.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"   {len(data)} jeux de données dans le catalogue")
    return data


def gbfs_feed_urls(autodisc: dict) -> list[tuple[str, str]]:
    """Retourne [(nom, url)] des sous-flux d'un gbfs.json (v1/v2 : par langue, v3 : liste)."""
    d = autodisc.get("data", {})
    feeds = []
    if isinstance(d.get("feeds"), list):  # GBFS v3
        feeds = d["feeds"]
    else:  # v1/v2 : {"fr": {"feeds": [...]}, "en": ...}
        for lang in ("fr", "en"):
            if isinstance(d.get(lang), dict) and d[lang].get("feeds"):
                feeds = d[lang]["feeds"]
                break
        if not feeds:
            for v in d.values():
                if isinstance(v, dict) and v.get("feeds"):
                    feeds = v["feeds"]
                    break
    return [(f.get("name", "feed"), f.get("url")) for f in feeds if f.get("url")]


def fetch_gbfs_system(ds: dict, res: dict, root: Path, category: str) -> dict:
    """Télécharge gbfs.json + tous ses sous-flux (station_information, station_status, ...)."""
    sysdir = root / slug(ds["slug"]) / slug(res.get("title") or str(res.get("id")), 50)
    sysdir.mkdir(parents=True, exist_ok=True)
    url = res.get("url") or res.get("original_url")
    label = f"GBFS - {ds['title']} - {res.get('title', '')}"
    info = {"dataset": ds["slug"], "title": ds["title"], "gbfs_url": url, "dir": str(sysdir), "feeds": {}}
    try:
        raw = http_get(url, 60)
        (sysdir / "gbfs.json").write_bytes(raw)
        auto = json.loads(raw)
        feeds = gbfs_feed_urls(auto)
        if not feeds:  # la ressource n'est pas un gbfs.json d'autodécouverte
            info["feeds"]["raw"] = url
        for name, furl in feeds:
            ok = download(furl, sysdir / f"{slug(name)}.json", f"{label} [{name}]", category, timeout=60)
            if ok:
                info["feeds"][name] = furl
        with _lock:
            MANIFEST.append({"categorie": category, "source": label, "url": url,
                             "fichier": str(sysdir / "gbfs.json"), "taille": len(raw), "statut": "ok",
                             "date": dt.datetime.now().isoformat(timespec="seconds")})
    except Exception as e:  # noqa: BLE001
        log(f"  [ERR] {category:<14} {ds['slug']}: {type(e).__name__}: {e}")
        info["error"] = str(e)
    return info


def run_gbfs(catalog: list[dict], out: Path, workers: int, citiz_only: bool) -> None:
    category = "citiz" if citiz_only else "gbfs"
    root = out / ("gbfs_citiz" if citiz_only else "gbfs_all")
    jobs = []
    for ds in catalog:
        if ds.get("type") != "vehicles-sharing":
            continue
        is_citiz = "citiz" in (ds.get("title", "") + ds.get("slug", "")).lower()
        if citiz_only != is_citiz:
            continue
        for res in ds.get("resources", []):
            if (res.get("format") or "").lower() == "gbfs" and res.get("is_available", True):
                jobs.append((ds, res))
    log(f"-> GBFS {'Citiz' if citiz_only else '(vélos, trottinettes, autopartage hors Citiz)'} : "
        f"{len(jobs)} flux")
    index = []
    with cf.ThreadPoolExecutor(workers) as ex:
        for info in ex.map(lambda j: fetch_gbfs_system(j[0], j[1], root, category), jobs):
            index.append(info)
    (root / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def run_gtfs(catalog: list[dict], out: Path, workers: int, filters: list[str]) -> None:
    root = out / "gtfs"
    jobs = []
    for ds in catalog:
        if ds.get("type") != "public-transit":
            continue
        text = " ".join([ds.get("title", ""), ds.get("slug", ""),
                         json.dumps(ds.get("covered_area", ""), ensure_ascii=False)]).lower()
        if filters and not any(f.lower() in text for f in filters):
            continue
        for res in ds.get("resources", []):
            if (res.get("format") or "").upper() == "GTFS" and res.get("is_available", True):
                url = res.get("url") or res.get("original_url")
                name = f"{slug(ds['slug'], 60)}__{res.get('id')}.zip"
                jobs.append((f"GTFS - {ds['title']} - {res.get('title', '')}", url, root / name))
    log(f"-> GTFS transports en commun : {len(jobs)} fichiers"
        + (f" (filtre : {', '.join(filters)})" if filters else " (France entière)"))
    with cf.ThreadPoolExecutor(workers) as ex:
        list(ex.map(lambda j: download(j[1], j[2], j[0], "gtfs", timeout=300), jobs))


# --------------------------------------------------------------------------------------
# IGN (Atom data.geopf.fr)
# --------------------------------------------------------------------------------------
ATOM = "{http://www.w3.org/2005/Atom}"


def ign_entries(collection: str) -> list[str]:
    names, page = [], 1
    while page <= 30:
        url = f"https://data.geopf.fr/telechargement/resource/{collection}?page={page}"
        try:
            root = ET.fromstring(http_get(url, 60))
        except Exception:  # noqa: BLE001
            break
        entries = root.findall(f"{ATOM}entry")
        if not entries:
            break
        for e in entries:
            t = e.findtext(f"{ATOM}title") or ""
            for l in e.findall(f"{ATOM}link"):
                href = l.get("href", "")
                t = t or href.rstrip("/").split("/")[-1]
            names.append(t.strip())
        page += 1
    return [n for n in names if n]


def ign_pick_latest(names: list[str]) -> str | None:
    """Dernière édition France entière, GPKG de préférence."""
    def score(n: str):
        date = (re.findall(r"(\d{4}-\d{2}-\d{2})", n) or ["0000"])[-1]
        zone = 2 if re.search(r"_FRA_", n) else (1 if re.search(r"_FXX_", n) else 0)
        fmt = 1 if "GPKG" in n else 0
        return (zone > 0, date, zone, fmt)
    cands = [n for n in names if re.search(r"_(FRA|FXX)_", n)]
    return max(cands, key=score) if cands else None


def run_ign(out: Path) -> None:
    for key, (label, coll) in IGN.items():
        log(f"-> IGN {coll} : recherche de la dernière édition ...")
        names = ign_entries(coll)
        entry = ign_pick_latest(names)
        if not entry:
            log(f"  [ERR] ign            aucune entrée trouvée pour {coll} "
                f"(télécharge à la main : https://cartes.gouv.fr)")
            continue
        log(f"   édition choisie : {entry}")
        files = []
        try:
            root = ET.fromstring(http_get(
                f"https://data.geopf.fr/telechargement/resource/{coll}/{entry}", 60))
            for l in root.iter(f"{ATOM}link"):
                href = l.get("href", "")
                if re.search(r"\.(7z|zip)(\.\d+)?$", href):
                    files.append(href)
        except Exception:  # noqa: BLE001
            pass
        if not files:  # schéma d'URL standard en secours
            files = [f"https://data.geopf.fr/telechargement/download/{coll}/{entry}/{entry}.7z"]
        for href in files:
            download(href, out / "ign" / key / href.split("/")[-1], f"{label} ({entry})", "ign",
                     timeout=600)


# --------------------------------------------------------------------------------------
# OSM (Geofabrik)
# --------------------------------------------------------------------------------------
def run_osm(out: Path, mode: str, regions: list[str]) -> None:
    if mode == "none":
        return
    if mode == "france":
        jobs = [("france", "https://download.geofabrik.de/europe/france-latest.osm.pbf")]
    else:
        jobs = [(r, f"{GEOFABRIK}/{r}-latest.osm.pbf") for r in regions]
    for name, url in jobs:
        log(f"-> OSM {name} (gros fichier, patience) ...")
        download(url, out / "osm" / f"{name}-latest.osm.pbf",
                 f"OpenStreetMap - {name} (Geofabrik)", "osm", timeout=3600)


# --------------------------------------------------------------------------------------
# Sorties : manifest + sources.md
# --------------------------------------------------------------------------------------
def write_outputs(out: Path, docs: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.csv"
    old = []
    if mpath.exists():
        with open(mpath, encoding="utf-8") as f:
            old = list(csv.DictReader(f))
    seen = {r["fichier"] for r in MANIFEST}
    rows = [r for r in old if r["fichier"] not in seen] + MANIFEST
    with open(mpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["categorie", "source", "url", "fichier", "taille", "statut", "date"])
        w.writeheader()
        w.writerows(rows)

    docs.mkdir(parents=True, exist_ok=True)
    by_src: dict[str, dict] = {}
    for r in rows:
        if not str(r["statut"]).startswith("erreur"):
            key = re.sub(r" \[.*\]$", "", r["source"])
            by_src.setdefault(r["categorie"], {}).setdefault(key, r["url"])
    lines = ["# Sources de données", "",
             f"Généré automatiquement par `download_all.py` le {dt.date.today().isoformat()}.", "",
             "Toutes les données sont ouvertes (Licence Ouverte Etalab / ODbL pour OpenStreetMap).", ""]
    titles = {"citiz": "Citiz (GBFS, partenaire)", "gbfs": "Mobilités partagées (GBFS)",
              "gtfs": "Transports en commun (GTFS)", "stops_national": "Arrêts nationaux",
              "gbfs_catalog": "Catalogue GBFS", "insee": "INSEE", "ign": "IGN",
              "osm": "OpenStreetMap"}
    for cat in CATEGORIES:
        if cat not in by_src:
            continue
        lines += [f"## {titles.get(cat, cat)}", ""]
        items = sorted(by_src[cat].items())
        for src, url in items[:300]:
            lines.append(f"- {src} — <{url}>")
        if len(items) > 300:
            lines.append(f"- ... et {len(items) - 300} autres (voir `data/raw/manifest.csv`)")
        lines.append("")
    (docs / "sources.md").write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------------------
def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="data/raw", help="dossier de sortie (défaut : data/raw)")
    p.add_argument("--docs", default="docs", help="dossier où écrire sources.md")
    p.add_argument("--only", nargs="*", choices=CATEGORIES, help="ne télécharger que ces catégories")
    p.add_argument("--skip", nargs="*", choices=CATEGORIES, default=[], help="catégories à ignorer")
    p.add_argument("--gtfs-filter", nargs="*", default=[], help="mots-clés pour filtrer les GTFS")
    p.add_argument("--osm", choices=["france", "region", "none"], default="france",
                   help="OSM : France entière (~4,5 Go), une/des région(s), ou rien")
    p.add_argument("--osm-region", nargs="*", default=["ile-de-france"],
                   help="régions Geofabrik (ex : grand-est, auvergne-rhone-alpes, ile-de-france)")
    p.add_argument("--workers", type=int, default=8, help="téléchargements en parallèle")
    p.add_argument("--list", action="store_true", help="liste les catégories et quitte")
    a = p.parse_args()

    if a.list:
        print("\n".join(CATEGORIES))
        return 0

    cats = [c for c in (a.only or CATEGORIES) if c not in a.skip]
    out, docs = Path(a.out), Path(a.docs)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log(f"Catégories : {', '.join(cats)}\nSortie : {out.resolve()}\n")

    try:
        for cat in ("stops_national", "gbfs_catalog", "insee"):
            if cat in cats:
                log(f"-> {cat}")
                with cf.ThreadPoolExecutor(a.workers) as ex:
                    list(ex.map(lambda s: download(s[1], out / s[2], s[0], cat, timeout=900), STATIC[cat]))

        if any(c in cats for c in ("citiz", "gbfs", "gtfs")):
            catalog = tdg_catalog(out)
            if "citiz" in cats:
                run_gbfs(catalog, out, a.workers, citiz_only=True)
            if "gbfs" in cats:
                run_gbfs(catalog, out, a.workers, citiz_only=False)
            if "gtfs" in cats:
                run_gtfs(catalog, out, a.workers, a.gtfs_filter)

        if "ign" in cats:
            run_ign(out)
        if "osm" in cats:
            run_osm(out, a.osm, a.osm_region)
    except KeyboardInterrupt:
        log("\nInterrompu : relance la même commande pour reprendre.")
    finally:
        write_outputs(out, docs)

    ok = [r for r in MANIFEST if not str(r["statut"]).startswith("erreur")]
    ko = [r for r in MANIFEST if str(r["statut"]).startswith("erreur")]
    total = sum(int(r["taille"]) for r in ok)
    log(f"\nTerminé en {(time.time() - t0) / 60:.1f} min : {len(ok)} fichiers ({human(total)}), "
        f"{len(ko)} erreurs.")
    log(f"Manifeste : {out / 'manifest.csv'}  |  Sources : {docs / 'sources.md'}")
    if ko:
        log("Les erreurs sont listées dans le manifeste (souvent : flux temps réel protégé par clé "
            "ou serveur temporairement indisponible). Relancer le script les retente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
