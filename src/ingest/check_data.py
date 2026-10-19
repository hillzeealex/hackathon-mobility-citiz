#!/usr/bin/env python3
"""
Vérifie les données téléchargées par download_all.py et collect_gbfs_status.py.

Uniquement la bibliothèque standard Python : aucune installation requise.

Usage :
    python src/ingest/check_data.py           # contrôles rapides (présence, tailles, JSON, comptages)
    python src/ingest/check_data.py --deep    # + intégrité des zip / 7z / parquet / pbf, contenu GTFS

Statuts :
    ✅  OK
    ⚠️  à surveiller (souvent normal en open data : flux optionnel absent, catégorie pas encore téléchargée)
    ❌  à corriger (fichier absent ou corrompu après tentative, page HTML à la place des données...)

Sortie : data/raw/check_report.md ; code de retour 1 s'il y a au moins un ❌.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from download_all import IGN, STATIC, human  # noqa: E402  (source unique des fichiers attendus)

ROOT = Path(__file__).resolve().parents[2]  # racine du dépôt (src/ingest/ -> ../..)
OK, WARN, ERR = "✅", "⚠️", "❌"
# Emprise large de la France métropolitaine (lon_min, lat_min, lon_max, lat_max)
FRANCE_BBOX = (-5.8, 41.2, 10.0, 51.3)
GTFS_REQUIRED = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
SEVEN_Z_MAGIC = b"7z\xbc\xaf\x27\x1c"
HISTORY_MAX_AGE_MIN = 15


class Report:
    def __init__(self) -> None:
        self.items: list[tuple[str, str, str, str]] = []  # (section, statut, objet, détail)
        self.tables: dict[str, list[str]] = {}

    def add(self, section: str, status: str, what: str, detail: str = "") -> None:
        self.items.append((section, status, what, detail))

    def count(self, status: str) -> int:
        return sum(1 for i in self.items if i[1] == status)


# --------------------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------------------
def head(path: Path, n: int = 512) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def looks_like_html(path: Path) -> bool:
    """Un lien cassé renvoie souvent une page HTML (200 OK) au lieu du fichier."""
    h = head(path, 512).lstrip().lower()
    return h.startswith(b"<!doctype html") or h.startswith(b"<html")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def manifest_categories(raw: Path) -> dict[str, Counter]:
    """{catégorie: Counter(ok=…, erreur=…)} d'après manifest.csv (vide si absent)."""
    res: dict[str, Counter] = defaultdict(Counter)
    m = raw / "manifest.csv"
    if m.exists():
        with open(m, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                res[r["categorie"]]["erreur" if r["statut"].startswith("erreur") else "ok"] += 1
    return res


def manifest_errors(raw: Path) -> list[dict]:
    m = raw / "manifest.csv"
    if not m.exists():
        return []
    with open(m, encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r["statut"].startswith("erreur")]


def missing_status(cat: str, attempted: dict) -> str:
    """Absent mais jamais tenté = ⚠️ (pas encore téléchargé) ; absent après tentative = ❌."""
    return ERR if cat in attempted else WARN


# --------------------------------------------------------------------------------------
# Contrôles
# --------------------------------------------------------------------------------------
def check_manifest(raw: Path, rep: Report) -> dict:
    sec = "Manifeste"
    cats = manifest_categories(raw)
    if not cats:
        rep.add(sec, WARN, "manifest.csv", "absent : aucun téléchargement encore effectué")
        return cats
    for cat, c in sorted(cats.items()):
        n_ok, n_err = c["ok"], c["erreur"]
        if n_err == 0:
            st = OK
        elif cat in ("gbfs", "gtfs", "citiz") and n_err <= 0.2 * (n_ok + n_err):
            st = WARN  # quelques flux temps réel indisponibles : courant en open data
        else:
            st = ERR
        rep.add(sec, st, cat, f"{n_ok} OK, {n_err} en erreur")
    errs = manifest_errors(raw)
    if errs:
        rep.tables["Erreurs du manifeste"] = (
            ["| catégorie | source | statut |", "|---|---|---|"]
            + [f"| {e['categorie']} | {e['source'][:90]} | {e['statut'][:120]} |" for e in errs[:60]]
            + ([f"| ... | {len(errs) - 60} autres | |"] if len(errs) > 60 else []))
    return cats


def station_list(path: Path) -> list[dict]:
    d = load_json(path).get("data", {})
    return d.get("stations", []) if isinstance(d, dict) else []


def check_citiz(raw: Path, rep: Report, attempted: dict) -> None:
    sec = "GBFS Citiz"
    idx = raw / "gbfs_citiz" / "index.json"
    if not idx.exists():
        rep.add(sec, missing_status("citiz", attempted), "index.json", "absent (download_all.py --only citiz)")
        return
    systems = load_json(idx)
    rows, tot_st, tot_veh, tot_cap = [], 0, 0, 0
    slugs = Counter(s.get("dataset") for s in systems)
    for s in systems:
        d = Path(s.get("dir", ""))
        if not d.is_absolute():
            d = ROOT / d
        name = d.name if d.name else s.get("title", "?")
        if s.get("error"):
            rep.add(sec, ERR, name, f"gbfs.json inaccessible : {s['error'][:120]}")
            continue
        si, ss = d / "station_information.json", d / "station_status.json"
        try:
            stations = station_list(si) if si.exists() else []
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            rep.add(sec, ERR, f"{name}/station_information.json", f"JSON invalide : {e}")
            continue
        try:
            status = station_list(ss) if ss.exists() else []
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            rep.add(sec, ERR, f"{name}/station_status.json", f"JSON invalide : {e}")
            status = []
        if not stations:
            rep.add(sec, WARN, name, "aucune station dans station_information")
        bad = [x for x in stations
               if not (FRANCE_BBOX[0] <= float(x.get("lon") or 0) <= FRANCE_BBOX[2]
                       and FRANCE_BBOX[1] <= float(x.get("lat") or 0) <= FRANCE_BBOX[3])]
        if bad:
            rep.add(sec, WARN, name, f"{len(bad)} station(s) aux coordonnées aberrantes (0,0 ou hors France)")
        veh = sum(int(x.get("num_vehicles_available", x.get("num_bikes_available")) or 0) for x in status)
        cap = sum(int(x.get("capacity") or 0) for x in stations)
        tot_st, tot_veh, tot_cap = tot_st + len(stations), tot_veh + veh, tot_cap + cap
        rows.append(f"| {name} | {s.get('dataset')} | {len(stations)} | {cap} | {veh} | "
                    f"{', '.join(k for k in s.get('feeds', {}))} |")
    dup = [k for k, v in slugs.items() if v > 1]
    if dup:
        rep.add(sec, WARN, "identifiants",
                f"{len(dup)} jeu(x) regroupant plusieurs réseaux ({', '.join(dup)}) : préfixer station_id "
                "par le réseau pour éviter les collisions")
    n_ok = len(rows)
    rep.add(sec, OK if n_ok and tot_st else ERR, "réseaux",
            f"{n_ok} réseaux, {tot_st} stations, capacité déclarée {tot_cap}, {tot_veh} véhicules disponibles")
    rep.tables["Réseaux Citiz"] = (["| réseau | jeu | stations | capacité | véh. dispo | flux |",
                                    "|---|---|---:|---:|---:|---|"] + sorted(rows))


def check_gbfs_all(raw: Path, rep: Report, attempted: dict) -> None:
    sec = "GBFS autres"
    idx = raw / "gbfs_all" / "index.json"
    if not idx.exists():
        rep.add(sec, missing_status("gbfs", attempted), "index.json", "absent (download_all.py --only gbfs)")
        return
    systems = load_json(idx)
    err = [s for s in systems if s.get("error")]
    with_st = [s for s in systems if "station_information" in s.get("feeds", {})]
    rate = len(err) / max(1, len(systems))
    rep.add(sec, OK if rate == 0 else (WARN if rate <= 0.2 else ERR), "systèmes",
            f"{len(systems)} flux, {len(with_st)} avec stations, {len(err)} inaccessibles")


def check_history(raw: Path, rep: Report) -> None:
    sec = "Historique Citiz"
    files = sorted((raw / "gbfs_history").glob("station_status_*.csv"))
    if not files:
        rep.add(sec, WARN, "gbfs_history", "vide : lancer collect_gbfs_status.py")
        return
    snaps, stations, n = set(), set(), 0
    for p in files:
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                n += 1
                snaps.add(r["snapshot_utc"])
                stations.add((r["dataset"], r["station_id"]))
    last = max(snaps)
    age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last)).total_seconds() / 60
    rep.add(sec, OK if n else ERR, "photos",
            f"{len(files)} fichier(s), {len(snaps)} photos, {n} lignes, {len(stations)} stations distinctes")
    rep.add(sec, OK if age <= HISTORY_MAX_AGE_MIN else WARN, "fraîcheur",
            f"dernière photo {last} (il y a {age:.0f} min)"
            + ("" if age <= HISTORY_MAX_AGE_MIN else " : le collecteur est-il arrêté ?"))


