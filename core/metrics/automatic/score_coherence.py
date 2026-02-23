"""
SCORE-based Narrative Coherence metric.

M_AUTO_11: score_narrative_coherence

Based on SCORE paper (2025) - uses knowledge graph-like entity tracking
to measure narrative coherence across scenes.

The SCORE approach tracks:
1. Entity persistence (same subjects across scenes)
2. Temporal consistency (logical progression)
3. Causal relationships (actions/consequences)

Simplified implementation using NLP entity extraction.
"""

from typing import Any, Dict, List, Set, Tuple
import re

# Try to import spaCy for NER
try:
    import spacy
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False


# Semantic roles for marine/visual domain
VISUAL_ENTITIES = {
    # Natural elements
    "sky", "sun", "moon", "stars", "clouds", "horizon",
    "ocean", "sea", "water", "waves", "tide", "current",
    # Objects
    "boat", "yacht", "sail", "ship", "vessel",
    "rock", "cliff", "shore", "beach", "island",
    # Light/atmosphere
    "light", "shadow", "reflection", "glow", "mist",
    # Camera/visual
    "camera", "shot", "frame", "scene"
}

# Temporal/progression markers
PROGRESSION_MARKERS = {
    "start": ["begins", "opens", "starts", "initial", "first", "establishing"],
    "evolve": ["develops", "builds", "intensifies", "grows", "transforms", "shifts"],
    "end": ["concludes", "resolves", "fades", "settles", "final", "closes"]
}


class ScoreCoherence:
    """
    Computes SCORE-based narrative coherence.

    Tracks entity persistence and narrative progression across scenes.
    """

    def __init__(self, output: Dict[str, Any], profile: Dict[str, Any]):
        self.output = output
        self.profile = profile
        self.triptych = output.get("video_triptych", [])

        # Load spaCy model if available
        self._nlp = None
        if HAS_SPACY:
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError:
                pass

    def compute(self) -> float:
        """
        M_AUTO_11: Compute SCORE-based narrative coherence.

        Returns score 0.0-1.0.
        """
        if len(self.triptych) < 3:
            return 0.0

        # Component scores
        entity_score = self._entity_persistence()
        temporal_score = self._temporal_consistency()
        progression_score = self._narrative_progression()

        # Weighted combination
        return (
            entity_score * 0.4 +
            temporal_score * 0.3 +
            progression_score * 0.3
        )

    def _extract_entities(self, text: str) -> Set[str]:
        """Extract entities from text using spaCy or fallback."""
        entities = set()
        text_lower = text.lower()

        if self._nlp is not None:
            # Use spaCy NER
            doc = self._nlp(text)
            for ent in doc.ents:
                entities.add(ent.text.lower())
            # Also extract nouns
            for token in doc:
                if token.pos_ in ("NOUN", "PROPN"):
                    entities.add(token.lemma_.lower())
        else:
            # Fallback: extract known visual entities
            words = set(re.findall(r'\w+', text_lower))
            entities = words.intersection(VISUAL_ENTITIES)

            # Also extract capitalized words as potential entities
            caps = re.findall(r'\b[A-Z][a-z]+\b', text)
            entities.update(w.lower() for w in caps)

        return entities

    def _entity_persistence(self) -> float:
        """
        Measure entity persistence across scenes.

        Higher score = more shared entities = more coherent narrative.
        """
        scene_entities = []
        for scene in self.triptych:
            prompt = scene.get("prompt", "")
            entities = self._extract_entities(prompt)
            scene_entities.append(entities)

        if not any(scene_entities):
            return 0.0

        # Calculate pairwise overlap
        overlaps = []
        for i in range(len(scene_entities)):
            for j in range(i + 1, len(scene_entities)):
                e1, e2 = scene_entities[i], scene_entities[j]
                if e1 and e2:
                    overlap = len(e1 & e2) / min(len(e1), len(e2))
                    overlaps.append(overlap)

        if not overlaps:
            return 0.0

        # Average overlap, boosted for having core persistent entities
        avg_overlap = sum(overlaps) / len(overlaps)

        # Bonus for entities in ALL scenes
        common_to_all = scene_entities[0]
        for entities in scene_entities[1:]:
            common_to_all = common_to_all & entities

        if len(common_to_all) >= 2:
            avg_overlap = min(1.0, avg_overlap * 1.3)

        return avg_overlap

    def _temporal_consistency(self) -> float:
        """
        Check for temporal consistency markers.

        Scenes should flow logically in time (no backwards jumps).
        """
        prompts = [s.get("prompt", "").lower() for s in self.triptych]

        # Check for appropriate temporal markers in each position
        scores = []

        for i, prompt in enumerate(prompts):
            role = self.triptych[i].get("scene_role", "").lower()

            # Check if prompt has markers appropriate for its role
            if role in PROGRESSION_MARKERS:
                markers = PROGRESSION_MARKERS[role]
                has_marker = any(m in prompt for m in markers)
                scores.append(1.0 if has_marker else 0.5)
            else:
                scores.append(0.5)  # Unknown role

        return sum(scores) / len(scores) if scores else 0.0

    def _narrative_progression(self) -> float:
        """
        Measure narrative intensity progression.

        Good progression: Start (low) → Evolve (build) → End (resolve)
        """
        # Intensity indicators
        low_intensity = ["calm", "still", "quiet", "gentle", "soft", "peaceful"]
        high_intensity = ["dramatic", "intense", "powerful", "dynamic", "bold"]
        resolution = ["fades", "settles", "resolves", "peaceful", "calm", "serene"]

        prompts = [s.get("prompt", "").lower() for s in self.triptych]

        if len(prompts) < 3:
            return 0.0

        # Count intensity markers per scene
        def count_markers(text, markers):
            return sum(1 for m in markers if m in text)

        start_low = count_markers(prompts[0], low_intensity)
        evolve_high = count_markers(prompts[1], high_intensity)
        end_resolve = count_markers(prompts[2], resolution)

        # Score based on expected arc
        score = 0.0

        # Start should have low intensity
        if start_low > 0:
            score += 0.33

        # Evolve should have build/intensity
        if evolve_high > 0:
            score += 0.33

        # End should resolve
        if end_resolve > 0:
            score += 0.34

        return score

    def get_analysis(self) -> Dict[str, Any]:
        """Get detailed coherence analysis for debugging."""
        scene_entities = []
        for scene in self.triptych:
            prompt = scene.get("prompt", "")
            entities = self._extract_entities(prompt)
            scene_entities.append(list(entities))

        # Find common entities
        if scene_entities:
            common = set(scene_entities[0])
            for entities in scene_entities[1:]:
                common = common & set(entities)
        else:
            common = set()

        return {
            "entities_per_scene": scene_entities,
            "common_entities": list(common),
            "entity_persistence": self._entity_persistence(),
            "temporal_consistency": self._temporal_consistency(),
            "narrative_progression": self._narrative_progression(),
            "overall_score": self.compute()
        }
