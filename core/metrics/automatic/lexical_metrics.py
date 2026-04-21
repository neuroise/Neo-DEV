"""
Lexical metrics for prompt quality assessment.

Metrics:
- M_AUTO_07: archetype_lexical_fit - Keyword matching for archetype
- M_AUTO_10: marine_vocabulary_ratio - Domain adherence
"""

from typing import Any, Dict, Set
import re

from core.config import get_archetype_lexicon, resolve_archetype

# Extended archetype vocabulary (loaded from centralized config)
ARCHETYPE_LEXICON = get_archetype_lexicon()

# Marine/coastal vocabulary
MARINE_VOCABULARY = {
    # Water forms
    "ocean", "sea", "water", "wave", "tide", "current", "ripple",
    "surf", "swell", "foam", "spray", "mist",
    # Marine features
    "horizon", "coastline", "shore", "beach", "bay", "cove",
    "reef", "sandbar", "inlet", "cliff", "rock", "seabed",
    # Sky/atmosphere
    "sky", "cloud", "sun", "sunrise", "sunset", "dawn", "dusk",
    "moonlight", "starlight", "twilight",
    # Marine life
    "dolphin", "whale", "fish", "seabird", "gull", "pelican",
    # Vessels
    "yacht", "boat", "sail", "hull", "deck", "bow", "stern",
    "anchor", "mast", "helm",
    # Visual elements
    "reflection", "shimmer", "sparkle", "glimmer", "glow",
    "turquoise", "azure", "blue", "teal", "aquamarine",
    # Atmospheric
    "breeze", "wind", "calm", "storm", "weather",
    "light", "shadow", "silhouette"
}


class LexicalMetrics:
    """
    Computes lexical metrics for prompt quality.

    Uses keyword matching and vocabulary analysis.
    """

    def __init__(self, output: Dict[str, Any], profile: Dict[str, Any]):
        self.output = output
        self.profile = profile
        self.triptych = output.get("video_triptych", [])
        self.ost = output.get("ost_prompt", {})

        user_profile = profile.get("user_profile", profile)
        self.archetype = resolve_archetype(
            user_profile.get("primary_archetype", "sage")
        )

        # Precompute all text
        self.all_prompts = " ".join(s.get("prompt", "") for s in self.triptych)
        self.all_text = self.all_prompts + " " + self.ost.get("prompt", "")
        self.all_words = set(re.findall(r'\w+', self.all_text.lower()))

    def compute_all(self) -> Dict[str, float]:
        """Compute all lexical metrics."""
        return {
            "M_AUTO_07_archetype_lexical_fit": self.archetype_lexical_fit(),
            "M_AUTO_10_marine_vocabulary_ratio": self.marine_vocabulary_ratio(),
        }

    def archetype_lexical_fit(self) -> float:
        """
        M_AUTO_07: Measure how well prompts match archetype vocabulary.

        Uses weighted keyword matching:
        - High weight words: 3 points
        - Medium weight words: 2 points
        - Low weight words: 1 point

        Score normalized to 0.0-1.0.
        """
        lexicon = ARCHETYPE_LEXICON.get(self.archetype)
        if not lexicon:
            return 0.5  # Unknown archetype

        text = self.all_text.lower()
        score = 0
        max_score = 0

        # High weight (3 points each, max 15)
        for word in lexicon["high_weight"]:
            max_score += 3
            if word in text:
                score += 3

        # Medium weight (2 points each, max 12)
        for word in lexicon["medium_weight"]:
            max_score += 2
            if word in text:
                score += 2

        # Low weight (1 point each, max 6)
        for word in lexicon["low_weight"]:
            max_score += 1
            if word in text:
                score += 1

        # Normalize
        raw_score = score / max_score if max_score > 0 else 0

        # Boost if at least some high-weight words present
        high_count = sum(1 for w in lexicon["high_weight"] if w in text)
        if high_count >= 2:
            raw_score = min(1.0, raw_score * 1.2)

        return min(1.0, raw_score)

    def marine_vocabulary_ratio(self) -> float:
        """
        M_AUTO_10: Measure domain adherence through marine vocabulary.

        Calculates the ratio of marine-related words to total unique words.
        """
        if not self.all_words:
            return 0.0

        # Count marine vocabulary matches
        marine_matches = self.all_words.intersection(MARINE_VOCABULARY)
        marine_count = len(marine_matches)

        # Calculate ratio
        # We expect at least 5-10 marine words in good prompts
        ratio = marine_count / len(self.all_words)

        # Also check absolute count
        absolute_score = min(marine_count / 10, 1.0)

        # Combine ratio and absolute
        return (ratio * 0.3 + absolute_score * 0.7)

    def get_vocabulary_analysis(self) -> Dict[str, Any]:
        """
        Get detailed vocabulary analysis for debugging.

        Returns dict with:
        - archetype_words_found
        - marine_words_found
        - unique_word_count
        """
        lexicon = ARCHETYPE_LEXICON.get(self.archetype, {})
        text = self.all_text.lower()

        archetype_found = []
        for weight, words in lexicon.items():
            for word in words:
                if word in text:
                    archetype_found.append((word, weight))

        marine_found = list(self.all_words.intersection(MARINE_VOCABULARY))

        return {
            "archetype_words_found": archetype_found,
            "marine_words_found": marine_found,
            "unique_word_count": len(self.all_words),
            "archetype": self.archetype
        }