def check_file_integrity(path: Path, deep: bool) -> tuple[str, str]:
    """Contrôle d'un fichier statique : (statut, détail)."""
    size = path.stat().st_size
    if size == 0:
        return ERR, "fichier vide"
    if looks_like_html(path):
        return ERR, "page HTML au lieu des données : lien probablement changé"
    if size < 1024:
        return WARN, f"très petit ({human(size)})"
    detail = human(size)
    if not deep:
        return OK, detail
    suf = path.suffix.lower()
    try:
        if suf == ".zip":
            with zipfile.ZipFile(path) as z:
                badf = z.testzip()
                if badf:
                    return ERR, f"zip corrompu ({badf})"
                detail += f", zip OK ({len(z.namelist())} fichiers)"
        elif suf == ".parquet":
            with open(path, "rb") as f:
                start = f.read(4)
                f.seek(-4, 2)
                end = f.read(4)
            if start != b"PAR1" or end != b"PAR1":
                return ERR, "parquet invalide (signature PAR1 absente)"
            detail += ", parquet OK"
        elif suf == ".csv":
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                hdr = f.readline().strip()
                n = sum(1 for _ in f)
            detail += f", {n} lignes, en-tête : {hdr[:80]}"
    except zipfile.BadZipFile:
        return ERR, "zip illisible (téléchargement tronqué ?)"
    return OK, detail


