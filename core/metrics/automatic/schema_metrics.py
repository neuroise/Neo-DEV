"""
Schema-based metrics for Director output validation.

Metrics M_AUTO_01 to M_AUTO_06:
- M_AUTO_01: schema_compliance - Valid JSON structure
- M_AUTO_02: archetype_consistency - Same archetype across scenes
- M_AUTO_03: role_sequence_valid - start→evolve→end sequence
- M_AUTO_04: story_thread_presence - Thread reflected in prompts
- M_AUTO_05: red_flag_score - Policy violation check
- M_AUTO_06: prompt_length_valid - Length constraints
"""

from typing import Any, Dict, List
import re


# Archetype keywords for consistency checking
ARCHETYPE_KEYWORDS = {
    "sage": [
        "contemplative", "minimal", "serene", "philosophical", "calm",
        "horizon", "still", "peaceful", "quiet", "meditative",
        "slow", "gentle", "timeless", "eternal", "reflective"
    ],
    "rebel": [
        "dynamic", "bold", "powerful", "energetic", "dramatic",
        "waves", "crashing", "wind", "speed", "intense",
        "adventure", "freedom", "wild", "fierce", "thrilling"
    ],
    "lover": [
        "warm", "intimate", "romantic", "sensual", "tender",
        "sunset", "golden", "soft", "close", "connected",
        "gentle", "embrace", "touch", "beauty", "passion"
    ]
}

# Red flag terms that should not appear
RED_FLAG_TERMS = [
    "urban", "city", "building", "skyscraper", "street",
    "face", "person", "people", "crowd", "portrait",
    "logo", "brand", "text", "sign", "advertisement",
    "violence", "blood", "weapon", "danger", "death",
    "forest", "desert", "mountain", "jungle", "snow"
]


