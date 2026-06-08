from __future__ import annotations

from typing import Any, Dict, List, Optional


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def _normalize_label(value: Any) -> Optional[str]:
    """
    Deterministic archetype normalization.

    Important:
    Do NOT infer from free-text coherence_notes.
    Those notes can contain comparison words such as "SAGE" and corrupt the gate.
    """
    if value is None:
        return None

    text = str(value).strip().lower()
    if not text:
        return None

    text = text.replace("_", "-").replace("/", " ")

    # Exact / strong aliases first
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
        "rebel catalyst": "rebel",
        "rebel-catalyst": "rebel",

        "v": "visionary",
        "v-01": "visionary",
        "visionary": "visionary",
        "mage": "visionary",
        "visionary mage": "visionary",
        "visionary-mage": "visionary",
    }

    if text in aliases:
        return aliases[text]

    # Controlled contains fallback, still on explicit fields only
    if "r-01" in text or "rebel" in text or "catalyst" in text:
        return "rebel"
    if "v-01" in text or "visionary" in text or "mage" in text:
        return "visionary"
    if "s-01" in text or "sage" in text:
        return "sage"
    if "e-01" in text or "explorer" in text:
        return "explorer"
    if "l-01" in text or "lover" in text:
        return "lover"

    return None


def _detect_archetype(profile: Dict[str, Any], metadata: Dict[str, Any] | None = None) -> str:
    """
    Detect archetype from deterministic fields only.

    Priority:
    1. profile_id / case_id
    2. user_profile explicit archetype fields
    3. metadata.archetype_detected
    4. unknown

    We intentionally DO NOT inspect metadata.coherence_notes.
    """
    metadata = metadata or {}
    profile = profile or {}

    candidates: List[Any] = []

    # Top-level profile identifiers
    for key in ["profile_id", "case_id", "id", "name"]:
        candidates.append(profile.get(key))

    # Nested user profile fields
    user_profile = profile.get("user_profile", {})
    if isinstance(user_profile, dict):
        for key in [
            "profile_id",
            "case_id",
            "archetype",
            "primary_archetype",
            "archetype_id",
            "archetype_detected",
            "display_name",
        ]:
            candidates.append(user_profile.get(key))

    # Metadata explicit fields only
    for key in ["archetype_detected", "archetype", "primary_archetype", "archetype_id"]:
        candidates.append(metadata.get(key))

    for candidate in candidates:
        resolved = _normalize_label(candidate)
        if resolved:
            return resolved

    return "unknown"


def _extract_relevant_thread_text(sequence_thread: Any) -> str:
    """
    Inspect only generated creative content.

    Do NOT inspect:
    - forbidden_generic_substitutes
    - forbidden lists
    - why_it_matches_archetype

    Otherwise the gate creates false positives from the model's own forbidden terms.
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
            for key in [
                "prompt",
                "visual_prompt",
                "description",
                "thread_state",
                "mood_tags",
                "camera_hints",
            ]:
                parts.append(_flatten(scene.get(key)))
        else:
            parts.append(_flatten(scene))

    return " ".join(parts)


_FALLBACK_RULES = {
    "sage": {
        "fail_terms": [
            "cloud gap",
            "light beam",
            "beam of light",
            "pillar of light",
            "sacred",
            "spiritual",
            "ethereal glow",
            "fantasy glow",
            "horizon opening",
            "luminous path",
        ],
        "rationale": "Sage should express observation, hidden order and readable natural patterns, not atmospheric revelation or sacred light.",
    },
    "rebel": {
        "fail_terms": [
            "massive breaking wave",
            "breaking wave",
            "wave crest",
            "barrel wave",
            "barrel",
            "curling wave",
            "crashing wave",
            "spray explosion",
            "violent impact",
            "churning foam",
            "surf-video",
            "surf video",
            "surf energy",
            "storm wave",
        ],
        "rationale": "Rebel/Catalyst should express controlled tension, interruption and reconfiguration, not big-wave or surf-action clichés.",
    },
    "visionary": {
        "fail_terms": [
            "portal",
            "transcendent",
            "fractal",
            "bioluminescent anomaly",
            "bioluminescent",
            "infinite depth",
            "sci-fi",
            "magical",
            "mystical",
            "architectural network",
            "luminous network",
            "submerged city",
            "sacred geometry",
        ],
        "rationale": "Visionary/Mage should express latent natural order becoming visible, not fantasy, sci-fi or mystical glow.",
    },
}


def _rules_from_config(archetype: str) -> Dict[str, Any]:
    """
    Prefer anchor_grammar.json if available.
    Fall back to local rules if config loading fails.
    """
    fallback = _FALLBACK_RULES.get(archetype, {
        "fail_terms": [],
        "rationale": "No hard post-check rules configured for this archetype yet.",
    })

    try:
        from core.config import get_anchor_grammar

        grammar = get_anchor_grammar(archetype)
        if not grammar:
            return fallback

        fail_terms: List[str] = []
        fail_terms.extend(grammar.get("forbidden_thread_anchors", []))
        fail_terms.extend(grammar.get("forbidden_terms", []))
        fail_terms.extend(grammar.get("avoid_prompt_terms", []))

        # Keep order, remove duplicates
        seen = set()
        clean_terms = []
        for term in fail_terms:
            key = str(term).strip().lower()
            if key and key not in seen:
                seen.add(key)
                clean_terms.append(str(term))

        return {
            "fail_terms": clean_terms or fallback.get("fail_terms", []),
            "rationale": grammar.get("known_failure_mode") or fallback.get("rationale", ""),
        }

    except Exception:
        return fallback


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

    rule = _rules_from_config(archetype)
    fail_terms = rule.get("fail_terms", [])

    matched = [
        term
        for term in fail_terms
        if str(term).strip().lower() and str(term).strip().lower() in inspected_text
    ]

    return {
        "status": "fail" if matched else "pass",
        "archetype": archetype,
        "matched_bans": matched,
        "rationale": rule.get("rationale", ""),
    }
