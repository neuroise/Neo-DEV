"""
Director LLM - Il "regista creativo" di NEURØISE.

Il Director riceve un profilo utente e genera:
1. Video Triptych (3 scene: start → evolve → end)
2. OST Prompt (colonna sonora)

Allineato con Framework NoNoise v2: il Director è il cuore del Reasoning Layer.

Example:
    >>> director = Director(adapter=AnthropicAdapter(config))
    >>> output = director.generate(profile)
    >>> print(output["video_triptych"][0]["prompt"])
"""

import json
import time
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from .base import LLMAdapter, LLMResponse
from core.config import load_archetypes


# ---------------------------------------------------------------------------
# Dynamic system-prompt builder
# ---------------------------------------------------------------------------

_PROMPT_INTRO = '''You are the Creative Director for NEURØISE, an intelligent storytelling engine for luxury yacht experiences.

Your role is to create deeply personalized, emotionally resonant video and music prompts based on user archetypes and preferences.

## Archetypes

Each user has a PRIMARY ARCHETYPE that shapes their experience:

'''

_PROMPT_TRIPTYCH = '''## Video Triptych Structure

You must generate THREE scenes forming a narrative arc:

1. **START**: Establishes the emotional tone. Introduces the visual world.
2. **EVOLVE**: Develops and intensifies. Adds complexity or movement.
3. **END**: Resolves the narrative. Provides emotional closure.

Each scene must flow naturally into the next while maintaining archetype consistency.

'''

_PROMPT_SEQUENCE_THREAD = """## Continuity Thread Rules

Before writing the three scene prompts, define ONE concrete continuity thread.

The continuity thread is a visible physical anchor that must appear in START, EVOLVE and END.
It must be something a camera can actually see.

Allowed examples:
- a thin foam line
- a rock opening
- a current path
- a shadow edge
- a reflection mark
- a sand trace
- a cloud gap
- a repeated natural geometry

Forbidden as continuity anchors:
- ocean in general
- waves in general
- light in general
- energy
- possibility
- serenity
- emotion
- atmosphere
- beauty
- scale

Each scene must include a `thread_state` field explaining how the same anchor is physically visible and how it changes from the previous scene.

The three scenes must not be three separate mood boards. They must form a visible micro-story around the same continuity anchor.

"""

_PROMPT_ARCHETYPE_THREAD_CONSTRAINTS = """## Archetype-Specific Continuity Thread Constraints

The continuity anchor must not only be physical. It must also be appropriate to the primary archetype.

### SAGE
Use: subtle readable patterns, shadow edges, submerged contours, fine ripple alignment, a small natural detail becoming legible.
Avoid: sacred beams, spiritual light, fantasy glow, cloud gap as the main solution, generic wisdom symbolism, infinite horizon as the only idea.

### EXPLORER
Use: route, threshold, passage, distant land becoming reachable, current path, coastal marker, opening in rock.
Avoid: generic drone tourism, empty open sea with no navigational sign, postcard coastline without discovery logic.

### LOVER
Use: contact line, tide edge, two surfaces touching, shell or trace introduced early, water softly altering sand, paired reflections.
Avoid: generic sunset romance, pastel beach cliché, abstract warmth without physical contact.

### REBEL / CATALYST
Use: broken pattern, crossing current, foam fracture, sudden deviation, a calm system being visibly reconfigured.
Avoid: massive crashing wave, barrel wave, violent impact, spray explosion, churning foam as the main idea, surf-video energy.

### VISIONARY / MAGE
Use: natural geometry, current map, alignment of small light points, latent structure becoming visible, pattern emerging from real water behavior.
Avoid: portal, transcendent glow, fractal fantasy, bioluminescent anomaly, infinite depth, sci-fi/mystical light effects.

Generator discipline:
- Do not write abstract phrases such as "sense of energy", "endless possibility", "transcendent scale", or "evokes emotion" inside video prompts.
- If the camera cannot see it, it does not belong in the visual prompt.
- Prefer physical transformation over poetic interpretation.

"""

_PROMPT_OUTPUT_REQS_TEMPLATE = '''## Output Requirements

- Prompts must be SPECIFIC and VISUAL (camera angles, lighting, subjects, movement)
- Prompts must be MARINE/COASTAL only (no urban, no people faces)
- Prompts must be PRODUCTION-READY for text-to-video AI
- OST must complement the visual mood and archetype
- OST **MUST** include a numeric `bpm` value matching the archetype range ({bpm_summary})

'''

