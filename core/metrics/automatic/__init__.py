# Automatic Metrics Module
from .schema_metrics import SchemaMetrics
from .lexical_metrics import LexicalMetrics
from .semantic_metrics import SemanticMetrics
from .score_coherence import ScoreCoherence
from .pacing_metrics import PacingMetrics
from .llm_judge import LLMJudge, evaluate_with_llm_judge


def compute_all_automatic_metrics(
    output: dict,
    profile: dict,
    judge_model: str = "qwen3:32b",
    judge_num_ctx: int = None
) -> dict:
    """
    Compute all automatic metrics (M_AUTO_01-13) for a Director output.

    Args:
        output: DirectorOutput.to_dict() or equivalent
        profile: User profile dict
        judge_model: Model for LLM-as-Judge (default: qwen3:32b)
        judge_num_ctx: Ollama context window for judge (reduces VRAM)

    Returns:
        Dict with all metric scores (0.0-1.0)
    """
    results = {}

    # Schema metrics (M_AUTO_01-06)
    schema = SchemaMetrics(output, profile)
    results.update(schema.compute_all())

    # Lexical metrics (M_AUTO_07, M_AUTO_10)
    lexical = LexicalMetrics(output, profile)
    results.update(lexical.compute_all())

    # Semantic metrics (M_AUTO_08, M_AUTO_09)
    semantic = SemanticMetrics(output, profile)
    results.update(semantic.compute_all())

    # SCORE coherence (M_AUTO_11)
    score = ScoreCoherence(output, profile)
    results["M_AUTO_11_score_narrative_coherence"] = score.compute()

    # LLM-as-Judge (M_AUTO_12)
    judge = LLMJudge(output, profile, judge_model, num_ctx=judge_num_ctx)
    results["M_AUTO_12_llm_judge_quality"] = judge.compute()

    # Pacing progression (M_AUTO_13)
    pacing = PacingMetrics(output, profile)
    results["M_AUTO_13_pacing_progression"] = pacing.compute()

    # Aggregate score
    scores = [v for k, v in results.items()
              if isinstance(v, (int, float)) and k.startswith("M_AUTO")]
    results["aggregate_score"] = sum(scores) / len(scores) if scores else 0.0

    return results


__all__ = [
    "compute_all_automatic_metrics",
    "SchemaMetrics",
    "LexicalMetrics",
    "SemanticMetrics",
    "ScoreCoherence",
    "PacingMetrics",
    "LLMJudge",
    "evaluate_with_llm_judge",
]
