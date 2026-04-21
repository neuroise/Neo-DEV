"""
Test Part B — Unit tests for paper readiness features.

Tests:
- P1: seed in LLMConfig, robust stats (std, CI95), summary_by_archetype
- P2+P4: ExperimentComparator and LaTeX export
- P3: Human evaluation store and inter-rater agreement
- P5: Prompt packs loading
"""

import json
import math
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── P1: Seed + Robust Statistics ─────────────────────────────────

class TestP1_Seed:
    """Test seed in LLMConfig and OllamaAdapter."""

    def test_llm_config_has_seed(self):
        from core.llm.base import LLMConfig
        config = LLMConfig(model="test:7b", seed=42)
        assert config.seed == 42
        d = config.to_dict()
        assert d["seed"] == 42

    def test_llm_config_seed_default_none(self):
        from core.llm.base import LLMConfig
        config = LLMConfig(model="test:7b")
        assert config.seed is None
        d = config.to_dict()
        assert "seed" not in d

    def test_ollama_adapter_seed_in_payload(self):
        """OllamaAdapter should include seed in options when set."""
        from core.llm.base import LLMConfig
        from core.llm.ollama_adapter import OllamaAdapter

        config = LLMConfig(model="test:7b", seed=42)

        with patch.object(OllamaAdapter, "_verify_connection"):
            adapter = OllamaAdapter(config)

        # Mock requests.post to capture the payload
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": '{"test": true}',
            "done": True,
            "prompt_eval_count": 10,
            "eval_count": 20,
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("core.llm.ollama_adapter.requests") as mock_requests:
            mock_requests.post.return_value = mock_resp
            adapter.generate("test prompt")

            call_args = mock_requests.post.call_args
            payload = call_args.kwargs.get("json") or call_args[1].get("json")
            assert payload["options"]["seed"] == 42


class TestP1_Stats:
    """Test robust statistics in ExperimentResults."""

    def test_get_summary_has_std(self):
        from core.experiments.runner import ExperimentResults, ExperimentConfig

        config = ExperimentConfig(name="test", profiles=["S-01", "S-02"], models=["m:7b"])
        results = ExperimentResults(config=config)

        for pid, score in [("S-01", 0.8), ("S-02", 0.9)]:
            results.add_result({
                "profile_id": pid,
                "model": "m:7b",
                "success": True,
                "metrics": {"aggregate_score": score, "M_AUTO_01_schema_compliance": score},
            })

        summary = results.get_summary()
        model_data = summary["models"]["m:7b"]
        assert "std" in model_data["aggregate_score"]
        assert model_data["aggregate_score"]["std"] > 0

    def test_get_summary_has_ci95(self):
        from core.experiments.runner import ExperimentResults, ExperimentConfig

        config = ExperimentConfig(name="test", profiles=[f"S-{i:02d}" for i in range(1, 6)], models=["m:7b"])
        results = ExperimentResults(config=config)

        for i in range(5):
            results.add_result({
                "profile_id": f"S-{i+1:02d}",
                "model": "m:7b",
                "success": True,
                "metrics": {"aggregate_score": 0.7 + i * 0.05},
            })

        summary = results.get_summary()
        agg = summary["models"]["m:7b"]["aggregate_score"]
        assert "ci95_low" in agg
        assert "ci95_high" in agg
        assert agg["ci95_low"] < agg["mean"]
        assert agg["ci95_high"] > agg["mean"]

    def test_get_summary_by_archetype(self):
        from core.experiments.runner import ExperimentResults, ExperimentConfig

        config = ExperimentConfig(name="test", profiles=["S-01", "R-01", "L-01"], models=["m:7b"])
        results = ExperimentResults(config=config)

        for pid, score in [("S-01", 0.8), ("R-01", 0.7), ("L-01", 0.9)]:
            results.add_result({
                "profile_id": pid,
                "model": "m:7b",
                "success": True,
                "metrics": {"aggregate_score": score},
            })

        by_arch = results.get_summary_by_archetype()
        assert "sage" in by_arch
        assert "catalyst" in by_arch  # R-01 resolves to catalyst
        assert "lover" in by_arch
        assert by_arch["sage"]["aggregate_score"]["mean"] == 0.8


