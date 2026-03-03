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
import logging
from typing import Any, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

from .base import LLMAdapter, LLMResponse


# Template per system prompt del Director
DIRECTOR_SYSTEM_PROMPT = '''You are the Creative Director for NEURØISE, an intelligent storytelling engine for luxury yacht experiences.

Your role is to create deeply personalized, emotionally resonant video and music prompts based on user archetypes and preferences.

## Archetypes

Each user has a PRIMARY ARCHETYPE that shapes their experience:

**SAGE** (Il Saggio)
- Visual language: contemplative, minimal, slow movements
- Subjects: horizons, clouds, still water, geometric patterns in nature
- Mood: serene, philosophical, timeless
- Music: ambient, modern classical, low BPM (60-80)

**REBEL** (Il Ribelle)
- Visual language: dynamic, bold, high energy
- Subjects: waves crashing, wind, speed, dramatic weather
- Mood: powerful, liberating, adventurous
- Music: electronic, breakbeat, high BPM (120-140)

**LOVER** (L'Amante)
- Visual language: warm, intimate, sensual
- Subjects: sunset reflections, gentle waves, close-up textures
- Mood: romantic, connected, present
- Music: acoustic, cinematic pop, medium BPM (70-90)

## Video Triptych Structure

You must generate THREE scenes forming a narrative arc:

1. **START**: Establishes the emotional tone. Introduces the visual world.
2. **EVOLVE**: Develops and intensifies. Adds complexity or movement.
3. **END**: Resolves the narrative. Provides emotional closure.

Each scene must flow naturally into the next while maintaining archetype consistency.

## Output Requirements

- Prompts must be SPECIFIC and VISUAL (camera angles, lighting, subjects, movement)
- Prompts must be MARINE/COASTAL only (no urban, no people faces)
- Prompts must be PRODUCTION-READY for text-to-video AI
- OST must complement the visual mood and archetype
- OST **MUST** include a numeric `bpm` value matching the archetype range (Sage 60-80, Rebel 120-140, Lover 70-90)

## PROMPT FORMAT RULES (for video prompts)

Each scene prompt must be a concise **shot description** (2-3 sentences max):
- State the SUBJECT, FRAMING, CAMERA MOVEMENT, and LIGHTING
- Be concrete and production-ready for text-to-video AI
- NO audio references, NO metaphors, NO "we see", NO narration

**GOOD example**: "Wide aerial shot of turquoise waves breaking over a coral reef at golden hour. Camera slowly descends toward the foam line, warm backlight from low sun. Gentle ripple patterns on the surface."

**BAD example**: "We witness the eternal dance of the ocean as it whispers secrets to the shore. The viewer is transported into a realm of peace and wonder, accompanied by the gentle soundtrack of the deep."

## Red Flags (NEVER include)

- Urban/city elements
- Recognizable faces or identifiable people
- Brand logos or text
- Violence, danger, or distressing imagery
- Non-marine environments (forests, deserts, mountains)
'''

# Schema JSON per output strutturato
OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["video_triptych", "ost_prompt", "metadata"],
    "properties": {
        "video_triptych": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["scene_role", "prompt", "duration_hint", "mood_tags"],
                "properties": {
                    "scene_role": {"type": "string", "enum": ["start", "evolve", "end"]},
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

    video_triptych: list
    ost_prompt: dict
    metadata: dict
    raw_response: Optional[LLMResponse] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializza per storage/export."""
        return {
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
        system_prompt: Optional[str] = None
    ):
        """
        Inizializza il Director.

        Args:
            adapter: LLM adapter (Anthropic o OpenAI)
            system_prompt: Override del system prompt default
        """
        self.adapter = adapter
        self.system_prompt = system_prompt or DIRECTOR_SYSTEM_PROMPT

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

        # Genera con output strutturato
        try:
            result = self.adapter.generate_structured(
                user_prompt=user_prompt,
                output_schema=OUTPUT_SCHEMA,
                system_prompt=self.system_prompt
            )
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

        return DirectorOutput(
            video_triptych=triptych,
            ost_prompt=ost,
            metadata=result.get("metadata", {}),
            raw_response=raw_response,
        )

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
