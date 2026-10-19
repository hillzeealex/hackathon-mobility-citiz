"""Localise (et extrait au besoin) les GeoPackages des archives IGN (.7z) et INSEE (.zip) de data/raw/."""
from __future__ import annotations

import zipfile
from pathlib import Path

import py7zr

from src.common.config import raw


def ign_gpkg(key: str, name_contains: str = "") -> Path:
    """GeoPackage de data/raw/ign/<key>/ (admin_express, iris), extrait dans <key>/extracted/ si besoin."""
    folder = raw("ign", key)
    found = [p for p in (folder / "extracted").rglob("*.gpkg") if name_contains in p.name]
    if found:
        return found[0]
    archives = sorted(folder.glob("*.7z"))
    if not archives:
        raise FileNotFoundError(f"aucune archive IGN dans {folder} : lancer download_all.py --only ign")
    with py7zr.SevenZipFile(archives[-1]) as z:
        targets = [n for n in z.getnames() if n.endswith(".gpkg") and name_contains in Path(n).name]
        z.extract(path=folder / "extracted", targets=targets)
    return next(p for p in (folder / "extracted").rglob("*.gpkg") if name_contains in p.name)


def filosofi_gpkg(member: str = "carreaux_200m_met.gpkg") -> Path:
    dest = raw("insee", "filosofi", member)
    if not dest.exists():
        with zipfile.ZipFile(raw("insee", "filosofi2021_carreaux_200m_gpkg.zip")) as z:
            z.extract(member, dest.parent)
    return dest