class TestP1_RecommendedTemp:
    """Test recommended temperature lookup."""

    def test_known_model_temperature(self):
        from core.llm.ollama_adapter import OllamaAdapter
        assert OllamaAdapter.get_recommended_temperature("qwen3:32b") == 0.6
        assert OllamaAdapter.get_recommended_temperature("llama3.3:70b") == 0.6
        assert OllamaAdapter.get_recommended_temperature("gemma3:27b") == 1.0

    def test_unknown_model_returns_none(self):
        from core.llm.ollama_adapter import OllamaAdapter
        assert OllamaAdapter.get_recommended_temperature("unknown:model") is None


# ─── P2+P4: Comparator + LaTeX ───────────────────────────────────

class TestP2_Comparator:
    """Test ExperimentComparator."""

    def _create_experiment(self, tmp_path, name, scores):
        """Helper to create a fake experiment directory."""
        exp_dir = tmp_path / name
        exp_dir.mkdir()
        results = {
            "results": [
                {
                    "profile_id": pid,
                    "model": "test:7b",
                    "success": True,
                    "metrics": {"aggregate_score": score, "M_AUTO_01_schema_compliance": score},
                }
                for pid, score in scores
            ]
        }
        (exp_dir / "results.json").write_text(json.dumps(results))

    def test_load_experiment(self, tmp_path):
        from core.experiments.comparator import ExperimentComparator

        self._create_experiment(tmp_path, "exp_a", [("S-01", 0.8), ("S-02", 0.9)])
        comp = ExperimentComparator(str(tmp_path))
        df = comp.load("exp_a")
        assert len(df) == 2
        assert "aggregate_score" in df.columns

    def test_compare_paired(self, tmp_path):
        from core.experiments.comparator import ExperimentComparator

        profiles = [(f"S-{i:02d}", 0.7 + i * 0.02) for i in range(1, 6)]
        profiles_b = [(f"S-{i:02d}", 0.6 + i * 0.02) for i in range(1, 6)]

        self._create_experiment(tmp_path, "exp_a", profiles)
        self._create_experiment(tmp_path, "exp_b", profiles_b)

        comp = ExperimentComparator(str(tmp_path))
        df = comp.compare_paired("exp_a", "exp_b")

        assert len(df) > 0
        assert "p_value" in df.columns
        assert "cohens_d" in df.columns
        assert all(0 <= p <= 1 for p in df["p_value"])

    def test_to_latex(self, tmp_path):
        from core.experiments.comparator import ExperimentComparator

        profiles = [(f"S-{i:02d}", 0.7 + i * 0.02) for i in range(1, 6)]
        profiles_b = [(f"S-{i:02d}", 0.6 + i * 0.02) for i in range(1, 6)]

        self._create_experiment(tmp_path, "exp_a", profiles)
        self._create_experiment(tmp_path, "exp_b", profiles_b)

        comp = ExperimentComparator(str(tmp_path))
        df = comp.compare_paired("exp_a", "exp_b")
        latex = comp.to_latex(df, "Baseline", "Ablation")

        assert r"\begin{table}" in latex
        assert r"\end{table}" in latex
        assert "Baseline" in latex
        assert "Ablation" in latex
        assert r"\textbf{" in latex


# ─── P3: Human Evaluation ────────────────────────────────────────