def check_static(raw: Path, rep: Report, attempted: dict, deep: bool) -> None:
    for cat, items in STATIC.items():
        sec = {"insee": "INSEE", "stops_national": "Arrêts nationaux", "gbfs_catalog": "Catalogue GBFS"}[cat]
        for label, _url, rel in items:
            p = raw / rel
            if not p.exists():
                rep.add(sec, missing_status(cat, attempted), p.name, f"absent ({label[:70]})")
                continue
            st, detail = check_file_integrity(p, deep)
            rep.add(sec, st, p.name, detail)
    cat_csv = raw / "gbfs_catalog" / "systems.csv"
    if cat_csv.exists() and not looks_like_html(cat_csv):
        with open(cat_csv, encoding="utf-8-sig", errors="replace") as f:
            rows = list(csv.DictReader(f))
        fr = [r for r in rows if (r.get("Country Code") or "").upper() == "FR"]
        citiz = [r for r in fr if "citiz" in json.dumps(r).lower()]
        rep.add("Catalogue GBFS", OK, "systems.csv (contenu)",
                f"{len(rows)} systèmes dans le monde, {len(fr)} en France dont {len(citiz)} Citiz")


def check_ign(raw: Path, rep: Report, attempted: dict, deep: bool) -> None:
    sec = "IGN"
    for key, (label, _coll) in IGN.items():
        files = sorted((raw / "ign" / key).glob("*")) if (raw / "ign" / key).exists() else []
        files = [f for f in files if f.is_file() and not f.name.endswith(".part")]  # ignore extracted/ etc.
        if not files:
            rep.add(sec, missing_status("ign", attempted), key, f"absent ({label[:60]})")
            continue
        for f in files:
            if looks_like_html(f):
                rep.add(sec, ERR, f.name, "page HTML au lieu de l'archive : lien IGN changé")
                continue
            detail, st = human(f.stat().st_size), OK
            first_volume = f.name.endswith(".7z") or f.name.endswith(".7z.001")
            if deep and first_volume and head(f, 6) != SEVEN_Z_MAGIC:
                st, detail = ERR, detail + ", signature 7z absente"
            elif deep and first_volume:
                detail += ", signature 7z OK"
            rep.add(sec, st, f.name, detail)


def check_osm(raw: Path, rep: Report, attempted: dict, deep: bool) -> None:
    sec = "OSM"
    files = sorted((raw / "osm").glob("*.osm.pbf")) if (raw / "osm").exists() else []
    if not files:
        rep.add(sec, missing_status("osm", attempted), "*.osm.pbf", "absent (download_all.py --osm region ...)")
        return
    for f in files:
        size = f.stat().st_size
        if deep and b"OSMHeader" not in head(f, 64):
            rep.add(sec, ERR, f.name, f"{human(size)}, en-tête PBF absent (fichier corrompu ?)")
        elif size < 10 * 1024 ** 2:
            rep.add(sec, WARN, f.name, f"{human(size)} : étonnamment petit pour une région")
        else:
            rep.add(sec, OK, f.name, human(size) + (", en-tête PBF OK" if deep else ""))


