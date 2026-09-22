import json
import os
from pathlib import Path


def app_support_dir() -> Path:
    p = Path.home() / "Library" / "Application Support" / "Card-Sharp"
    p.mkdir(parents=True, exist_ok=True)
    return p


PREFS_PATH = app_support_dir() / "prefs.json"

DEFAULTS = {
    "window_geometry": "1180x760+200+120",
    "preset_name": "Foxwoods — 6D Main Pit",
    "bankroll": 1000,
    "bet": 25,
    "custom_presets": {},   # name -> Rules.to_dict()
    "sound_enabled": True,
    "auto_deal": False,
    "deviations": {},       # "<hand_key>|<upcard>" -> action letter
}


def load() -> dict:
    if not PREFS_PATH.exists():
        return dict(DEFAULTS)
    try:
        with open(PREFS_PATH) as f:
            data = json.load(f)
        out = dict(DEFAULTS)
        out.update(data)
        return out
    except Exception:
        return dict(DEFAULTS)


def save(prefs: dict) -> None:
    try:
        with open(PREFS_PATH, "w") as f:
            json.dump(prefs, f, indent=2)
    except Exception:
        pass