class TestP3_HumanEval:
    """Test human evaluation store and agreement metrics."""

    def test_save_and_load(self, tmp_path):
        from core.metrics.manual.human_eval import HumanEvaluation, HumanEvalStore

        store = HumanEvalStore(str(tmp_path / "eval.jsonl"))
        ev = HumanEvaluation(
            experiment="test_exp",
            profile_id="S-01",
            rater_id="rater_A",
            scores={
                "visual_clarity": 4,
                "archetype_alignment": 5,
                "narrative_coherence": 3,
                "emotional_resonance": 4,
                "marine_adherence": 5,
            },
        )
        store.save(ev)

        loaded = store.load_all()
        assert len(loaded) == 1
        assert loaded[0].profile_id == "S-01"
        assert loaded[0].scores["visual_clarity"] == 4

    def test_load_for_item(self, tmp_path):
        from core.metrics.manual.human_eval import HumanEvaluation, HumanEvalStore

        store = HumanEvalStore(str(tmp_path / "eval.jsonl"))
        for pid in ["S-01", "S-02"]:
            store.save(HumanEvaluation(
                experiment="test_exp",
                profile_id=pid,
                rater_id="rater_A",
                scores={"visual_clarity": 4},
            ))

        items = store.load_for_item("test_exp", "S-01")
        assert len(items) == 1

    def test_mean_score(self):
        from core.metrics.manual.human_eval import HumanEvaluation

        ev = HumanEvaluation(
            experiment="x", profile_id="S-01", rater_id="r",
            scores={"a": 3, "b": 5},
        )
        assert ev.mean_score == 4.0

    def test_cohens_kappa(self, tmp_path):
        from core.metrics.manual.human_eval import HumanEvaluation, HumanEvalStore

        store = HumanEvalStore(str(tmp_path / "eval.jsonl"))

        # Perfect agreement → kappa = 1.0
        for pid in [f"S-{i:02d}" for i in range(1, 6)]:
            for rater in ["rater_A", "rater_B"]:
                store.save(HumanEvaluation(
                    experiment="test_exp",
                    profile_id=pid,
                    rater_id=rater,
                    scores={"visual_clarity": 4},
                ))

        kappa = store.cohens_kappa("test_exp", "rater_A", "rater_B", "visual_clarity")
        assert kappa == 1.0


# ─── P5: Prompt Packs ────────────────────────────────────────────

class TestP5_PromptPacks:
    """Test prompt pack loading."""

    def test_load_default(self):
        from core.llm.prompt_packs import load_prompt_pack
        system_prompt, schema = load_prompt_pack("default")
        assert "NEURØISE" in system_prompt
        assert "video_triptych" in json.dumps(schema)

    def test_load_concise(self):
        from core.llm.prompt_packs import load_prompt_pack
        system_prompt, schema = load_prompt_pack("concise")
        assert "NEURØISE" in system_prompt
        assert len(system_prompt) < 3000  # Concise but includes 5 archetypes

    def test_load_detailed(self):
        from core.llm.prompt_packs import load_prompt_pack
        system_prompt, schema = load_prompt_pack("detailed")
        assert "NEURØISE" in system_prompt
        assert "Camera" in system_prompt or "Lighting" in system_prompt

    def test_load_unknown_raises(self):
        from core.llm.prompt_packs import load_prompt_pack
        with pytest.raises(ValueError, match="Unknown prompt pack"):
            load_prompt_pack("nonexistent")

    def test_available_packs(self):
        from core.llm.prompt_packs import AVAILABLE_PACKS
        assert "default" in AVAILABLE_PACKS
        assert "concise" in AVAILABLE_PACKS
        assert "detailed" in AVAILABLE_PACKS


# ─── ExperimentConfig new fields ─────────────────────────────────

class TestExperimentConfig:
    """Test that ExperimentConfig has all new fields."""

    def test_config_has_seed(self):
        from core.experiments.runner import ExperimentConfig
        config = ExperimentConfig(name="t", profiles=["S-01"], models=["m:7b"], seed=42)
        assert config.seed == 42

    def test_config_has_judge_model(self):
        from core.experiments.runner import ExperimentConfig
        config = ExperimentConfig(name="t", profiles=["S-01"], models=["m:7b"], judge_model="qwen3:32b")
        assert config.judge_model == "qwen3:32b"

    def test_config_has_prompt_pack(self):
        from core.experiments.runner import ExperimentConfig
        config = ExperimentConfig(name="t", profiles=["S-01"], models=["m:7b"], prompt_pack="concise")
        assert config.prompt_pack == "concise"