def check_gtfs(raw: Path, rep: Report, attempted: dict, deep: bool) -> None:
    sec = "GTFS"
    files = sorted((raw / "gtfs").glob("*.zip")) if (raw / "gtfs").exists() else []
    if not files:
        rep.add(sec, missing_status("gtfs", attempted), "gtfs/*.zip", "aucun GTFS (download_all.py --only gtfs)")
        return
    total = sum(f.stat().st_size for f in files)
    rep.add(sec, OK, "fichiers", f"{len(files)} GTFS, {human(total)}")
    if not deep:
        return
    bad = []
    for f in files:
        try:
            with zipfile.ZipFile(f) as z:
                names = {Path(n).name for n in z.namelist()}
                missing = GTFS_REQUIRED - names
                if z.testzip():
                    bad.append((f.name, "zip corrompu"))
                elif missing:
                    bad.append((f.name, f"manque {', '.join(sorted(missing))}"))
        except zipfile.BadZipFile:
            bad.append((f.name, "HTML au lieu d'un zip" if looks_like_html(f) else "zip illisible"))
    rate = len(bad) / len(files)
    rep.add(sec, OK if not bad else (WARN if rate <= 0.1 else ERR), "intégrité",
            f"{len(files) - len(bad)}/{len(files)} GTFS valides")
    if bad:
        rep.tables["GTFS invalides"] = (["| fichier | problème |", "|---|---|"]
                                        + [f"| {n} | {p} |" for n, p in bad])


def check_tdg(raw: Path, rep: Report, attempted: dict) -> None:
    p = raw / "transport_data_gouv" / "catalogue_datasets.json"
    if not p.exists():
        if any(c in attempted for c in ("citiz", "gbfs", "gtfs")):
            rep.add("transport.data.gouv.fr", ERR, p.name, "absent")
        return
    try:
        rep.add("transport.data.gouv.fr", OK, p.name, f"{len(load_json(p))} jeux de données")
    except json.JSONDecodeError as e:
        rep.add("transport.data.gouv.fr", ERR, p.name, f"JSON invalide : {e}")


# --------------------------------------------------------------------------------------
def write_report(rep: Report, path: Path, deep: bool) -> None:
    lines = ["# Rapport de vérification des données", "",
             f"Généré par `check_data.py{' --deep' if deep else ''}` le "
             f"{dt.datetime.now().isoformat(timespec='seconds')}.", "",
             f"**{rep.count(OK)} {OK}  ·  {rep.count(WARN)} {WARN}  ·  {rep.count(ERR)} {ERR}**", "",
             "| section | statut | objet | détail |", "|---|:---:|---|---|"]
    lines += [f"| {s} | {st} | {w} | {d} |" for s, st, w, d in rep.items]
    for title, tbl in rep.tables.items():
        lines += ["", f"## {title}", ""] + tbl
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):  # console Windows : éviter UnicodeEncodeError sur les emojis
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--raw", default=str(ROOT / "data" / "raw"), help="dossier des données brutes")
    p.add_argument("--report", default=None, help="chemin du rapport (défaut : <raw>/check_report.md)")
    p.add_argument("--deep", action="store_true", help="contrôles d'intégrité complets (plus lent)")
    a = p.parse_args()

    raw = Path(a.raw)
    rep = Report()
    attempted = check_manifest(raw, rep)
    check_tdg(raw, rep, attempted)
    check_citiz(raw, rep, attempted)
    check_history(raw, rep)
    check_gbfs_all(raw, rep, attempted)
    check_static(raw, rep, attempted, a.deep)
    check_gtfs(raw, rep, attempted, a.deep)
    check_ign(raw, rep, attempted, a.deep)
    check_osm(raw, rep, attempted, a.deep)

    out = Path(a.report) if a.report else raw / "check_report.md"
    write_report(rep, out, a.deep)
    for s, st, w, d in rep.items:
        print(f"{st}  {s:<22} {w:<40} {d}")
    print(f"\n{rep.count(OK)} OK, {rep.count(WARN)} à surveiller, {rep.count(ERR)} à corriger -> {out}")
    return 1 if rep.count(ERR) else 0


if __name__ == "__main__":
    raise SystemExit(main())
