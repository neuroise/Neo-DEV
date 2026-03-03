"""
Experiment Runner for batch testing NEURØISE generation.

Runs experiments across multiple profiles and models, collecting metrics.

Example:
    >>> config = ExperimentConfig(
    ...     name="baseline_30",
    ...     profiles=["S-01", "S-02", ...],
    ...     models=["llama3.3:70b", "qwen3:32b"]
    ... )
    >>> runner = ExperimentRunner(config)
    >>> results = runner.run()
    >>> results.save("experiments/baseline_30/")
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from tqdm import tqdm

from core.llm import create_adapter, Director
from core.metrics.automatic import compute_all_automatic_metrics
from core.gating import PolicyGate


@dataclass
class ExperimentConfig:
    """Configuration for an experiment run."""

    name: str
    profiles: List[str]  # Profile IDs to test
    models: List[str]  # Models to test

    # Generation settings
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 300

    # Experiment settings
    runs_per_profile: int = 1  # For variance measurement
    save_outputs: bool = True
    verbose: bool = True

    # Paths
    profiles_dir: str = "data/profiles/official"
    output_dir: str = "data/experiments"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "profiles": self.profiles,
            "models": self.models,
            "temperature": self.temperature,
            "runs_per_profile": self.runs_per_profile,
            "timestamp": datetime.now().isoformat()
        }


@dataclass
class ExperimentResults:
    """Results from an experiment run."""

    config: ExperimentConfig
    results: List[Dict[str, Any]] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    # Aggregated stats
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0

    def add_result(self, result: Dict[str, Any]):
        """Add a single run result."""
        self.results.append(result)
        self.total_runs += 1
        if result.get("success"):
            self.successful_runs += 1
        else:
            self.failed_runs += 1

    def get_metrics_by_model(self) -> Dict[str, Dict[str, List[float]]]:
        """Group metrics by model for comparison."""
        by_model = {}

        for result in self.results:
            if not result.get("success"):
                continue

            model = result["model"]
            if model not in by_model:
                by_model[model] = {}

            metrics = result.get("metrics", {})
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    if metric_name not in by_model[model]:
                        by_model[model][metric_name] = []
                    by_model[model][metric_name].append(value)

        return by_model

    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        by_model = self.get_metrics_by_model()

        summary = {
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": self.successful_runs / self.total_runs if self.total_runs > 0 else 0,
            "models": {}
        }

        for model, metrics in by_model.items():
            model_summary = {}
            for metric_name, values in metrics.items():
                if values:
                    model_summary[metric_name] = {
                        "mean": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values)
                    }
            summary["models"][model] = model_summary

        return summary

    def save(self, output_dir: str = None):
        """Save results to disk."""
        self.end_time = datetime.now()

        out_dir = Path(output_dir or self.config.output_dir) / self.config.name
        out_dir.mkdir(parents=True, exist_ok=True)

        # Save full results
        results_file = out_dir / "results.json"
        with open(results_file, "w") as f:
            json.dump({
                "config": self.config.to_dict(),
                "summary": self.get_summary(),
                "results": self.results,
                "duration_seconds": (self.end_time - self.start_time).total_seconds()
            }, f, indent=2, default=str)

        # Save summary separately
        summary_file = out_dir / "summary.json"
        with open(summary_file, "w") as f:
            json.dump(self.get_summary(), f, indent=2)

        # Save JSONL (one line per run, for streaming / quick inspection)
        self._save_jsonl(out_dir)

        return out_dir

    def _save_jsonl(self, out_dir: Path):
        """Save results as JSONL — one JSON object per line per run."""
        jsonl_file = out_dir / "results.jsonl"
        with open(jsonl_file, "w") as f:
            for r in self.results:
                f.write(json.dumps(r, default=str) + "\n")

    def to_dataframe(self):
        """Convert results to pandas DataFrame (if available)."""
        try:
            import pandas as pd

            rows = []
            for result in self.results:
                if not result.get("success"):
                    continue

                row = {
                    "profile_id": result["profile_id"],
                    "model": result["model"],
                    "policy_flag": result.get("policy_flag", "unknown"),
                    "latency_ms": result.get("latency_ms", 0),
                }
                row.update(result.get("metrics", {}))
                rows.append(row)

            return pd.DataFrame(rows)
        except ImportError:
            return None


class ExperimentRunner:
    """
    Runs batch experiments across profiles and models.

    Example:
        >>> runner = ExperimentRunner(config)
        >>> results = runner.run()
        >>> print(results.get_summary())
    """

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.policy_gate = PolicyGate()

    def load_profile(self, profile_id: str) -> Dict[str, Any]:
        """Load a profile by ID."""
        profile_path = Path(self.config.profiles_dir) / f"{profile_id}.json"
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile not found: {profile_path}")

        with open(profile_path) as f:
            return json.load(f)

    def run(self) -> ExperimentResults:
        """
        Run the full experiment.

        Returns:
            ExperimentResults with all metrics and outputs
        """
        results = ExperimentResults(config=self.config)

        # Calculate total iterations
        total = len(self.config.profiles) * len(self.config.models) * self.config.runs_per_profile

        if self.config.verbose:
            print(f"\n{'='*60}")
            print(f"NEURØISE Experiment: {self.config.name}")
            print(f"{'='*60}")
            print(f"Profiles: {len(self.config.profiles)}")
            print(f"Models: {len(self.config.models)}")
            print(f"Runs per profile: {self.config.runs_per_profile}")
            print(f"Total iterations: {total}")
            print(f"{'='*60}\n")

        # Progress bar
        pbar = tqdm(total=total, disable=not self.config.verbose)

        for model in self.config.models:
            if self.config.verbose:
                print(f"\n--- Model: {model} ---")

            # Initialize adapter once per model
            try:
                adapter = create_adapter(
                    model,
                    temperature=self.config.temperature,
                    timeout=self.config.timeout
                )
                director = Director(adapter)
            except Exception as e:
                if self.config.verbose:
                    print(f"Failed to initialize {model}: {e}")
                # Record failures for all profiles
                for profile_id in self.config.profiles:
                    for _ in range(self.config.runs_per_profile):
                        results.add_result({
                            "profile_id": profile_id,
                            "model": model,
                            "success": False,
                            "error": f"Model init failed: {str(e)}"
                        })
                        pbar.update(1)
                continue

            for profile_id in self.config.profiles:
                try:
                    profile = self.load_profile(profile_id)
                except FileNotFoundError as e:
                    for _ in range(self.config.runs_per_profile):
                        results.add_result({
                            "profile_id": profile_id,
                            "model": model,
                            "success": False,
                            "error": str(e)
                        })
                        pbar.update(1)
                    continue

                for run_idx in range(self.config.runs_per_profile):
                    result = self._run_single(
                        profile_id=profile_id,
                        profile=profile,
                        model=model,
                        director=director,
                        run_idx=run_idx
                    )
                    results.add_result(result)
                    pbar.update(1)

                    # Update progress description
                    pbar.set_description(f"{profile_id} | {model.split(':')[0]}")

        pbar.close()

        # Save results
        if self.config.save_outputs:
            out_dir = results.save()
            if self.config.verbose:
                print(f"\nResults saved to: {out_dir}")

        # Print summary
        if self.config.verbose:
            self._print_summary(results)

        return results

    def _run_single(
        self,
        profile_id: str,
        profile: Dict[str, Any],
        model: str,
        director: Director,
        run_idx: int
    ) -> Dict[str, Any]:
        """Run a single generation + evaluation."""

        result = {
            "profile_id": profile_id,
            "model": model,
            "run_idx": run_idx,
            "timestamp": datetime.now().isoformat()
        }

        try:
            # Generate
            start_time = time.time()
            output = director.generate(profile)
            latency_ms = (time.time() - start_time) * 1000

            output_dict = output.to_dict()

            # Policy check
            policy_result = self.policy_gate.check(output_dict, profile)

            # Compute metrics
            metrics = compute_all_automatic_metrics(output_dict, profile)

            result.update({
                "success": True,
                "output": output_dict if self.config.save_outputs else None,
                "policy_flag": policy_result.flag.value,
                "policy_violations": len(policy_result.violations),
                "policy_warnings": len(policy_result.warnings),
                "metrics": metrics,
                "latency_ms": latency_ms
            })

        except Exception as e:
            result.update({
                "success": False,
                "error": str(e)
            })

        return result

    def _print_summary(self, results: ExperimentResults):
        """Print experiment summary."""
        summary = results.get_summary()

        print(f"\n{'='*60}")
        print("EXPERIMENT SUMMARY")
        print(f"{'='*60}")
        print(f"Total runs: {summary['total_runs']}")
        print(f"Successful: {summary['successful_runs']}")
        print(f"Failed: {summary['failed_runs']}")
        print(f"Success rate: {summary['success_rate']:.1%}")

        print(f"\n--- Metrics by Model ---")
        for model, metrics in summary["models"].items():
            print(f"\n{model}:")
            if "aggregate_score" in metrics:
                agg = metrics["aggregate_score"]
                print(f"  Aggregate Score: {agg['mean']:.3f} (min={agg['min']:.3f}, max={agg['max']:.3f})")

            # Show key metrics
            key_metrics = [
                "M_AUTO_01_schema_compliance",
                "M_AUTO_02_archetype_consistency",
                "M_AUTO_05_red_flag_score"
            ]
            for m in key_metrics:
                if m in metrics:
                    print(f"  {m.split('_', 3)[-1]}: {metrics[m]['mean']:.3f}")

        print(f"{'='*60}\n")


def run_quick_experiment(
    profiles: List[str] = None,
    models: List[str] = None,
    name: str = None
) -> ExperimentResults:
    """
    Quick helper to run an experiment.

    Args:
        profiles: Profile IDs (default: first 5 S profiles)
        models: Model names (default: llama3.2:3b)
        name: Experiment name (default: auto-generated)

    Returns:
        ExperimentResults
    """
    if profiles is None:
        profiles = [f"S-{i:02d}" for i in range(1, 6)]

    if models is None:
        models = ["llama3.2:3b"]

    if name is None:
        name = f"quick_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    config = ExperimentConfig(
        name=name,
        profiles=profiles,
        models=models
    )

    runner = ExperimentRunner(config)
    return runner.run()
