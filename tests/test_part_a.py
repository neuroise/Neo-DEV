"""
Test Part A — Offline unit tests for all Part A fixes (v0.2.0).

Tests cover:
- F1: BPM injection from profile when missing + PolicyGate R008
- F2: System prompt format rules (PROMPT FORMAT RULES, GOOD/BAD examples)
- F3: Temperature clamping in OllamaAdapter
- F4: Experiment results JSONL export
- F5: Profiles module importability and Streamlit integration
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ─── F1: BPM Injection ────────────────────────────────────────────

class TestF1_BPM:
    """Test BPM injection from profile and PolicyGate R008."""

    PROFILE_SAGE = {
        "meta": {"case_id": "S-01"},
        "user_profile": {
            "primary_archetype": "sage",
            "music_seed": {"top_genre": "ambient", "bpm": 72, "mood_tag": "contemplative"},
            "story_thread_hint": "stillness and reflection",
        },
    }

    def _make_result(self, ost_bpm=None):
        """Build a minimal valid Director result dict."""
        ost = {"prompt": "Ambient synth pad", "genre": "ambient", "mood": "serene"}
        if ost_bpm is not None:
            ost["bpm"] = ost_bpm
        return {
            "video_triptych": [
                {"scene_role": "start", "prompt": "Wide aerial of ocean waves at dawn", "duration_hint": 5, "mood_tags": ["calm"]},
                {"scene_role": "evolve", "prompt": "Camera descends toward turquoise water surface", "duration_hint": 5, "mood_tags": ["meditative"]},
                {"scene_role": "end", "prompt": "Slow zoom on horizon line at golden hour", "duration_hint": 5, "mood_tags": ["peaceful"]},
            ],
            "ost_prompt": ost,
            "metadata": {"archetype_detected": "sage"},
        }

    def test_parse_result_injects_bpm_from_profile_when_missing(self):
        """Director._parse_result() should inject BPM from profile if LLM omits it."""
        from core.llm.director import Director

        result = self._make_result(ost_bpm=None)
        output = Director._parse_result(result, profile=self.PROFILE_SAGE)
        assert output.ost_prompt.get("bpm") == 72

    def test_parse_result_keeps_existing_bpm(self):
        """If the LLM already provides bpm, it should NOT be overwritten."""
        from core.llm.director import Director

        result = self._make_result(ost_bpm=65)
        output = Director._parse_result(result, profile=self.PROFILE_SAGE)
        assert output.ost_prompt["bpm"] == 65

    def test_policy_gate_r008_flags_missing_bpm(self):
        """R008a should produce a RED violation when bpm is absent."""
        from core.gating.policy_gate import PolicyGate, PolicyFlag

        gate = PolicyGate()
        result_dict = self._make_result(ost_bpm=None)
        pr = gate.check(result_dict, self.PROFILE_SAGE)

        r008a = [v for v in pr.violations if v.rule_id == "R008a"]
        assert len(r008a) == 1
        assert r008a[0].severity == PolicyFlag.RED

    def test_policy_gate_r008_bpm_out_of_range(self):
        """R008b should produce a YELLOW warning when BPM is outside archetype range."""
        from core.gating.policy_gate import PolicyGate, PolicyFlag

        gate = PolicyGate()
        # Sage range is 60-80; 100 is out-of-range
        result_dict = self._make_result(ost_bpm=100)
        pr = gate.check(result_dict, self.PROFILE_SAGE)

        r008b = [w for w in pr.warnings if w.rule_id == "R008b"]
        assert len(r008b) == 1
        assert r008b[0].severity == PolicyFlag.YELLOW

    def test_policy_gate_r008_passes_for_valid_bpm(self):
        """R008 should pass when BPM is present and in range."""
        from core.gating.policy_gate import PolicyGate

        gate = PolicyGate()
        result_dict = self._make_result(ost_bpm=72)
        pr = gate.check(result_dict, self.PROFILE_SAGE)
        assert "R008_bpm" in pr.passed_rules


# ─── F2: System Prompt Format Rules ───────────────────────────────

class TestF2:
    """Test that the Director system prompt contains PROMPT FORMAT RULES."""

    def test_system_prompt_contains_format_rules(self):
        from core.llm.director import DIRECTOR_SYSTEM_PROMPT

        assert "PROMPT FORMAT RULES" in DIRECTOR_SYSTEM_PROMPT
        assert "GOOD example" in DIRECTOR_SYSTEM_PROMPT
        assert "BAD example" in DIRECTOR_SYSTEM_PROMPT

    def test_system_prompt_forbids_narration(self):
        from core.llm.director import DIRECTOR_SYSTEM_PROMPT

        prompt_lower = DIRECTOR_SYSTEM_PROMPT.lower()
        # Should mention forbidden phrases
        assert "we see" in prompt_lower
        assert "accompanied by" in prompt_lower


# ─── F3: Temperature Clamping ─────────────────────────────────────

class TestF3:
    """Test OllamaAdapter temperature clamping."""

    def _make_adapter(self, temperature):
        """Create OllamaAdapter with mocked connection check."""
        from core.llm.base import LLMConfig
        from core.llm.ollama_adapter import OllamaAdapter

        config = LLMConfig(model="test:7b", temperature=temperature)

        with patch.object(OllamaAdapter, "_verify_connection"):
            adapter = OllamaAdapter(config)
        return adapter

    def test_clamp_high_temperature(self):
        adapter = self._make_adapter(30.0)
        assert adapter.config.temperature == 2.0

    def test_clamp_negative_temperature(self):
        adapter = self._make_adapter(-1.0)
        assert adapter.config.temperature == 0.0

    def test_valid_temperature_unchanged(self):
        adapter = self._make_adapter(0.7)
        assert adapter.config.temperature == 0.7


# ─── F4: JSONL Export ─────────────────────────────────────────────

class TestF4:
    """Test that ExperimentResults.save() writes a results.jsonl."""

    def test_experiment_results_save_jsonl(self, tmp_path):
        from core.experiments.runner import ExperimentResults, ExperimentConfig

        config = ExperimentConfig(
            name="test_run",
            profiles=["S-01"],
            models=["test:7b"],
            output_dir=str(tmp_path),
        )
        results = ExperimentResults(config=config)
        results.add_result({
            "profile_id": "S-01",
            "model": "test:7b",
            "success": True,
            "metrics": {"aggregate_score": 0.85},
        })

        out_dir = results.save(str(tmp_path))
        jsonl_path = Path(out_dir) / "results.jsonl"
        assert jsonl_path.exists()

        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["profile_id"] == "S-01"


# ─── F5: Profiles Module ─────────────────────────────────────────

class TestF5:
    """Test profiles module importability and Streamlit integration."""

    def test_profiles_module_importable(self):
        from app.views.profiles import render_profiles, _save_profile, _load_profile
        assert callable(render_profiles)
        assert callable(_save_profile)
        assert callable(_load_profile)

    def test_profiles_in_sidebar(self):
        """main.py should reference Profiles page and render_profiles."""
        main_src = (PROJECT_ROOT / "app" / "main.py").read_text()
        assert "Profiles" in main_src
        assert "render_profiles" in main_src
