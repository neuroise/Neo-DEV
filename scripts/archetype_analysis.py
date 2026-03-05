#!/usr/bin/env python3
"""
Per-archetype analysis of NEUROISE experiment results.

Splits results by archetype (S=Sage, R=Rebel, L=Lover) and computes
per-group statistics. Optionally generates LaTeX tables for the paper.

Usage:
    python scripts/archetype_analysis.py baseline_30_llama70b_v3
    python scripts/archetype_analysis.py baseline_30_llama70b_v3 --latex
    python scripts/archetype_analysis.py exp_a exp_b --compare --latex
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

ARCHETYPE_MAP = {"S": "Sage", "R": "Rebel", "L": "Lover"}

METRIC_LABELS = {
    "M_AUTO_01_schema_compliance": "Schema",
    "M_AUTO_02_archetype_consistency": "Archetype",
    "M_AUTO_03_role_sequence_valid": "Sequence",
    "M_AUTO_04_story_thread_presence": "Thread",
    "M_AUTO_05_red_flag_score": "Red Flags",
    "M_AUTO_06_prompt_length_valid": "Length",
    "M_AUTO_07_archetype_lexical_fit": "Lex. Fit",
    "M_AUTO_08_cross_scene_coherence": "Coherence",
    "M_AUTO_09_prompt_specificity": "Specificity",
    "M_AUTO_10_marine_vocabulary_ratio": "Marine",
    "M_AUTO_11_score_narrative_coherence": "Narrative",
    "M_AUTO_12_llm_judge_quality": "LLM Judge",
    "M_AUTO_13_pacing_progression": "Pacing",
    "aggregate_score": "Aggregate",
}


def load_results(experiment_dir: Path):
    """Load experiment results and split by archetype."""
    results_path = experiment_dir / "results.json"
    with open(results_path) as f:
        data = json.load(f)

    by_archetype = {}
    for run in data.get("results", []):
        if not run.get("success"):
            continue
        pid = run["profile_id"]
        prefix = pid.split("-")[0]
        arch = ARCHETYPE_MAP.get(prefix, "Unknown")
        by_archetype.setdefault(arch, []).append(run)

    return by_archetype, data.get("config", {})


def compute_stats(values):
    """Compute mean, std for a list of values."""
    n = len(values)
    if n == 0:
        return {"mean": 0, "std": 0, "n": 0}
    mean = sum(values) / n
    if n >= 2:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)
    else:
        std = 0
    return {"mean": mean, "std": std, "n": n}


def analyze_single(experiment_name: str, experiments_dir: str = "data/experiments",
                   latex: bool = False):
    """Analyze a single experiment by archetype."""
    exp_dir = Path(experiments_dir) / experiment_name
    by_archetype, config = load_results(exp_dir)

    print(f"\n{'='*70}")
    print(f"Per-Archetype Analysis: {experiment_name}")
    print(f"Model: {config.get('models', ['?'])[0]}  |  "
          f"Prompt Pack: {config.get('prompt_pack', 'default')}")
    print(f"{'='*70}")

    # Collect all metric names
    metric_names = list(METRIC_LABELS.keys())

    # Print table header
    header = f"{'Metric':<20}"
    for arch in ["Sage", "Rebel", "Lover"]:
        header += f"  {arch:>16}"
    print(f"\n{header}")
    print("-" * 70)

    archetype_stats = {}
    for arch in ["Sage", "Rebel", "Lover"]:
        runs = by_archetype.get(arch, [])
        stats = {}
        for m in metric_names:
            values = [r.get("metrics", {}).get(m) for r in runs]
            values = [v for v in values if v is not None]
            stats[m] = compute_stats(values)
        archetype_stats[arch] = stats

    for m in metric_names:
        label = METRIC_LABELS.get(m, m)
        row = f"{label:<20}"
        for arch in ["Sage", "Rebel", "Lover"]:
            s = archetype_stats[arch].get(m, {})
            if s.get("n", 0) > 0:
                row += f"  {s['mean']:.3f}±{s['std']:.3f} "
            else:
                row += f"  {'N/A':>16}"
        print(row)

    print("-" * 70)

    if latex:
        print("\n" + generate_latex_table(archetype_stats, experiment_name))

    return archetype_stats


def generate_latex_table(archetype_stats, experiment_name):
    """Generate LaTeX table for per-archetype results."""
    lines = [
        r"\begin{table}[ht]",
        r"\centering",
        rf"\caption{{Per-archetype results ({experiment_name})}}",
        rf"\label{{tab:archetype_{experiment_name}}}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Metric & Sage & Rebel & Lover \\",
        r"\midrule",
    ]

    for m, label in METRIC_LABELS.items():
        cells = []
        means = []
        for arch in ["Sage", "Rebel", "Lover"]:
            s = archetype_stats[arch].get(m, {})
            means.append(s.get("mean", 0))

        best_idx = means.index(max(means))

        for i, arch in enumerate(["Sage", "Rebel", "Lover"]):
            s = archetype_stats[arch].get(m, {})
            if s.get("n", 0) > 0:
                val = rf"{s['mean']:.3f} {{\scriptsize$\pm${s['std']:.3f}}}"
                if i == best_idx:
                    val = rf"\textbf{{{s['mean']:.3f}}} {{\scriptsize$\pm${s['std']:.3f}}}"
                cells.append(val)
            else:
                cells.append("--")

        lines.append(rf"{label} & {' & '.join(cells)} \\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    return "\n".join(lines)


def analyze_comparison(exp_a: str, exp_b: str,
                       experiments_dir: str = "data/experiments",
                       latex: bool = False):
    """Compare two experiments per-archetype using Wilcoxon signed-rank test."""
    try:
        from scipy.stats import wilcoxon
    except ImportError:
        print("scipy required for paired comparison. Install: pip install scipy")
        sys.exit(1)

    dir_a = Path(experiments_dir) / exp_a
    dir_b = Path(experiments_dir) / exp_b
    by_arch_a, config_a = load_results(dir_a)
    by_arch_b, config_b = load_results(dir_b)

    print(f"\n{'='*80}")
    print(f"Per-Archetype Comparison: {exp_a} vs {exp_b}")
    print(f"{'='*80}")

    for arch in ["Sage", "Rebel", "Lover"]:
        runs_a = {r["profile_id"]: r for r in by_arch_a.get(arch, [])}
        runs_b = {r["profile_id"]: r for r in by_arch_b.get(arch, [])}
        common_pids = sorted(set(runs_a.keys()) & set(runs_b.keys()))

        if not common_pids:
            print(f"\n{arch}: No common profiles")
            continue

        print(f"\n--- {arch} (n={len(common_pids)}) ---")
        print(f"{'Metric':<20} {'A':>8} {'B':>8} {'Δ':>8} {'p':>8}")
        print("-" * 55)

        for m in METRIC_LABELS:
            vals_a = [runs_a[pid].get("metrics", {}).get(m) for pid in common_pids]
            vals_b = [runs_b[pid].get("metrics", {}).get(m) for pid in common_pids]
            vals_a = [v for v in vals_a if v is not None]
            vals_b = [v for v in vals_b if v is not None]

            if len(vals_a) < 3 or len(vals_b) < 3:
                continue

            mean_a = sum(vals_a) / len(vals_a)
            mean_b = sum(vals_b) / len(vals_b)
            delta = mean_b - mean_a

            try:
                diff = [a - b for a, b in zip(vals_a, vals_b)]
                if all(d == 0 for d in diff):
                    p_val = 1.0
                else:
                    _, p_val = wilcoxon(vals_a, vals_b)
            except Exception:
                p_val = 1.0

            stars = "***" if p_val < 0.001 else "**" if p_val < 0.01 else "*" if p_val < 0.05 else ""
            label = METRIC_LABELS.get(m, m)
            print(f"{label:<20} {mean_a:>8.3f} {mean_b:>8.3f} {delta:>+8.3f} {p_val:>7.3f}{stars}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Per-archetype analysis")
    parser.add_argument("experiments", nargs="+",
                        help="Experiment name(s). One for single analysis, two for comparison.")
    parser.add_argument("--compare", action="store_true",
                        help="Compare two experiments")
    parser.add_argument("--latex", action="store_true",
                        help="Generate LaTeX table")
    parser.add_argument("--experiments-dir", default="data/experiments")

    args = parser.parse_args()

    if args.compare or len(args.experiments) == 2:
        if len(args.experiments) != 2:
            print("Comparison requires exactly 2 experiment names")
            sys.exit(1)
        analyze_comparison(args.experiments[0], args.experiments[1],
                           args.experiments_dir, args.latex)
    else:
        for exp in args.experiments:
            analyze_single(exp, args.experiments_dir, args.latex)
