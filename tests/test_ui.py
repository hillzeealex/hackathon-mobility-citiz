"""Formats français de l'interface."""
import math

from app.ui import fr, pct, walk_minutes


def test_french_numbers():
    assert fr(34979) == "34 979"
    assert fr(13.62, 1, "€") == "13,6 €"
    assert pct(0.259) == "25,9 %" and pct(None) == "n.d."


def test_walk_minutes_rounds_up():
    assert walk_minutes(400.6) == "6 min"            # au-delà de 400 m : jamais « 5 min »
    assert walk_minutes(508) == "7 min"
    assert walk_minutes(math.inf) == walk_minutes(5000) == "plus de 30 min"
