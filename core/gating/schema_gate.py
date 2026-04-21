"""
Schema validation for NEURØISE inputs and outputs.

Validates JSON profiles and Director outputs against defined schemas.

Example:
    >>> is_valid, errors = validate_profile(profile)
    >>> if not is_valid:
    ...     print(errors)
"""

from typing import Any, Dict, List, Optional, Tuple
import json

from core.config import get_prefix_map, get_archetype_names, get_archetype


def _build_profile_schema() -> Dict[str, Any]:
    """Build PROFILE_SCHEMA dynamically from centralized config."""
    # Build regex char class from all prefix letters (sorted for stability)
    prefixes = sorted(set(get_prefix_map().keys()))
    prefix_chars = "".join(prefixes)
    case_id_pattern = f"^[{prefix_chars}]-\\d{{2}}$"

    # Build enum: canonical names + all aliases
    archetype_enum: List[str] = []
    for name in get_archetype_names():
        archetype_enum.append(name)
        archetype_enum.extend(get_archetype(name).get("aliases", []))

    return {
        "type": "object",
        "required": ["meta", "user_profile"],
        "properties": {
            "meta": {
                "type": "object",
                "required": ["case_id"],
                "properties": {
                    "case_id": {"type": "string", "pattern": case_id_pattern}
                }
            },
            "user_profile": {
                "type": "object",
                "required": ["primary_archetype", "music_seed"],
                "properties": {
                    "primary_archetype": {
                        "type": "string",
                        "enum": archetype_enum
                    },
                    "music_seed": {
                        "type": "object",
                        "required": ["top_genre", "bpm", "mood_tag"],
                        "properties": {
                            "top_genre": {"type": "string"},
                            "bpm": {"type": "integer", "minimum": 40, "maximum": 200},
                            "mood_tag": {"type": "string"}
                        }
                    },
                    "story_thread_hint": {"type": "string"}
                }
            }
        }
    }


# Lazy-initialized module-level reference (preserves backward compat)
PROFILE_SCHEMA: Optional[Dict[str, Any]] = None


def get_profile_schema() -> Dict[str, Any]:
    """Return the profile schema, building it on first call."""
    global PROFILE_SCHEMA
    if PROFILE_SCHEMA is None:
        PROFILE_SCHEMA = _build_profile_schema()
    return PROFILE_SCHEMA

# Schema per output Director
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["video_triptych", "ost_prompt"],
    "properties": {
        "video_triptych": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["scene_role", "prompt"],
                "properties": {
                    "scene_role": {
                        "type": "string",
                        "enum": ["start", "evolve", "end"]
                    },
                    "prompt": {
                        "type": "string",
                        "minLength": 20
                    },
                    "duration_hint": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 30
                    },
                    "mood_tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "camera_hints": {"type": "string"}
                }
            },
            "minItems": 3,
            "maxItems": 3
        },
        "ost_prompt": {
            "type": "object",
            "required": ["prompt"],
            "properties": {
                "prompt": {"type": "string", "minLength": 10},
                "genre": {"type": "string"},
                "bpm": {"type": "integer", "minimum": 40, "maximum": 200},
                "mood": {"type": "string"},
                "instruments_hint": {"type": "string"}
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "archetype_detected": {"type": "string"},
                "story_thread_used": {"type": "string"},
                "coherence_notes": {"type": "string"}
            }
        }
    }
}


class SchemaGate:
    """
    Validator per schema JSON.

    Implementazione leggera senza dipendenze esterne.
    Per validazione più robusta, usare jsonschema library.
    """

    def __init__(self, schema: Dict[str, Any]):
        """
        Inizializza con uno schema.

        Args:
            schema: JSON Schema dict
        """
        self.schema = schema

    def validate(self, data: Any) -> Tuple[bool, List[str]]:
        """
        Valida dati contro lo schema.

        Args:
            data: Dati da validare

        Returns:
            Tuple (is_valid, list of errors)
        """
        errors = []
        self._validate_value(data, self.schema, "", errors)
        return len(errors) == 0, errors

    def _validate_value(
        self,
        value: Any,
        schema: Dict[str, Any],
        path: str,
        errors: List[str]
    ) -> None:
        """Validazione ricorsiva."""

        # Type check
        expected_type = schema.get("type")
        if expected_type:
            if not self._check_type(value, expected_type):
                errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
                return

        # Enum check
        if "enum" in schema:
            if value not in schema["enum"]:
                errors.append(f"{path}: value '{value}' not in {schema['enum']}")

        # String constraints
        if expected_type == "string" and isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errors.append(f"{path}: string too short (min {schema['minLength']})")
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                errors.append(f"{path}: string too long (max {schema['maxLength']})")
            if "pattern" in schema:
                import re
                if not re.match(schema["pattern"], value):
                    errors.append(f"{path}: doesn't match pattern {schema['pattern']}")

        # Integer constraints
        if expected_type == "integer" and isinstance(value, int):
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(f"{path}: value {value} below minimum {schema['minimum']}")
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(f"{path}: value {value} above maximum {schema['maximum']}")

        # Object validation
        if expected_type == "object" and isinstance(value, dict):
            # Required properties
            for req in schema.get("required", []):
                if req not in value:
                    errors.append(f"{path}: missing required property '{req}'")

            # Validate properties
            props_schema = schema.get("properties", {})
            for key, val in value.items():
                if key in props_schema:
                    new_path = f"{path}.{key}" if path else key
                    self._validate_value(val, props_schema[key], new_path, errors)

        # Array validation
        if expected_type == "array" and isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errors.append(f"{path}: array too short (min {schema['minItems']})")
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                errors.append(f"{path}: array too long (max {schema['maxItems']})")

            # Validate items
            items_schema = schema.get("items")
            if items_schema:
                for i, item in enumerate(value):
                    self._validate_value(item, items_schema, f"{path}[{i}]", errors)

    def _check_type(self, value: Any, expected: str) -> bool:
        """Verifica tipo JSON."""
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
            "null": type(None)
        }
        return isinstance(value, type_map.get(expected, object))


# Convenience functions

def validate_profile(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Valida un profilo NoNoise.

    Args:
        profile: Profilo da validare

    Returns:
        (is_valid, errors)
    """
    gate = SchemaGate(get_profile_schema())
    return gate.validate(profile)


def validate_output(output: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Valida un output del Director.

    Args:
        output: Output da validare

    Returns:
        (is_valid, errors)
    """
    gate = SchemaGate(OUTPUT_SCHEMA)
    return gate.validate(output)


def load_and_validate_profile(path: str) -> Tuple[Optional[Dict], List[str]]:
    """
    Carica e valida un profilo da file.

    Args:
        path: Path al file JSON

    Returns:
        (profile or None, errors)
    """
    try:
        with open(path, 'r') as f:
            profile = json.load(f)
        is_valid, errors = validate_profile(profile)
        return profile if is_valid else None, errors
    except json.JSONDecodeError as e:
        return None, [f"Invalid JSON: {e}"]
    except FileNotFoundError:
        return None, [f"File not found: {path}"]
