"""
Human Evaluation Framework for NEUROISE.

Stores and manages human evaluation scores with inter-rater agreement metrics.

Dimensions (Likert 1-5):
- visual_clarity: Can a video AI render this prompt?
- archetype_alignment: Does it match the archetype?
- narrative_coherence: Do scenes tell a coherent story?
- emotional_resonance: Does it evoke intended emotion?
- marine_adherence: Marine/coastal only, no red flags?

Example:
    >>> store = HumanEvalStore()
    >>> evaluation = HumanEvaluation(
    ...     experiment="baseline_qwen",
    ...     profile_id="S-01",
    ...     rater_id="rater_A",
    ...     scores={"visual_clarity": 4, "archetype_alignment": 5, ...}
    ... )
    >>> store.save(evaluation)
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


EVAL_DIMENSIONS = [
    "visual_clarity",
    "archetype_alignment",
    "narrative_coherence",
    "emotional_resonance",
    "marine_adherence",
]

DIMENSION_DESCRIPTIONS = {
    "visual_clarity": "Can a video AI render these prompts with no ambiguity?",
    "archetype_alignment": "Do all scenes match the archetype's visual language?",
    "narrative_coherence": "Do the 3 scenes tell a coherent visual story?",
    "emotional_resonance": "Does the sequence evoke the intended emotion?",
    "marine_adherence": "Is everything marine/coastal with zero red flags?",
}


@dataclass
class HumanEvaluation:
    """A single human evaluation of a generated output."""

    experiment: str
    profile_id: str
    rater_id: str
    scores: Dict[str, int]  # dimension -> 1-5
    notes: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def mean_score(self) -> float:
        if not self.scores:
            return 0.0
        return sum(self.scores.values()) / len(self.scores)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HumanEvaluation":
        return cls(**d)


class HumanEvalStore:
    """JSONL-backed storage for human evaluations."""

    DEFAULT_PATH = "data/evaluations/human_eval.jsonl"

    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or self.DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, evaluation: HumanEvaluation) -> None:
        """Append a human evaluation to the JSONL file."""
        with open(self.path, "a") as f:
            f.write(json.dumps(evaluation.to_dict()) + "\n")

    def load_all(self) -> List[HumanEvaluation]:
        """Load all evaluations."""
        if not self.path.exists():
            return []
        evals = []
        for line in self.path.read_text().strip().split("\n"):
            if line.strip():
                evals.append(HumanEvaluation.from_dict(json.loads(line)))
        return evals

    def load_for_item(
        self, experiment: str, profile_id: str
    ) -> List[HumanEvaluation]:
        """Load evaluations for a specific experiment + profile pair."""
        return [
            e for e in self.load_all()
            if e.experiment == experiment and e.profile_id == profile_id
        ]

    def load_for_experiment(self, experiment: str) -> List[HumanEvaluation]:
        """Load all evaluations for an experiment."""
        return [e for e in self.load_all() if e.experiment == experiment]

    def cohens_kappa(
        self, experiment: str, rater_a: str, rater_b: str,
        dimension: Optional[str] = None,
    ) -> float:
        """Compute Cohen's kappa for two raters.

        Args:
            experiment: Experiment name
            rater_a: First rater ID
            rater_b: Second rater ID
            dimension: Specific dimension (or None for all dimensions averaged)

        Returns:
            Cohen's kappa coefficient (-1 to 1)
        """
        evals = self.load_for_experiment(experiment)

        # Group by (profile_id, dimension)
        ratings_a = {}
        ratings_b = {}
        for e in evals:
            dims = [dimension] if dimension else EVAL_DIMENSIONS
            for dim in dims:
                if dim in e.scores:
                    key = (e.profile_id, dim)
                    if e.rater_id == rater_a:
                        ratings_a[key] = e.scores[dim]
                    elif e.rater_id == rater_b:
                        ratings_b[key] = e.scores[dim]

        # Find common items
        common_keys = set(ratings_a.keys()) & set(ratings_b.keys())
        if len(common_keys) < 2:
            return 0.0

        a_vals = [ratings_a[k] for k in common_keys]
        b_vals = [ratings_b[k] for k in common_keys]

        return self._compute_kappa(a_vals, b_vals, categories=list(range(1, 6)))

    def fleiss_kappa(
        self, experiment: str, dimension: Optional[str] = None,
    ) -> float:
        """Compute Fleiss' kappa for 3+ raters.

        Args:
            experiment: Experiment name
            dimension: Specific dimension (or None = all averaged)

        Returns:
            Fleiss' kappa coefficient
        """
        evals = self.load_for_experiment(experiment)
        if not evals:
            return 0.0

        # Collect all raters
        raters = set(e.rater_id for e in evals)
        if len(raters) < 3:
            return 0.0

        dims = [dimension] if dimension else EVAL_DIMENSIONS

        # Build rating matrix: items x categories
        # Each item = (profile_id, dim)
        item_ratings: Dict[tuple, List[int]] = {}
        for e in evals:
            for dim in dims:
                if dim in e.scores:
                    key = (e.profile_id, dim)
                    item_ratings.setdefault(key, []).append(e.scores[dim])

        # Only keep items rated by at least n_raters
        n_raters = len(raters)
        items = {k: v for k, v in item_ratings.items() if len(v) >= n_raters}
        if not items:
            return 0.0

        categories = list(range(1, 6))
        n_items = len(items)
        n_cats = len(categories)
        n = n_raters

        # Build n_ij matrix (items x categories)
        p_j = [0.0] * n_cats
        p_i_list = []

        for ratings in items.values():
            counts = [ratings.count(c) for c in categories]
            p_i = (sum(c * c for c in counts) - n) / (n * (n - 1)) if n > 1 else 0
            p_i_list.append(p_i)
            for j, c in enumerate(counts):
                p_j[j] += c

        p_bar = sum(p_i_list) / n_items if n_items > 0 else 0
        total_ratings = n_items * n
        p_e = sum((pj / total_ratings) ** 2 for pj in p_j) if total_ratings > 0 else 0

        if p_e == 1.0:
            return 1.0
        return (p_bar - p_e) / (1 - p_e)

    @staticmethod
    def _compute_kappa(a: List[int], b: List[int], categories: List[int]) -> float:
        """Compute Cohen's kappa from two lists of ratings."""
        n = len(a)
        if n == 0:
            return 0.0

        # Observed agreement
        p_o = sum(1 for x, y in zip(a, b) if x == y) / n

        # Expected agreement
        p_e = 0.0
        for c in categories:
            p_a = sum(1 for x in a if x == c) / n
            p_b = sum(1 for x in b if x == c) / n
            p_e += p_a * p_b

        if p_e == 1.0:
            return 1.0
        return (p_o - p_e) / (1 - p_e)