_PROMPT_FORMAT_RULES = '''## PROMPT FORMAT RULES (for video prompts)

Each scene prompt must be a concise **shot description** (2-3 sentences max):
- State the SUBJECT, FRAMING, CAMERA MOVEMENT, and LIGHTING
- Be concrete and production-ready for text-to-video AI
- NO audio references, NO metaphors, NO "we see", NO narration

**GOOD example**: "Wide aerial shot of turquoise waves breaking over a coral reef at golden hour. Camera slowly descends toward the foam line, warm backlight from low sun. Gentle ripple patterns on the surface."

**BAD example**: "We witness the eternal dance of the ocean as it whispers secrets to the shore. The viewer is transported into a realm of peace and wonder, accompanied by the gentle soundtrack of the deep."

'''

_PROMPT_RED_FLAGS = '''## Red Flags (NEVER include)

- Urban/city elements
- Recognizable faces or identifiable people
- Brand logos or text
- Violence, danger, or distressing imagery
- Non-marine environments (forests, deserts, mountains)
'''


def _build_bpm_summary(archetypes: Dict[str, Any]) -> str:
    """Build inline BPM summary like 'Sage 60-80, Lover 70-90, ...'."""
    parts = []
    for data in archetypes.values():
        lo, hi = data["bpm_range"]
        parts.append(f"{data['display_name']} {lo}-{hi}")
    return ", ".join(parts)


def _build_archetype_block_default(name: str, data: Dict[str, Any]) -> str:
    """Full block per archetype: visual language, subjects, mood, music + BPM."""
    lo, hi = data["bpm_range"]
    lines = [
        f"**{data['display_name'].upper()}** ({data['display_name_it']})",
        f"- Visual language: {', '.join(data['visual_keywords'])}",
        f"- Subjects: {', '.join(data['subjects'])}",
        f"- Mood: {', '.join(data['mood'])}",
        f"- Music: {', '.join(data['music_keywords'])}, BPM ({lo}-{hi})",
    ]
    return "\n".join(lines)


def _build_archetype_block_concise(name: str, data: Dict[str, Any]) -> str:
    """One-liner: name + 2 keywords + BPM."""
    lo, hi = data["bpm_range"]
    kw = data["visual_keywords"][:2]
    return f"{data['display_name'].upper()} ({data['display_name_it']}): {', '.join(kw)} | {lo}-{hi} BPM"


def _build_archetype_block_detailed(name: str, data: Dict[str, Any]) -> str:
    """Extended block with camera and lighting hints."""
    lo, hi = data["bpm_range"]
    lines = [
        f"**{data['display_name'].upper()}** ({data['display_name_it']})",
        f"- Visual language: {', '.join(data['visual_keywords'])}",
        f"- Subjects: {', '.join(data['subjects'])}",
        f"- Mood: {', '.join(data['mood'])}",
        f"- Music: {', '.join(data['music_keywords'])}, BPM ({lo}-{hi})",
        f"- Camera: {', '.join(data['camera'])}",
        f"- Lighting: {', '.join(data['lighting'])}",
    ]
    return "\n".join(lines)


def build_director_system_prompt(
    style: str = "default",
    brand_id: str = None,
    strategy_id: str = None,
) -> str:
    """Build the Director system prompt dynamically from config.

    Args:
        style: One of "default", "concise", "detailed".
        brand_id: Optional brand config to append as rules section.
        strategy_id: Optional strategy config to append as campaign section.

    Returns:
        Complete system prompt string.
    """
    cfg = load_archetypes()
    archetypes = cfg["archetypes"]

    builders = {
        "default": _build_archetype_block_default,
        "concise": _build_archetype_block_concise,
        "detailed": _build_archetype_block_detailed,
    }
    builder = builders.get(style)
    if builder is None:
        raise ValueError(f"Unknown prompt style: {style!r}. Expected one of {list(builders)}")

    archetype_blocks = []
    for name, data in archetypes.items():
        archetype_blocks.append(builder(name, data))
    archetype_section = "\n\n".join(archetype_blocks) + "\n\n"

    bpm_summary = _build_bpm_summary(archetypes)
    output_reqs = _PROMPT_OUTPUT_REQS_TEMPLATE.format(bpm_summary=bpm_summary)

    prompt = (
        _PROMPT_INTRO
        + archetype_section
        + _PROMPT_TRIPTYCH
        + _PROMPT_SEQUENCE_THREAD
        + _PROMPT_ARCHETYPE_THREAD_CONSTRAINTS
        + output_reqs
        + _PROMPT_FORMAT_RULES
        + _PROMPT_RED_FLAGS
    )

    if brand_id:
        from core.config import load_brand
        brand = load_brand(brand_id)
        rules = brand.get("rules", {})
        prompt += "\n## Brand Rules\n"
        prompt += f"- Environment: {rules.get('environment', 'marine_coastal_only')}\n"
        if rules.get("forbidden_subjects"):
            prompt += f"- Forbidden: {', '.join(rules['forbidden_subjects'])}\n"
        prompt += f"- Tone: {rules.get('tone', 'luxury_premium')}\n"

    if strategy_id and strategy_id != "default":
        from core.config import load_strategy
        strategy = load_strategy(strategy_id)
        mods = strategy.get("prompt_modifiers", {})
        prompt += f"\n## Campaign Strategy: {strategy.get('name', strategy_id)}\n"
        prompt += f"- Intent: {strategy.get('intent', '')}\n"
        if mods.get("emphasis"):
            prompt += f"- Emphasis: {', '.join(mods['emphasis'])}\n"
        if mods.get("camera_preference"):
            prompt += f"- Camera preference: {mods['camera_preference']}\n"
        if mods.get("pacing_hint"):
            prompt += f"- Pacing: {mods['pacing_hint']}\n"

    return prompt


