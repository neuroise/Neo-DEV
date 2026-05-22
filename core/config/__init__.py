"""
NEUROISE configuration loader.

Single Source of Truth for archetypes, brand rules, and strategies.
All archetype-dependent code imports from this module.
"""

import json
import functools
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

_CONFIG_DIR = Path(__file__).parent


@functools.lru_cache(maxsize=1)
def load_archetypes() -> Dict[str, Any]:
    path = _CONFIG_DIR / "archetypes.json"
    with open(path) as f:
        return json.load(f)


def get_archetype_names() -> List[str]:
    return list(load_archetypes()["archetypes"].keys())


def get_archetype(name: str) -> Dict[str, Any]:
    cfg = load_archetypes()["archetypes"]
    key = name.lower()
    if key in cfg:
        return cfg[key]
    for canonical, data in cfg.items():
        if key in data.get("aliases", []):
            return data
    raise KeyError(f"Unknown archetype: {name}")


def resolve_archetype(name: str) -> str:
    cfg = load_archetypes()["archetypes"]
    key = name.lower()
    if key in cfg:
        return key
    for canonical, data in cfg.items():
        if key in data.get("aliases", []):
            return canonical
    return key


def get_prefix_map() -> Dict[str, str]:
    return load_archetypes()["prefix_map"]


def prefix_to_archetype(profile_id: str) -> str:
    prefix = profile_id.split("-")[0]
    return get_prefix_map().get(prefix, "unknown")


def get_bpm_ranges() -> Dict[str, Tuple[int, int]]:
    return {
        name: tuple(data["bpm_range"])
        for name, data in load_archetypes()["archetypes"].items()
    }


def get_archetype_colors() -> Dict[str, str]:
    return {
        name: data["color"]
        for name, data in load_archetypes()["archetypes"].items()
    }


def get_consistency_keywords() -> Dict[str, Set[str]]:
    return {
        name: set(data["consistency_keywords"])
        for name, data in load_archetypes()["archetypes"].items()
    }


def get_archetype_lexicon() -> Dict[str, Dict[str, List[str]]]:
    return {
        name: data["lexicon"]
        for name, data in load_archetypes()["archetypes"].items()
    }


def get_pacing_curves() -> Dict[str, Dict[str, Tuple[float, float]]]:
    return {
        name: {role: tuple(vals) for role, vals in data["pacing_curves"].items()}
        for name, data in load_archetypes()["archetypes"].items()
    }


def get_display_prefix_map() -> Dict[str, str]:
    """{'S': 'Sage', 'L': 'Lover', ...} using display_name."""
    cfg = load_archetypes()["archetypes"]
    pm = load_archetypes()["prefix_map"]
    result = {}
    for prefix, arch_id in pm.items():
        result[prefix] = cfg[arch_id]["display_name"]
    return result


# --- Brand & Strategy ---

def load_brand(brand_id: str = "neuroise_default") -> Dict[str, Any]:
    path = _CONFIG_DIR / "brand.json"
    with open(path) as f:
        return json.load(f)


def load_strategy(strategy_id: str = "default") -> Dict[str, Any]:
    path = _CONFIG_DIR / "strategies" / f"{strategy_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Strategy not found: {strategy_id}")
    with open(path) as f:
        return json.load(f)


def list_strategies() -> List[str]:
    strategies_dir = _CONFIG_DIR / "strategies"
    if not strategies_dir.exists():
        return []
    return sorted(p.stem for p in strategies_dir.glob("*.json"))

# ---------------------------------------------------------------------------
# Anchor Grammar Config
# ---------------------------------------------------------------------------

from pathlib import Path as _Path
import json as _json


def load_anchor_grammar() -> dict:
    """Load the NEURØISE anchor grammar configuration."""
    path = _Path(__file__).parent / "anchor_grammar.json"
    with path.open("r", encoding="utf-8") as f:
        return _json.load(f)


def get_anchor_grammar(archetype: str) -> dict:
    """Return anchor grammar for a normalized archetype name."""
    cfg = load_anchor_grammar()
    key = str(archetype or "").strip().lower()

    aliases = {
        "s": "sage",
        "s-01": "sage",
        "sage": "sage",
        "e": "explorer",
        "e-01": "explorer",
        "explorer": "explorer",
        "l": "lover",
        "l-01": "lover",
        "lover": "lover",
        "r": "rebel",
        "r-01": "rebel",
        "rebel": "rebel",
        "catalyst": "rebel",
        "v": "visionary",
        "v-01": "visionary",
        "visionary": "visionary",
        "mage": "visionary"
    }

    resolved = aliases.get(key, key)
    return cfg.get("archetypes", {}).get(resolved, {})
