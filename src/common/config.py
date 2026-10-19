"""Accès centralisé à config/settings.yaml et aux chemins du dépôt."""
from __future__ import annotations

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
