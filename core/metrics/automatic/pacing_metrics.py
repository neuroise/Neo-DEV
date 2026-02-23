"""
Pacing and intensity progression metrics.

M_AUTO_13: pacing_progression

Analyzes the intensity curve across the video triptych to ensure
proper narrative pacing:
- START: Establishes tone (typically lower intensity)
- EVOLVE: Builds and develops (rising intensity)
- END: Resolves (can vary based on archetype)

Different archetypes have different expected pacing curves.
"""

from typing import Any, Dict, List, Tuple
import re


# Intensity markers by level
INTENSITY_MARKERS = {
    "very_low": [
        "still", "silent", "motionless", "frozen", "static",
        "peaceful", "tranquil", "serene", "whisper"
    ],
    "low": [
        "calm", "gentle", "soft", "quiet", "slow",
        "subtle", "delicate", "light", "floating", "drifting"
    ],
    "medium": [
        "moving", "flowing", "steady", "continuous", "moderate",
        "gradual", "building", "shifting", "changing"
    ],
    "high": [
        "dynamic", "energetic", "active", "vivid", "bold",
        "intense", "dramatic", "powerful", "sweeping"
    ],
    "very_high": [
        "explosive", "crashing", "thundering", "fierce", "wild",
        "violent", "rapid", "extreme", "overwhelming"
    ]
}

# Camera movement indicators (affect perceived intensity)
CAMERA_INTENSITY = {
    "static": ["still shot", "fixed camera", "locked off", "stationary"],
    "slow": ["slow pan", "gentle zoom", "tracking shot", "dolly"],
    "medium": ["pan", "tilt", "zoom", "crane shot"],
    "fast": ["whip pan", "fast zoom", "rapid", "quick cut"],
    "very_fast": ["shake", "handheld", "chaotic", "frenetic"]
}

# Expected pacing curves by archetype
ARCHETYPE_CURVES = {
    "sage": {
        "start": (0.1, 0.3),    # Low, contemplative
        "evolve": (0.2, 0.4),   # Gentle build
        "end": (0.1, 0.3)       # Return to calm
    },
    "rebel": {
        "start": (0.3, 0.5),    # Medium start
        "evolve": (0.6, 0.9),   # High intensity
        "end": (0.4, 0.7)       # Strong resolution
    },
    "lover": {
        "start": (0.2, 0.4),    # Warm introduction
        "evolve": (0.4, 0.6),   # Emotional build
        "end": (0.3, 0.5)       # Tender resolution
    }
}


class PacingMetrics:
    """
    Analyzes pacing and intensity progression in the triptych.
    """

    def __init__(self, output: Dict[str, Any], profile: Dict[str, Any]):
        self.output = output
        self.profile = profile
        self.triptych = output.get("video_triptych", [])

        user_profile = profile.get("user_profile", profile)
        self.archetype = user_profile.get("primary_archetype", "sage").lower()

    def compute(self) -> float:
        """
        M_AUTO_13: Compute pacing progression score.

        Returns 0.0-1.0 based on how well pacing matches archetype expectations.
        """
        if len(self.triptych) < 3:
            return 0.0

        # Get intensity for each scene
        intensities = self._compute_intensities()

        # Get expected curve
        expected = ARCHETYPE_CURVES.get(self.archetype, ARCHETYPE_CURVES["sage"])

        # Score each scene against expected range
        scores = []
        roles = ["start", "evolve", "end"]

        for i, (role, intensity) in enumerate(zip(roles, intensities)):
            low, high = expected[role]

            if low <= intensity <= high:
                # Perfect match
                scores.append(1.0)
            elif intensity < low:
                # Too low - calculate distance penalty
                distance = low - intensity
                scores.append(max(0.0, 1.0 - distance * 2))
            else:
                # Too high - calculate distance penalty
                distance = intensity - high
                scores.append(max(0.0, 1.0 - distance * 2))

        # Also check progression pattern
        progression_bonus = self._check_progression(intensities)

        # Weighted average
        base_score = sum(scores) / len(scores)
        return min(1.0, base_score * 0.8 + progression_bonus * 0.2)

    def _compute_intensities(self) -> List[float]:
        """Compute intensity score (0-1) for each scene."""
        intensities = []

        for scene in self.triptych:
            prompt = scene.get("prompt", "").lower()
            camera = scene.get("camera_hints", "").lower()
            mood_tags = [t.lower() for t in scene.get("mood_tags", [])]

            # Combine all text
            all_text = prompt + " " + camera + " " + " ".join(mood_tags)

            intensity = self._text_intensity(all_text)
            intensities.append(intensity)

        return intensities

    def _text_intensity(self, text: str) -> float:
        """Calculate intensity score for text."""
        # Count markers at each level
        counts = {
            "very_low": 0,
            "low": 0,
            "medium": 0,
            "high": 0,
            "very_high": 0
        }

        for level, markers in INTENSITY_MARKERS.items():
            for marker in markers:
                if marker in text:
                    counts[level] += 1

        # Also check camera intensity
        for level, markers in CAMERA_INTENSITY.items():
            for marker in markers:
                if marker in text:
                    # Map camera levels to intensity levels
                    level_map = {
                        "static": "very_low",
                        "slow": "low",
                        "medium": "medium",
                        "fast": "high",
                        "very_fast": "very_high"
                    }
                    counts[level_map[level]] += 1

        # Calculate weighted intensity
        weights = {
            "very_low": 0.1,
            "low": 0.3,
            "medium": 0.5,
            "high": 0.7,
            "very_high": 0.9
        }

        total_weight = 0
        total_count = 0

        for level, count in counts.items():
            if count > 0:
                total_weight += weights[level] * count
                total_count += count

        if total_count == 0:
            return 0.5  # Neutral if no markers

        return total_weight / total_count

    def _check_progression(self, intensities: List[float]) -> float:
        """
        Check if intensity progression makes narrative sense.

        Returns bonus score (0-1) for good progression.
        """
        if len(intensities) < 3:
            return 0.0

        start, evolve, end = intensities

        # Different archetypes have different expected progressions
        if self.archetype == "sage":
            # Sage: relatively flat, contemplative
            variance = max(intensities) - min(intensities)
            return 1.0 if variance < 0.3 else max(0.0, 1.0 - variance)

        elif self.archetype == "rebel":
            # Rebel: should build to high point
            if evolve > start and evolve >= end:
                return 1.0  # Good build
            elif evolve > start:
                return 0.7  # Partial build
            else:
                return 0.3

        elif self.archetype == "lover":
            # Lover: gentle arc, emotional peak in middle
            if evolve >= start and evolve >= end:
                return 1.0  # Good emotional arc
            else:
                return 0.5

        return 0.5

    def get_analysis(self) -> Dict[str, Any]:
        """Get detailed pacing analysis."""
        intensities = self._compute_intensities()
        expected = ARCHETYPE_CURVES.get(self.archetype, ARCHETYPE_CURVES["sage"])

        scenes = []
        roles = ["start", "evolve", "end"]

        for i, (role, intensity) in enumerate(zip(roles, intensities)):
            low, high = expected[role]
            in_range = low <= intensity <= high

            scenes.append({
                "role": role,
                "intensity": intensity,
                "expected_range": (low, high),
                "in_range": in_range
            })

        return {
            "archetype": self.archetype,
            "scenes": scenes,
            "progression_bonus": self._check_progression(intensities),
            "overall_score": self.compute()
        }
