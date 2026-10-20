"""Calcul des poids des offres de transport pour le modèle d'accessibilité."""
from __future__ import annotations

import numpy as np
import pandas as pd


def offer_weights(offer: pd.DataFrame, settings: dict) -> np.ndarray:
    """Calcule le poids pondéré de chaque point d'offre selon le mode et la fréquence."""
    mode_weights = settings.get("mode_weights", {
        "bus": 1.0, "tram": 2.0, "metro": 3.0, "train": 3.0,
        "velo": 1.0, "trottinette": 0.5, "citiz": 1.5, "autopartage": 1.0
    })
    
    # Poids de base par mode
    base_w = offer["type"].map(lambda t: mode_weights.get(t, 1.0)).to_numpy(dtype=float)
    
    # Free-floating
    if "sous_type" in offer.columns and "free_floating_weight" in settings:
        ff_mask = offer["sous_type"].isin(["zone_free_floating", "free_floating"]).to_numpy()
        base_w[ff_mask] = settings["free_floating_weight"]
        
    # Pondération fréquence (si renseignée et activée)
    freq_cfg = settings.get("frequency", {})
    if freq_cfg.get("enabled", False) and "passages_jour" in offer.columns:
        ref = freq_cfg.get("reference_passages_jour", 100)
        min_f = freq_cfg.get("min_factor", 0.25)
        max_f = freq_cfg.get("max_factor", 2.0)
        
        has_freq = offer["passages_jour"].notna().to_numpy()
        factors = np.clip(offer["passages_jour"].to_numpy(dtype=float) / ref, min_f, max_f)
        factors[~has_freq] = 1.0
        base_w = base_w * factors

    return base_w

