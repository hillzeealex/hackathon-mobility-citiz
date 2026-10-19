"""Éléments d'affichage partagés entre la vue nationale et la vue zoom."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pydeck as pdk

# Rampe froid -> chaud (bleu -> rouge), lisible en daltonisme léger
RAMP = np.array([[49, 54, 149], [69, 117, 180], [116, 173, 209], [171, 217, 233], [254, 224, 144],
                 [253, 174, 97], [244, 109, 67], [215, 48, 39]])


def colorize(values: pd.Series, reverse: bool = False) -> list[list[int]]:
    """Couleur par quantile (robuste aux valeurs extrêmes) ; reverse : valeurs fortes en froid."""
    q = values.rank(pct=True).fillna(0).to_numpy()
    if reverse:
        q = 1 - q
    idx = np.clip((q * len(RAMP)).astype(int), 0, len(RAMP) - 1)
    return RAMP[idx].tolist()


def view(gdf, zoom: float = 11.3) -> pdk.ViewState:
    minx, miny, maxx, maxy = gdf.total_bounds
    return pdk.ViewState(longitude=(minx + maxx) / 2, latitude=(miny + maxy) / 2, zoom=zoom, pitch=0)


def deck(layers, gdf, tooltip, zoom: float = 11.3) -> pdk.Deck:
    return pdk.Deck(layers=layers, initial_view_state=view(gdf, zoom), map_provider="carto", map_style="light",
                    tooltip={"html": tooltip, "style": {"fontSize": "12px"}})


def fmt(x: float, unit: str = "") -> str:
    return f"{x:,.0f}".replace(",", " ") + (f" {unit}" if unit else "")