class SchemaMetrics:
    """
    Computes schema-based metrics for Director output.

    These are deterministic metrics that don't require ML models.
    """

    def __init__(self, output: Dict[str, Any], profile: Dict[str, Any]):
        """
        Initialize with output and profile.

        Args:
            output: Director output dict (video_triptych, ost_prompt, metadata)
            profile: User profile dict
        """
        self.output = output
        self.profile = profile
        self.triptych = output.get("video_triptych", [])
        self.ost = output.get("ost_prompt", {})
        self.metadata = output.get("metadata", {})

        # Extract archetype from profile
        user_profile = profile.get("user_profile", profile)
        self.archetype = user_profile.get("primary_archetype", "sage").lower()
        self.story_thread = user_profile.get("story_thread_hint", "")

    def compute_all(self) -> Dict[str, float]:
        """Compute all schema metrics."""
        return {
            "M_AUTO_01_schema_compliance": self.schema_compliance(),
            "M_AUTO_02_archetype_consistency": self.archetype_consistency(),
            "M_AUTO_03_role_sequence_valid": self.role_sequence_valid(),
            "M_AUTO_04_story_thread_presence": self.story_thread_presence(),
            "M_AUTO_05_red_flag_score": self.red_flag_score(),
            "M_AUTO_06_prompt_length_valid": self.prompt_length_valid(),
        }

    def schema_compliance(self) -> float:
        """
        M_AUTO_01: Check if output has valid structure.

        Returns 1.0 if all required fields present, 0.0-1.0 otherwise.
        """
        score = 0.0
        checks = 0

        # Check video_triptych exists and has 3 scenes
        checks += 1
        if isinstance(self.triptych, list) and len(self.triptych) == 3:
            score += 1.0

        # Check each scene has required fields
        required_scene_fields = ["scene_role", "prompt", "duration_hint", "mood_tags"]
        for scene in self.triptych:
            checks += 1
            if isinstance(scene, dict):
                present = sum(1 for f in required_scene_fields if f in scene)
                score += present / len(required_scene_fields)

        # Check OST has required fields
        required_ost_fields = ["prompt", "genre", "bpm", "mood"]
        checks += 1
        if isinstance(self.ost, dict):
            present = sum(1 for f in required_ost_fields if f in self.ost)
            score += present / len(required_ost_fields)

        return score / checks if checks > 0 else 0.0

    def archetype_consistency(self) -> float:
        """
        M_AUTO_02: Check if archetype is consistent across all scenes.

        Uses keyword matching to detect archetype alignment.
        """
        if not self.triptych:
            return 0.0

        keywords = ARCHETYPE_KEYWORDS.get(self.archetype, [])
        if not keywords:
            return 0.5  # Unknown archetype, neutral score

        total_score = 0.0

        for scene in self.triptych:
            prompt = scene.get("prompt", "").lower()
            mood_tags = [t.lower() for t in scene.get("mood_tags", [])]
            text = prompt + " " + " ".join(mood_tags)

            # Count keyword matches
            matches = sum(1 for kw in keywords if kw in text)
            scene_score = min(matches / 3, 1.0)  # Cap at 3 matches = 1.0
            total_score += scene_score

        return total_score / len(self.triptych)

    def role_sequence_valid(self) -> float:
        """
        M_AUTO_03: Check if scenes follow start→evolve→end sequence.

        Returns 1.0 if perfect sequence, 0.0-1.0 otherwise.
        """
        if len(self.triptych) != 3:
            return 0.0

        expected_sequence = ["start", "evolve", "end"]
        actual_sequence = [s.get("scene_role", "").lower() for s in self.triptych]

        # Check exact match
        if actual_sequence == expected_sequence:
            return 1.0

        # Check if all roles present (even if order wrong)
        if set(actual_sequence) == set(expected_sequence):
            return 0.5

        # Check how many are correct
        correct = sum(1 for a, e in zip(actual_sequence, expected_sequence) if a == e)
        return correct / 3

    def story_thread_presence(self) -> float:
        """
        M_AUTO_04: Check if story_thread_hint is reflected in prompts.

        Returns 1.0 if thread clearly present, 0.0 if absent.
        """
        if not self.story_thread:
            return 1.0  # No thread to check, passes by default

        thread_lower = self.story_thread.lower()
        # Split on underscores, spaces, and other non-alpha chars to get individual words
        thread_words = set(re.findall(r'[a-zA-Z]+', thread_lower))

        # Filter out common words
        common_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of"}
        thread_words = thread_words - common_words

        if not thread_words:
            return 1.0

        # Check all prompts
        all_text = " ".join(s.get("prompt", "") for s in self.triptych).lower()
        all_text += " " + self.ost.get("prompt", "").lower()

        # Count thread word occurrences
        found = sum(1 for word in thread_words if word in all_text)
        return min(found / len(thread_words), 1.0)

    def red_flag_score(self) -> float:
        """
        M_AUTO_05: Check for policy violations (red flag terms).

        Returns 1.0 if clean, decreases with violations.
        """
        all_text = " ".join(s.get("prompt", "") for s in self.triptych).lower()
        all_text += " " + self.ost.get("prompt", "").lower()

        violations = []
        for term in RED_FLAG_TERMS:
            if term in all_text:
                violations.append(term)

        if not violations:
            return 1.0

        # Penalize: each violation reduces score
        penalty = len(violations) * 0.15
        return max(0.0, 1.0 - penalty)

    def prompt_length_valid(self) -> float:
        """
        M_AUTO_06: Check if prompts meet length requirements.

        Video prompts: 50-500 chars
        OST prompt: 20-300 chars
        """
        scores = []

        # Check video prompts
        for scene in self.triptych:
            prompt = scene.get("prompt", "")
            length = len(prompt)

            if 50 <= length <= 500:
                scores.append(1.0)
            elif 30 <= length < 50 or 500 < length <= 600:
                scores.append(0.7)
            elif 20 <= length < 30 or 600 < length <= 700:
                scores.append(0.4)
            else:
                scores.append(0.0)

        # Check OST prompt
        ost_prompt = self.ost.get("prompt", "")
        ost_length = len(ost_prompt)

        if 20 <= ost_length <= 300:
            scores.append(1.0)
        elif 10 <= ost_length < 20 or 300 < ost_length <= 400:
            scores.append(0.7)
        else:
            scores.append(0.0)

        return sum(scores) / len(scores) if scores else 0.0
