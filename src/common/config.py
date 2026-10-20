"""Accès centralisé à config/settings.yaml et aux chemins du dépôt."""
from __future__ import annotations

import argparse
import os
import sys
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = ROOT / "config" / "settings.yaml"


@lru_cache(maxsize=None)
def load_settings(path: str | Path = SETTINGS_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def raw(*parts: str) -> Path:
    """Chemin sous data/raw (absolu, indépendant du dossier courant)."""
    return ROOT / load_settings()["paths"]["raw"] / Path(*parts)


def processed(*parts: str) -> Path:
    """Chemin sous data/processed ; crée le dossier parent si besoin."""
    p = ROOT / load_settings()["paths"]["processed"] / Path(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# --- Ville zoomée --------------------------------------------------------------------------------
CITY_ENV = "HACKATHON_VILLE"   # transmis aux sous-processus : une commande = une ville


def cities() -> list[str]:
    return list(load_settings()["cities"])


def current_city() -> str:
    return os.environ.get(CITY_ENV) or load_settings()["default_city"]


def set_city(name: str) -> str:
    if name not in cities():
        raise ValueError(f"ville inconnue : {name} (connues : {', '.join(cities())})")
    os.environ[CITY_ENV] = name
    return name


def study_area() -> dict:
    """Paramètres de la ville courante (section cities.<ville> de settings.yaml)."""
    return {"ville": current_city(), **load_settings()["cities"][current_city()]}


def city_processed(*parts: str) -> Path:
    """Chemin sous data/processed/<ville>/ (sorties du zoom)."""
    return processed(current_city(), *parts)


def city_from_args(argv: list[str] | None = None) -> str:
    """Lit --ville dans la ligne de commande (les autres options sont laissées au script)."""
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--ville", default=None)
    known, _ = ap.parse_known_args(sys.argv[1:] if argv is None else argv)
    return set_city(known.ville) if known.ville else current_city()
