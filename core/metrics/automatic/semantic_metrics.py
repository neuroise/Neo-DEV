"""
Semantic metrics using embeddings.

Metrics:
- M_AUTO_08: cross_scene_coherence - Embedding similarity across scenes
- M_AUTO_09: prompt_specificity - Concreteness and detail level
"""

from typing import Any, Dict, List, Optional
import os
import re
import numpy as np

# Set HF cache to project directory to avoid permission issues
_PROJECT_CACHE = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".cache", "huggingface")
os.environ.setdefault("HF_HOME", _PROJECT_CACHE)

# Optional sentence-transformers import
try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


# Concrete/specific words that indicate detail
CONCRETE_INDICATORS = {
    # Camera angles
    "close-up", "wide shot", "aerial", "tracking", "pan", "zoom",
    "overhead", "low angle", "high angle", "dolly", "crane",
    # Movement
    "slowly", "gradually", "gently", "rapidly", "steadily",
    "drifting", "floating", "gliding", "sweeping", "rising",
    # Colors (specific)
    "azure", "turquoise", "golden", "amber", "coral", "crimson",
    "silver", "pearl", "sapphire", "emerald", "cobalt",
    # Lighting
    "backlit", "rim light", "soft light", "diffused", "silhouette",
    "golden hour", "blue hour", "overcast", "dappled", "filtered",
    # Textures
    "rippled", "smooth", "crystalline", "foamy", "glassy", "misty",
    # Composition
    "foreground", "background", "midground", "rule of thirds",
    "centered", "off-center", "symmetrical", "layered"
}

# Abstract/vague words that indicate low specificity
ABSTRACT_INDICATORS = {
    "beautiful", "nice", "good", "amazing", "wonderful", "great",
    "feeling", "emotion", "vibe", "energy", "essence",
    "something", "somehow", "somewhat", "various", "different"
}


class SemanticMetrics:
    """
    Computes semantic metrics using embeddings and linguistic analysis.
    """

    def __init__(self, output: Dict[str, Any], profile: Dict[str, Any]):
        self.output = output
        self.profile = profile
        self.triptych = output.get("video_triptych", [])
        self.ost = output.get("ost_prompt", {})

        # Extract prompts
        self.scene_prompts = [s.get("prompt", "") for s in self.triptych]
        self.ost_prompt = self.ost.get("prompt", "")

        # Lazy load embedding model
        self._model = None

    def _get_model(self):
        """Lazy load sentence transformer model."""
        if self._model is None and HAS_SENTENCE_TRANSFORMERS:
            try:
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception:
                # Fallback: can't load model (permissions, network, etc.)
                self._model = None
        return self._model

    def compute_all(self) -> Dict[str, float]:
        """Compute all semantic metrics."""
        return {
            "M_AUTO_08_cross_scene_coherence": self.cross_scene_coherence(),
            "M_AUTO_09_prompt_specificity": self.prompt_specificity(),
        }

    def cross_scene_coherence(self) -> float:
        """
        M_AUTO_08: Measure semantic coherence across scenes using embeddings.

        Computes pairwise cosine similarity between scene embeddings.
        High similarity = coherent narrative thread.

        Falls back to keyword overlap if embeddings unavailable.
        """
        if len(self.scene_prompts) < 2:
            return 0.0

        model = self._get_model()

        if model is not None:
            return self._coherence_with_embeddings(model)
        else:
            return self._coherence_with_overlap()

    def _coherence_with_embeddings(self, model) -> float:
        """Compute coherence using sentence embeddings."""
        # Encode all scene prompts
        embeddings = model.encode(self.scene_prompts)

        # Compute pairwise cosine similarities
        similarities = []
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                sim = self._cosine_similarity(embeddings[i], embeddings[j])
                similarities.append(sim)

        # Average similarity
        avg_sim = np.mean(similarities) if similarities else 0.0

        # Calibrated normalization based on empirical data:
        # Marine-themed triptychs: 0.60-0.84 range (baseline llama3.3:70b)
        # Random/incoherent prompts: ~0.2-0.4
        # Map: 0.45 -> 0.0, 0.90 -> 1.0
        normalized = (avg_sim - 0.45) / 0.45
        return max(0.0, min(1.0, normalized))

    def _coherence_with_overlap(self) -> float:
        """Fallback coherence using word overlap."""
        word_sets = []
        for prompt in self.scene_prompts:
            words = set(re.findall(r'\w+', prompt.lower()))
            # Remove common words
            common = {"the", "a", "an", "and", "or", "in", "on", "at", "to", "of", "with", "is", "are"}
            words = words - common
            word_sets.append(words)

        # Compute pairwise Jaccard similarity
        similarities = []
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])
                if union > 0:
                    similarities.append(intersection / union)

        return np.mean(similarities) if similarities else 0.0

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def prompt_specificity(self) -> float:
        """
        M_AUTO_09: Measure concreteness and detail level in prompts.

        Higher score = more specific, production-ready prompts.
        Lower score = vague, abstract descriptions.
        """
        all_text = " ".join(self.scene_prompts + [self.ost_prompt]).lower()
        words = re.findall(r'\w+', all_text)

        if not words:
            return 0.0

        # Count concrete indicators
        concrete_count = sum(
            1 for word in words
            if any(ind in word for ind in CONCRETE_INDICATORS)
        )

        # Also check multi-word phrases
        for indicator in CONCRETE_INDICATORS:
            if " " in indicator and indicator in all_text:
                concrete_count += 2  # Bonus for phrases

        # Count abstract indicators (negative)
        abstract_count = sum(
            1 for word in words
            if word in ABSTRACT_INDICATORS
        )

        # Calculate specificity score
        # Baseline: expect ~3-5 concrete indicators per scene
        expected_concrete = len(self.scene_prompts) * 4
        concrete_score = min(concrete_count / expected_concrete, 1.0)

        # Penalty for abstract words
        abstract_penalty = min(abstract_count * 0.1, 0.3)

        # Final score
        return max(0.0, concrete_score - abstract_penalty)

    def get_specificity_analysis(self) -> Dict[str, Any]:
        """
        Get detailed specificity analysis for debugging.
        """
        all_text = " ".join(self.scene_prompts).lower()
        words = set(re.findall(r'\w+', all_text))

        concrete_found = [w for w in CONCRETE_INDICATORS if w in all_text]
        abstract_found = [w for w in ABSTRACT_INDICATORS if w in all_text]

        return {
            "concrete_indicators_found": concrete_found,
            "abstract_indicators_found": abstract_found,
            "unique_word_count": len(words),
            "avg_prompt_length": np.mean([len(p) for p in self.scene_prompts])
        }
