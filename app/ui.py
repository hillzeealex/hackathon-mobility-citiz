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


def fr(x, digits: int = 0, unit: str = "") -> str:
    """Nombre au format français : 12 345,6 (espace fine insécable pour les milliers)."""
    if x is None or pd.isna(x):
        return "n.d."
    s = f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s + (f" {unit}" if unit else "")


def fit_zoom(gdf, width_px: int = 600, height_px: int = 440, pad: float = 1.4, lo: float = 9.5,
             hi: float = 13.0) -> float:
    """Zoom qui fait tenir l'emprise de `gdf` (WGS84) dans une carte d'au moins width_px × height_px."""
    minx, miny, maxx, maxy = gdf.total_bounds
    span_x = max(maxx - minx, 1e-3) * pad
    span_y = max(maxy - miny, 1e-3) * pad / np.cos(np.radians((miny + maxy) / 2))
    z = min(np.log2(width_px * 360 / (512 * span_x)), np.log2(height_px * 360 / (512 * span_y)))   # tuiles deck.gl : 512 px
    return float(np.clip(z, lo, hi))


def fmt(x: float, unit: str = "") -> str:
    return fr(x, 0, unit)


def pct(v, digits: int = 1) -> str:
    """Part (0-1) en pourcentage français : 0,259 -> « 25,9 % »."""
    return "n.d." if v is None or pd.isna(v) else fr(100 * v, digits, "%")


def walk_minutes(m: float, speed_kmh: float = 4.8) -> str:
    """Distance de marche (m) -> « 7 min » (arrondi au-dessus) ; au-delà de 30 min : « plus de 30 min »."""
    if m is None or not np.isfinite(m):
        return "plus de 30 min"
    minutes = int(np.ceil(m / (speed_kmh * 1000 / 60)))
    return "plus de 30 min" if minutes > 30 else f"{minutes} min"


def table(df: pd.DataFrame, digits: dict[str, int] | None = None, percent: dict[str, int] | None = None):
    """Tableau au format français pour st.dataframe (les colonnes restent numériques pour le tri)."""
    sty = df.style
    for col, n in (digits or {}).items():
        if col in df:
            sty = sty.format(lambda v, n=n: fr(v, n), subset=[col])
    for col, n in (percent or {}).items():
        if col in df:
            sty = sty.format(lambda v, n=n: pct(v, n), subset=[col])
    return sty
