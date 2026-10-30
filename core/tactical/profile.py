# -*- coding: utf-8 -*-
"""Player Profile (manual, seção 2) — totalmente configurável e persistido em data/player_profile.json."""
from . import load_json, save_json

PROFILE_FILE = "player_profile.json"

DEFAULT_PROFILE = {
    "account_type": "Alpha",
    "character_faction": "Amarr",
    "faction_warfare": "Amarr Empire",
    "militia": "24th Imperial Crusade",
    "experience": "Beginner",
    "preferred_pvp": ["Solo PvP", "Faction Warfare", "Frigate Duels", "Small Scale Combat"],
    "preferred_combat_style": ["Brawling", "Scram Kiting"],
    "preferred_language": "pt-BR",
    "primary_ship": "Tormentor",
    # Limiares configuráveis (não são fatos do jogo — são preferências do piloto)
    "thresholds": {
        "cap_low_pct": 35,
        "cap_critical_pct": 15,
        "armor_repair_start_pct": 70,
        "paste_low_count": 20,
        "range_lost_ratio": 0.75,
        "miss_ratio_alert": 0.6,
        "miss_min_shots": 8,
    },
    # Faixas de referência de cristais (m) — editáveis; confirmar sempre no jogo
    "ammo_bands_m": {"multifrequency_max": 4000, "standard_max": 8000},
}

EXPERIENCE_LEVELS = ["Beginner", "Intermediate", "Advanced"]
ACCOUNT_TYPES = ["Alpha", "Omega"]


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_profile() -> dict:
    return _merge(DEFAULT_PROFILE, load_json(PROFILE_FILE, {}))


def save_profile(profile: dict) -> bool:
    return save_json(PROFILE_FILE, profile)
