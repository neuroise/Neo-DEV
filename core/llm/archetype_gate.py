from __future__ import annotations

from typing import Any, Dict, List


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def _detect_archetype(profile: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> str:
    metadata = metadata or {}
    combined = f"{_flatten(profile)} {_flatten(metadata)}".lower()

    if "s-01" in combined or "sage" in combined:
        return "sage"
    if "e-01" in combined or "explorer" in combined:
        return "explorer"
    if "l-01" in combined or "lover" in combined:
        return "lover"
    if "r-01" in combined or "rebel" in combined or "catalyst" in combined:
        return "rebel"
    if "v-01" in combined or "visionary" in combined or "mage" in combined:
        return "visionary"

    return "unknown"


def _extract_relevant_thread_text(sequence_thread: Any) -> str:
    """
    Inspect only generated creative content.
    Do NOT inspect forbidden_generic_substitutes, otherwise the gate creates false positives.
    """
    if not isinstance(sequence_thread, dict):
        return _flatten(sequence_thread)

    allowed_keys = [
        "anchor",
        "physical_description",
        "transformation_rule",
    ]

    return " ".join(_flatten(sequence_thread.get(k)) for k in allowed_keys)


def _extract_relevant_scene_text(triptych: List[Any]) -> str:
    parts = []

    for scene in triptych or []:
        if isinstance(scene, dict):
            for key in ["prompt", "visual_prompt", "description", "thread_state", "mood_tags", "camera_hints"]:
                parts.append(_flatten(scene.get(key)))
        else:
            parts.append(_flatten(scene))

    return " ".join(parts)


_RULES = {
    "sage": {
        "fail_terms": [
            "cloud gap",
            "light beam",
            "beam of light",
            "sacred",
            "spiritual",
            "ethereal glow",
            "fantasy glow",
            "horizon opening",
        ],
        "rationale": "Sage should express observation, hidden order and readable natural patterns, not atmospheric revelation or sacred light.",
    },
    "rebel": {
        "fail_terms": [
            "wave crest",
            "breaking wave",
            "barrel",
            "curl",
            "crash",
            "crashing",
            "spray explosion",
            "violent impact",
            "white water",
            "churning foam",
            "surf-video",
            "surf video",
        ],
        "rationale": "Rebel/Catalyst should express pattern rupture and visible reconfiguration, not big-wave or surf-energy clichés.",
    },
    "visionary": {
        "fail_terms": [
            "portal",
            "transcendent",
            "fractal",
            "bioluminescent anomaly",
            "infinite depth",
            "sci-fi",
            "magical",
            "mystical",
            "architectural network",
        ],
        "rationale": "Visionary/Mage should express latent natural order becoming visible, not fantasy, sci-fi or mystical glow.",
    },
}


def evaluate_archetype_gate(
    profile: Dict[str, Any],
    sequence_thread: Any,
    triptych: List[Any],
    metadata: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    archetype = _detect_archetype(profile, metadata)

    inspected_text = (
        _extract_relevant_thread_text(sequence_thread)
        + " "
        + _extract_relevant_scene_text(triptych)
    ).lower()

    rule = _RULES.get(archetype)
    if not rule:
        return {
            "status": "pass",
            "archetype": archetype,
            "matched_bans": [],
            "rationale": "No hard post-check rules configured for this archetype yet.",
        }

    matched = [term for term in rule["fail_terms"] if term in inspected_text]

    return {
        "status": "fail" if matched else "pass",
        "archetype": archetype,
        "matched_bans": matched,
        "rationale": rule["rationale"],
    }
