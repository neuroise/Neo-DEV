"""
LLM-as-Judge metric for qualitative evaluation.

M_AUTO_12: llm_judge_quality

Uses an LLM to evaluate prompt quality on multiple dimensions:
1. Visual clarity - How clear and production-ready is the prompt?
2. Archetype alignment - Does it match the intended archetype?
3. Narrative coherence - Does the triptych tell a coherent story?
4. Emotional resonance - Does it evoke the intended mood?

Based on LLM-as-Judge literature (2024-2025).
"""

import json
from typing import Any, Dict, List, Optional

# Import LLM adapter
try:
    from core.llm import create_adapter
    HAS_LLM = True
except ImportError:
    HAS_LLM = False


JUDGE_SYSTEM_PROMPT = """You are an expert evaluator for AI-generated video prompts.
You evaluate prompts for a luxury yacht storytelling system called NEURØISE.

Your task is to score prompts on multiple quality dimensions.
Be critical but fair. Focus on production-readiness and alignment with requirements.

Score each dimension from 1-5:
1 = Poor/Fails completely
2 = Below average/Major issues
3 = Acceptable/Some issues
4 = Good/Minor issues
5 = Excellent/No issues

Provide brief justification for each score."""


JUDGE_USER_TEMPLATE = """## Evaluation Task

Evaluate the following video prompt triptych for a {archetype} archetype user.

### Profile Context
- Primary Archetype: {archetype}
- Story Thread Hint: {story_thread}
- Music Genre: {music_genre}

### Video Triptych to Evaluate

**Scene 1 (START):**
{start_prompt}

**Scene 2 (EVOLVE):**
{evolve_prompt}

**Scene 3 (END):**
{end_prompt}

### OST Prompt
{ost_prompt}

---

## Evaluation Criteria

Score each dimension 1-5:

1. **visual_clarity**: Are the prompts specific enough for AI video generation? Do they include camera angles, lighting, subjects, movement?

2. **archetype_alignment**: Do the prompts match the {archetype} archetype characteristics? (Sage=contemplative/minimal, Rebel=dynamic/bold, Lover=warm/intimate)

3. **narrative_coherence**: Does the triptych tell a coherent visual story with beginning, development, and resolution?

4. **emotional_resonance**: Would these prompts create an emotionally impactful experience matching the archetype?

5. **marine_adherence**: Are prompts strictly marine/coastal themed without forbidden elements (urban, faces, logos)?

## Response Format

Respond with valid JSON only:
```json
{{
    "visual_clarity": {{"score": X, "reason": "..."}},
    "archetype_alignment": {{"score": X, "reason": "..."}},
    "narrative_coherence": {{"score": X, "reason": "..."}},
    "emotional_resonance": {{"score": X, "reason": "..."}},
    "marine_adherence": {{"score": X, "reason": "..."}},
    "overall_quality": X,
    "summary": "Brief overall assessment"
}}
```"""


class LLMJudge:
    """
    Uses LLM to evaluate prompt quality.

    Can use any available LLM adapter (Claude, GPT-4, Ollama).
    """

    def __init__(
        self,
        output: Dict[str, Any],
        profile: Dict[str, Any],
        judge_model: str = None
    ):
        """
        Initialize LLM Judge.

        Args:
            output: Director output to evaluate
            profile: User profile for context
            judge_model: Model to use as judge (default: qwen3:32b)
        """
        self.output = output
        self.profile = profile
        self.triptych = output.get("video_triptych", [])
        self.ost = output.get("ost_prompt", {})

        # Extract profile info
        user_profile = profile.get("user_profile", profile)
        self.archetype = user_profile.get("primary_archetype", "sage")
        self.story_thread = user_profile.get("story_thread_hint", "none")
        self.music_genre = user_profile.get("music_seed", {}).get("top_genre", "ambient")

        # Judge model - use a capable model from a different family than the generator
        self.judge_model = judge_model or "qwen3:32b"
        self._adapter = None

    def _get_adapter(self):
        """Lazy load judge adapter."""
        if self._adapter is None and HAS_LLM:
            try:
                self._adapter = create_adapter(
                    self.judge_model,
                    temperature=0.3,  # Low temperature for consistent evaluation
                    timeout=120
                )
            except Exception:
                pass
        return self._adapter

    def compute(self) -> float:
        """
        M_AUTO_12: Compute LLM judge quality score.

        Returns normalized score 0.0-1.0.
        """
        evaluation = self.evaluate()

        if evaluation is None:
            return 0.5  # Neutral if judge unavailable

        # Check for error in evaluation
        if "error" in evaluation:
            return 0.5  # Neutral on error

        # Extract overall quality or compute from dimensions
        score = 3  # Default neutral score

        if "overall_quality" in evaluation:
            raw_score = evaluation["overall_quality"]
            # Ensure score is numeric
            if isinstance(raw_score, (int, float)):
                score = raw_score
        else:
            # Average dimension scores
            dimensions = ["visual_clarity", "archetype_alignment",
                         "narrative_coherence", "emotional_resonance",
                         "marine_adherence"]
            scores = []
            for dim in dimensions:
                if dim in evaluation and isinstance(evaluation[dim], dict):
                    dim_score = evaluation[dim].get("score", 3)
                    if isinstance(dim_score, (int, float)):
                        scores.append(dim_score)
            if scores:
                score = sum(scores) / len(scores)

        # Ensure score is in valid range and normalize 1-5 to 0-1
        score = max(1, min(5, score))  # Clamp to 1-5
        return (score - 1) / 4

    def evaluate(self) -> Optional[Dict[str, Any]]:
        """
        Run full LLM evaluation.

        Returns evaluation dict with scores and reasons, or None if unavailable.
        """
        adapter = self._get_adapter()

        if adapter is None:
            return None

        if len(self.triptych) < 3:
            return None

        # Build evaluation prompt
        user_prompt = JUDGE_USER_TEMPLATE.format(
            archetype=self.archetype,
            story_thread=self.story_thread,
            music_genre=self.music_genre,
            start_prompt=self.triptych[0].get("prompt", "N/A"),
            evolve_prompt=self.triptych[1].get("prompt", "N/A"),
            end_prompt=self.triptych[2].get("prompt", "N/A"),
            ost_prompt=self.ost.get("prompt", "N/A")
        )

        try:
            # Generate evaluation
            response = adapter.generate(
                user_prompt=user_prompt,
                system_prompt=JUDGE_SYSTEM_PROMPT
            )

            # Parse JSON response
            content = response.content

            # Try to extract JSON
            try:
                # Find JSON in response
                start = content.find("{")
                end = content.rfind("}") + 1
                if start != -1 and end > start:
                    json_str = content[start:end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # Fallback: try parsing entire content
            return json.loads(content)

        except Exception as e:
            return {"error": str(e)}

    def get_detailed_evaluation(self) -> Dict[str, Any]:
        """Get full evaluation with all details."""
        evaluation = self.evaluate()

        return {
            "model_used": self.judge_model,
            "archetype": self.archetype,
            "evaluation": evaluation,
            "normalized_score": self.compute()
        }


def evaluate_with_llm_judge(
    output: Dict[str, Any],
    profile: Dict[str, Any],
    judge_model: str = "qwen3:32b"
) -> Dict[str, Any]:
    """
    Convenience function to evaluate output with LLM judge.

    Args:
        output: Director output dict
        profile: User profile dict
        judge_model: Model to use as judge

    Returns:
        Evaluation dict with scores
    """
    judge = LLMJudge(output, profile, judge_model)
    return judge.get_detailed_evaluation()