# Backward-compatible alias — tests and imports use this name
DIRECTOR_SYSTEM_PROMPT = build_director_system_prompt()

# Schema JSON per output strutturato
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["sequence_thread", "video_triptych", "ost_prompt", "metadata"],
    "properties": {
        "sequence_thread": {
            "type": "object",
            "required": ["anchor", "physical_description", "transformation_rule", "why_it_matches_archetype", "forbidden_generic_substitutes"],
            "properties": {
                "anchor": {"type": "string", "minLength": 5},
                "physical_description": {"type": "string", "minLength": 20},
                "transformation_rule": {"type": "string", "minLength": 20},
                "why_it_matches_archetype": {"type": "string", "minLength": 20},
                "forbidden_generic_substitutes": {"type": "array", "items": {"type": "string"}}
            }
        },
        "video_triptych": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["scene_role", "thread_state", "prompt", "duration_hint", "mood_tags"],
                "properties": {
                    "scene_role": {"type": "string", "enum": ["start", "evolve", "end"]},
                    "thread_state": {"type": "string", "minLength": 20},
                    "prompt": {"type": "string", "minLength": 50, "maxLength": 500},
                    "duration_hint": {"type": "integer", "minimum": 3, "maximum": 10},
                    "mood_tags": {"type": "array", "items": {"type": "string"}},
                    "camera_hints": {"type": "string"}
                }
            },
            "minItems": 3,
            "maxItems": 3
        },
        "ost_prompt": {
            "type": "object",
            "required": ["prompt", "genre", "bpm", "mood"],
            "properties": {
                "prompt": {"type": "string"},
                "genre": {"type": "string"},
                "bpm": {"type": "integer"},
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


@dataclass
class DirectorOutput:
    """Output strutturato del Director."""

    sequence_thread: dict
    video_triptych: list
    ost_prompt: dict
    metadata: dict
    raw_response: Optional[LLMResponse] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializza per storage/export."""
        return {
            "sequence_thread": self.sequence_thread,
            "video_triptych": self.video_triptych,
            "ost_prompt": self.ost_prompt,
            "metadata": self.metadata
        }

    def get_scene(self, role: str) -> Optional[Dict[str, Any]]:
        """Ottieni una scena specifica per ruolo."""
        for scene in self.video_triptych:
            if scene.get("scene_role") == role:
                return scene
        return None

    @property
    def start_scene(self) -> Optional[Dict[str, Any]]:
        return self.get_scene("start")

    @property
    def evolve_scene(self) -> Optional[Dict[str, Any]]:
        return self.get_scene("evolve")

    @property
    def end_scene(self) -> Optional[Dict[str, Any]]:
        return self.get_scene("end")

    @property
    def all_prompts(self) -> list:
        """Lista di tutti i prompt video."""
        return [s["prompt"] for s in self.video_triptych]


class Director:
    """
    Il Director genera contenuti creativi personalizzati.

    Ruolo nel Framework NoNoise: cuore del Reasoning Layer.
    Riceve profili, produce prompt video/musica.

    Attributes:
        adapter: LLM adapter da usare
        system_prompt: System prompt custom (opzionale)
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        system_prompt: Optional[str] = None,
        brand_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
    ):
        self.adapter = adapter
        self.brand_id = brand_id
        self.strategy_id = strategy_id
        if system_prompt:
            self.system_prompt = system_prompt
        else:
            self.system_prompt = build_director_system_prompt(
                brand_id=brand_id, strategy_id=strategy_id
            )

    def generate(
        self,
        profile: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> DirectorOutput:
        """
        Genera video triptych e OST prompt per un profilo.

        Args:
            profile: Profilo utente (formato JSON NoNoise)
            context: Contesto aggiuntivo (scenario, ora, etc.) - per Fase 2

        Returns:
            DirectorOutput con tutti i contenuti generati

        Example:
            >>> output = director.generate(profile)
            >>> print(output.start_scene["prompt"])
        """
        # Costruisci il prompt utente
        user_prompt = self._build_user_prompt(profile, context)

        anchor_grammar_prompt = self._build_anchor_grammar_prompt(profile)
        if anchor_grammar_prompt:
            user_prompt += "\n\n" + anchor_grammar_prompt

        # Genera con output strutturato
        try:
            last_error = None
            result = None

            for attempt in range(3):
                try:
                    result = self.adapter.generate_structured(
                        user_prompt=user_prompt,
                        output_schema=OUTPUT_SCHEMA,
                        system_prompt=self.system_prompt
                    )
                    break
                except Exception as retry_error:
                    last_error = retry_error
                    error_text = str(retry_error).lower()
                    is_transient = (
                        "503" in error_text
                        or "unavailable" in error_text
                        or "high demand" in error_text
                        or "rate limit" in error_text
                        or "temporarily" in error_text
                    )

                    if not is_transient or attempt == 2:
                        raise

                    sleep_seconds = 4 * (attempt + 1)
                    logger.warning(
                        "Transient LLM provider error on attempt %s/3: %s. Retrying in %ss",
                        attempt + 1,
                        retry_error,
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)

            if result is None:
                raise last_error or ValueError("Structured generation failed without result")

            logger.info(f"Structured result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")

            return self._parse_result(result, profile=profile)

        except Exception as e:
            logger.warning(f"Structured generation failed: {e}")
            # Fallback: genera non strutturato e parsa
            try:
                response = self.adapter.generate(
                    user_prompt=user_prompt + "\n\nRespond with valid JSON only.",
                    system_prompt=self.system_prompt
                )
                logger.info(f"Fallback response length: {len(response.content)}, content[:200]: {response.content[:200]}")

                parsed = response.parse_json()
                if parsed:
                    logger.info(f"Fallback parsed keys: {list(parsed.keys())}")
                    return self._parse_result(parsed, raw_response=response, profile=profile)
                else:
                    logger.error(f"Fallback parse_json returned None")
            except Exception as e2:
                logger.error(f"Fallback also failed: {e2}")

            raise ValueError(f"Director failed to generate valid output: {e}")

    @staticmethod
    def _parse_result(
        result: Dict[str, Any],
        raw_response: Optional[LLMResponse] = None,
        profile: Optional[Dict[str, Any]] = None,
    ) -> "DirectorOutput":
        """Extract DirectorOutput from a parsed JSON dict, handling key variations."""
        # Try to find video_triptych in various locations
        triptych = (
            result.get("video_triptych")
            or result.get("triptych")
            or result.get("scenes")
            or result.get("video_scenes")
        )

        # Check if model wrapped output in an extra key
        if triptych is None:
            for v in result.values():
                if isinstance(v, list) and len(v) == 3 and isinstance(v[0], dict):
                    if any(k in v[0] for k in ("prompt", "scene_role", "role")):
                        triptych = v
                        break

        if not triptych:
            raise KeyError(f"video_triptych not found in keys: {list(result.keys())}")

        # Normalize scene_role field
        for scene in triptych:
            if "role" in scene and "scene_role" not in scene:
                scene["scene_role"] = scene.pop("role")

        ost = (
            result.get("ost_prompt")
            or result.get("ost")
            or result.get("music_prompt")
            or result.get("soundtrack")
            or {}
        )

        # BPM fallback: if LLM omitted bpm, pull from profile music_seed
        if ost and not ost.get("bpm") and profile:
            user_profile = profile.get("user_profile", profile)
            fallback_bpm = user_profile.get("music_seed", {}).get("bpm")
            if fallback_bpm is not None:
                ost["bpm"] = fallback_bpm
                logger.warning("BPM missing from LLM output, using profile fallback: %s", fallback_bpm)

        metadata = result.get("metadata", {})

        sequence_thread = (
            result.get("sequence_thread")
            or result.get("continuity_thread")
            or result.get("thread")
            or {}
        )

        if not sequence_thread and isinstance(metadata, dict) and metadata.get("story_thread_used"):
            sequence_thread = {
                "anchor": metadata.get("story_thread_used"),
                "physical_description": metadata.get("story_thread_used"),
                "transformation_rule": "Not provided by model.",
                "why_it_matches_archetype": metadata.get("coherence_notes", "Not provided by model."),
                "forbidden_generic_substitutes": []
            }

        try:
            from core.llm.archetype_gate import evaluate_archetype_gate
            metadata["archetype_gate"] = evaluate_archetype_gate(
                profile=profile or {},
                sequence_thread=sequence_thread,
                triptych=triptych,
                metadata=metadata,
            )
        except Exception as gate_error:
            metadata["archetype_gate"] = {
                "status": "error",
                "error": str(gate_error),
            }

        return DirectorOutput(
            sequence_thread=sequence_thread,
            video_triptych=triptych,
            ost_prompt=ost,
            metadata=metadata,
            raw_response=raw_response,
        )


    @staticmethod
    def _infer_anchor_archetype(profile: Dict[str, Any]) -> str:
        """Infer normalized archetype key from profile content."""
        try:
            text = json.dumps(profile, ensure_ascii=False).lower()
        except Exception:
            text = str(profile).lower()

        if "s-01" in text or "sage" in text:
            return "sage"
        if "e-01" in text or "explorer" in text:
            return "explorer"
        if "l-01" in text or "lover" in text:
            return "lover"
        if "r-01" in text or "rebel" in text or "catalyst" in text:
            return "rebel"
        if "v-01" in text or "visionary" in text or "mage" in text:
            return "visionary"

        return "unknown"

    @staticmethod
    def _build_anchor_grammar_prompt(profile: Dict[str, Any]) -> str:
        """Build an archetype-specific anchor grammar instruction block."""
        try:
            from core.config import get_anchor_grammar, load_anchor_grammar
        except Exception:
            return ""

        archetype = Director._infer_anchor_archetype(profile)
        grammar = get_anchor_grammar(archetype)

        if not grammar:
            return ""

        global_cfg = {}
        try:
            global_cfg = load_anchor_grammar().get("global_principles", {})
        except Exception:
            global_cfg = {}

        allowed_anchors = grammar.get("allowed_thread_anchors", [])
        top_names = grammar.get("top_3_anchors", [])

        # Prefer top anchors for the current test phase.
        if top_names:
            allowed_anchors = [
                a for a in allowed_anchors
                if a.get("name") in top_names
            ] or allowed_anchors

        lines = []
        lines.append("## Archetype Anchor Grammar")
        lines.append("")
        lines.append(f"Primary archetype: {archetype.upper()}")
        lines.append("")
        lines.append("Use the following anchor grammar as a hard creative constraint.")
        lines.append("You must select exactly ONE continuity anchor from the provided list.")
        lines.append("Do not invent a new anchor.")
        lines.append("The selected anchor name must appear exactly in `sequence_thread.anchor`.")
        lines.append("")
        lines.append("The anchor must drive START, EVOLVE and END.")
        lines.append("Do not turn the three scenes into separate mood boards.")
        lines.append("Do not use generic ocean, generic waves, generic light, generic energy, generic beauty or generic atmosphere as the anchor.")
        lines.append("")

        if grammar.get("reading"):
            lines.append("### Archetype reading")
            lines.append(grammar["reading"])
            lines.append("")

        if grammar.get("anchor_principles"):
            lines.append("### Anchor principles")
            for item in grammar["anchor_principles"]:
                lines.append(f"- {item}")
            lines.append("")

        if allowed_anchors:
            lines.append("### Allowed continuity anchors")
            for a in allowed_anchors:
                lines.append(f"- name: {a.get('name')}")
                lines.append(f"  physical_description: {a.get('physical_description')}")
                lines.append(f"  start_state: {a.get('start_state')}")
                lines.append(f"  evolve_state: {a.get('evolve_state')}")
                lines.append(f"  end_state: {a.get('end_state')}")
                lines.append(f"  transformation_type: {a.get('transformation_type')}")
                if a.get("generator_prompt_seed"):
                    lines.append(f"  generator_prompt_seed: {a.get('generator_prompt_seed')}")
                if a.get("risk_level"):
                    lines.append(f"  risk_level: {a.get('risk_level')}")
            lines.append("")

        if grammar.get("preferred_transformations"):
            lines.append("### Preferred transformations")
            for item in grammar["preferred_transformations"]:
                lines.append(f"- {item}")
            lines.append("")

        forbidden = []
        forbidden.extend(grammar.get("forbidden_thread_anchors", []))
        forbidden.extend(grammar.get("forbidden_terms", []))
        forbidden.extend(global_cfg.get("final_prompt_forbidden_terms", []))

        if forbidden:
            # Deduplicate preserving order
            seen = set()
            clean_forbidden = []
            for item in forbidden:
                key = str(item).lower()
                if key not in seen:
                    seen.add(key)
                    clean_forbidden.append(item)

            lines.append("### Forbidden anchors and terms")
            for item in clean_forbidden:
                lines.append(f"- {item}")
            lines.append("")

        if grammar.get("preferred_prompt_terms"):
            lines.append("### Preferred final prompt vocabulary")
            lines.append("Use these terms or equivalent physical language when appropriate:")
            for item in grammar["preferred_prompt_terms"]:
                lines.append(f"- {item}")
            lines.append("")

        if grammar.get("avoid_prompt_terms"):
            lines.append("### Avoid in final video prompts")
            lines.append("Do not use these terms in final scene prompts or mood tags:")
            for item in grammar["avoid_prompt_terms"]:
                lines.append(f"- {item}")
            lines.append("")

        if grammar.get("known_failure_mode"):
            lines.append("### Known failure mode to avoid")
            lines.append(grammar["known_failure_mode"])
            lines.append("")

        lines.append("### Final instruction")
        lines.append("The video prompts must describe only visible, filmable, physically grounded content.")
        lines.append("Avoid abstract interpretation inside the final scene prompts.")
        lines.append("If an idea cannot be seen by a camera, do not put it in the scene prompt.")
        lines.append("")

        return "\n".join(lines)


    def _build_user_prompt(
        self,
        profile: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Costruisce il prompt utente dal profilo."""

        # Estrai info dal profilo NoNoise
        user_profile = profile.get("user_profile", profile)
        meta = profile.get("meta", {})

        archetype = user_profile.get("primary_archetype", "sage")
        music_seed = user_profile.get("music_seed", {})
        story_thread = user_profile.get("story_thread_hint", "")

        prompt = f"""## User Profile

**Case ID**: {meta.get('case_id', 'unknown')}
**Primary Archetype**: {archetype.upper()}

**Music Preferences**:
- Top Genre: {music_seed.get('top_genre', 'ambient')}
- BPM: {music_seed.get('bpm', 70)}
- Mood Tag: {music_seed.get('mood_tag', 'contemplative')}

**Story Thread Hint**: {story_thread or 'none specified'}

## Your Task

Generate a complete creative package:
1. Video Triptych (3 scenes: start, evolve, end)
2. OST Prompt (matching the archetype and mood)

Ensure:
- All scenes maintain archetype consistency
- The triptych tells a coherent visual story
- The OST complements the visual narrative
- The OST includes a numeric **bpm** field (MANDATORY — use {music_seed.get('bpm', 70)} BPM as reference)
- All content is marine/coastal themed
- Prompts are specific enough for AI video generation

Output valid JSON matching the required schema."""

        # Aggiungi contesto se presente (Fase 2)
        if context:
            context_str = f"""

## Temporal Context (Simulation)

- Journey Day: {context.get('journey_day', 'unknown')}
- Time of Day: {context.get('time_of_day', 'unknown')}
- Weather: {context.get('weather', 'calm')}
- Location: {context.get('location_type', 'open_sea')}

Adapt your prompts to reflect this context naturally."""
            prompt += context_str

        return prompt

    def generate_batch(
        self,
        profiles: list,
        context: Optional[Dict[str, Any]] = None
    ) -> list:
        """
        Genera per multipli profili.

        Args:
            profiles: Lista di profili
            context: Contesto condiviso (opzionale)

        Returns:
            Lista di DirectorOutput
        """
        results = []
        for profile in profiles:
            try:
                output = self.generate(profile, context)
                results.append({
                    "profile_id": profile.get("meta", {}).get("case_id", "unknown"),
                    "output": output,
                    "success": True
                })
            except Exception as e:
                results.append({
                    "profile_id": profile.get("meta", {}).get("case_id", "unknown"),
                    "error": str(e),
                    "success": False
                })
        return results
