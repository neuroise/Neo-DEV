#!/usr/bin/env python3
"""
Generate all LaTeX tables and figures data for the ACM MM 2026 paper.

Produces:
1. Table 1: Overall metrics comparison (baseline vs ablations)
2. Table 2: Per-archetype breakdown
3. Table 3: Cross-model comparison
4. Table 4: Policy compliance by archetype
5. Stats summary in console

Usage:
    python scripts/generate_paper_tables.py
    python scripts/generate_paper_tables.py --output-dir paper/tables/
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


ARCHETYPE_MAP = {"S": "Sage", "R": "Rebel", "L": "Lover"}

METRIC_LABELS = {
    "M_AUTO_01_schema_compliance": "Schema Compliance",
    "M_AUTO_02_archetype_consistency": "Archetype Consistency",
    "M_AUTO_03_role_sequence_valid": "Role Sequence",
    "M_AUTO_04_story_thread_presence": "Story Thread",
    "M_AUTO_05_red_flag_score": "Red Flag Score",
    "M_AUTO_06_prompt_length_valid": "Prompt Length",
    "M_AUTO_07_archetype_lexical_fit": "Lexical Fit",
    "M_AUTO_08_cross_scene_coherence": "Cross-Scene Coherence",
    "M_AUTO_09_prompt_specificity": "Prompt Specificity",
    "M_AUTO_10_marine_vocabulary_ratio": "Marine Vocabulary",
    "M_AUTO_11_score_narrative_coherence": "Narrative Coherence",
    "M_AUTO_12_llm_judge_quality": "LLM-as-Judge",
    "M_AUTO_13_pacing_progression": "Pacing Progression",
    "aggregate_score": "\\textbf{Aggregate}",
}

SHORT_LABELS = {
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
    "aggregate_score": "\\textbf{Aggregate}",
}


def load_experiment(experiments_dir, name):
    """Load experiment results.json."""
    path = Path(experiments_dir) / name / "results.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def get_metric_values(data, metric):
    """Extract metric values from all successful runs."""
    values = []
    for run in data.get("results", []):
        if run.get("success"):
            v = run.get("metrics", {}).get(metric)
            if isinstance(v, (int, float)):
                values.append(v)
    return values


def stats(values):
    """Compute mean ± std."""
    if not values:
        return 0, 0
    import math
    n = len(values)
    mean = sum(values) / n
    if n >= 2:
        var = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(var)
    else:
        std = 0
    return mean, std


def generate_table_1_ablation(experiments_dir, output_dir):
    """Table 1: Prompt Pack Ablation (Default vs Concise vs Detailed)."""
    experiments = {
        "Default": "baseline_30_llama70b_v3",
        "Concise": "ablation_concise_llama70b",
        "Detailed": "ablation_detailed_llama70b",
    }

    datasets = {}
    for label, name in experiments.items():
        data = load_experiment(experiments_dir, name)
        if data:
            datasets[label] = data
        else:
            print(f"  [skip] {name} not found")

    if len(datasets) < 2:
        print("  Need at least 2 experiments for ablation table")
        return

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Prompt pack ablation study. All experiments use LLaMA 3.3:70B at $T{=}0.7$ on 30 profiles. Bold indicates best mean per metric.}",
        r"\label{tab:ablation}",
        r"\resizebox{\columnwidth}{!}{%",
        r"\begin{tabular}{l" + "c" * len(datasets) + "}",
        r"\toprule",
    ]

    header = "Metric"
    for label in datasets:
        header += f" & {label}"
    header += r" \\"
    lines.append(header)
    lines.append(r"\midrule")

    for metric in METRIC_LABELS:
        means = {}
        for label, data in datasets.items():
            values = get_metric_values(data, metric)
            m, s = stats(values)
            means[label] = (m, s)

        best_label = max(means, key=lambda l: means[l][0])
        label_str = SHORT_LABELS.get(metric, metric)
        row = label_str

        for label in datasets:
            m, s = means[label]
            if label == best_label and m > 0:
                row += rf" & \textbf{{{m:.3f}}} {{\scriptsize$\pm${s:.3f}}}"
            else:
                row += rf" & {m:.3f} {{\scriptsize$\pm${s:.3f}}}"

        row += r" \\"
        lines.append(row)

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}}",
        r"\end{table}",
    ])

    table = "\n".join(lines)
    print("\n=== Table 1: Prompt Pack Ablation ===")
    print(table)

    if output_dir:
        (Path(output_dir) / "tab_ablation.tex").write_text(table)


def generate_table_2_archetype(experiments_dir, output_dir):
    """Table 2: Per-archetype breakdown for baseline."""
    data = load_experiment(experiments_dir, "baseline_30_llama70b_v3")
    if not data:
        print("  [skip] baseline not found")
        return

    # Split by archetype
    by_arch = {}
    for run in data.get("results", []):
        if not run.get("success"):
            continue
        pid = run["profile_id"]
        prefix = pid.split("-")[0]
        arch = ARCHETYPE_MAP.get(prefix, "?")
        by_arch.setdefault(arch, []).append(run)

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Per-archetype performance breakdown (LLaMA 3.3:70B, default prompt, $n{=}10$ per archetype). Bold indicates best mean.}",
        r"\label{tab:archetype}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"Metric & Sage & Rebel & Lover \\",
        r"\midrule",
    ]

    archetypes = ["Sage", "Rebel", "Lover"]

    for metric in METRIC_LABELS:
        means = {}
        for arch in archetypes:
            runs = by_arch.get(arch, [])
            values = [r.get("metrics", {}).get(metric) for r in runs
                      if isinstance(r.get("metrics", {}).get(metric), (int, float))]
            m, s = stats(values)
            means[arch] = (m, s)

        best = max(archetypes, key=lambda a: means[a][0])
        label = SHORT_LABELS.get(metric, metric)
        row = label

        for arch in archetypes:
            m, s = means[arch]
            if arch == best and m > 0:
                row += rf" & \textbf{{{m:.3f}}} {{\scriptsize$\pm${s:.3f}}}"
            else:
                row += rf" & {m:.3f} {{\scriptsize$\pm${s:.3f}}}"
        row += r" \\"
        lines.append(row)

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    table = "\n".join(lines)
    print("\n=== Table 2: Per-Archetype Breakdown ===")
    print(table)

    if output_dir:
        (Path(output_dir) / "tab_archetype.tex").write_text(table)


def generate_table_3_crossmodel(experiments_dir, output_dir):
    """Table 3: Cross-model comparison."""
    experiments = {
        "LLaMA 3.3:70B": "baseline_30_llama70b_v3",
        "Qwen3:32B": "baseline_30_qwen32b",
    }

    datasets = {}
    for label, name in experiments.items():
        data = load_experiment(experiments_dir, name)
        if data:
            datasets[label] = data
        else:
            print(f"  [skip] {name} not found")

    if len(datasets) < 2:
        print("  Need at least 2 models for cross-model table")
        return

    try:
        from core.experiments.comparator import ExperimentComparator
        comp = ExperimentComparator(experiments_dir)
        names = list(experiments.values())
        df = comp.compare_paired(names[0], names[1])
        labels = list(experiments.keys())
        latex = comp.to_latex(df, labels[0], labels[1],
                              caption="Cross-model comparison (paired Wilcoxon signed-rank test, $n{=}30$)",
                              table_label="tab:crossmodel")
        print("\n=== Table 3: Cross-Model Comparison ===")
        print(latex)
        if output_dir:
            (Path(output_dir) / "tab_crossmodel.tex").write_text(latex)
    except Exception as e:
        print(f"  Cross-model comparison error: {e}")


def generate_table_4_policy(experiments_dir, output_dir):
    """Table 4: Policy compliance by archetype."""
    data = load_experiment(experiments_dir, "baseline_30_llama70b_v3")
    if not data:
        print("  [skip] baseline not found")
        return

    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{PolicyGate compliance by archetype ($n{=}10$ per archetype). Rebel profiles trigger significantly more policy violations.}",
        r"\label{tab:policy}",
        r"\begin{tabular}{lccc}",
        r"\toprule",
        r"& Sage & Rebel & Lover \\",
        r"\midrule",
    ]

    by_arch = {}
    for run in data.get("results", []):
        if not run.get("success"):
            continue
        pid = run["profile_id"]
        prefix = pid.split("-")[0]
        arch = ARCHETYPE_MAP.get(prefix, "?")
        by_arch.setdefault(arch, []).append(run)

    for arch in ["Sage", "Rebel", "Lover"]:
        runs = by_arch.get(arch, [])
        flags = Counter(r.get("policy_flag", "?") for r in runs)
        by_arch[arch + "_flags"] = flags

    # Green count
    row_green = "Green (pass)"
    row_yellow = "Yellow (warn)"
    row_red = "Red (fail)"
    for arch in ["Sage", "Rebel", "Lover"]:
        flags = by_arch.get(arch + "_flags", Counter())
        row_green += f" & {flags.get('green', 0)}"
        row_yellow += f" & {flags.get('yellow', 0)}"
        row_red += f" & {flags.get('red', 0)}"

    lines.append(row_green + r" \\")
    lines.append(row_yellow + r" \\")
    lines.append(row_red + r" \\")

    # Avg violations
    row_violations = "Avg. violations"
    for arch in ["Sage", "Rebel", "Lover"]:
        runs = by_arch.get(arch, [])
        avg_v = sum(r.get("policy_violations", 0) for r in runs) / max(len(runs), 1)
        row_violations += f" & {avg_v:.1f}"
    lines.append(row_violations + r" \\")

    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ])

    table = "\n".join(lines)
    print("\n=== Table 4: Policy Compliance ===")
    print(table)

    if output_dir:
        (Path(output_dir) / "tab_policy.tex").write_text(table)


def print_summary_stats(experiments_dir):
    """Print key stats for paper text."""
    data = load_experiment(experiments_dir, "baseline_30_llama70b_v3")
    if not data:
        return

    print("\n=== Key Stats for Paper ===")

    # Overall
    agg = get_metric_values(data, "aggregate_score")
    m, s = stats(agg)
    print(f"Baseline aggregate: {m:.3f} ± {s:.3f} (n={len(agg)})")

    # Per archetype aggregates
    for prefix, name in ARCHETYPE_MAP.items():
        vals = [r.get("metrics", {}).get("aggregate_score", 0)
                for r in data["results"]
                if r.get("success") and r["profile_id"].startswith(prefix)]
        m, s = stats(vals)
        print(f"  {name}: {m:.3f} ± {s:.3f}")

    # Latency
    latencies = [r.get("latency_ms", 0) for r in data["results"] if r.get("success")]
    m_lat, s_lat = stats(latencies)
    print(f"Latency: {m_lat/1000:.1f}s ± {s_lat/1000:.1f}s per profile")

    # Policy
    flags = Counter(r.get("policy_flag", "?") for r in data["results"] if r.get("success"))
    print(f"Policy flags: {dict(flags)}")
    print(f"Green rate: {flags.get('green', 0)}/{sum(flags.values())} = {flags.get('green', 0)/max(sum(flags.values()), 1):.1%}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate paper tables")
    parser.add_argument("--experiments-dir", default="data/experiments")
    parser.add_argument("--output-dir", default=None,
                        help="Directory to save .tex files")

    args = parser.parse_args()

    if args.output_dir:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    print("Generating paper tables...")
    print(f"Experiments dir: {args.experiments_dir}")

    available = sorted([d.name for d in Path(args.experiments_dir).iterdir() if d.is_dir()])
    print(f"Available experiments: {', '.join(available)}")
    print()

    generate_table_1_ablation(args.experiments_dir, args.output_dir)
    generate_table_2_archetype(args.experiments_dir, args.output_dir)
    generate_table_3_crossmodel(args.experiments_dir, args.output_dir)
    generate_table_4_policy(args.experiments_dir, args.output_dir)
    print_summary_stats(args.experiments_dir)


if __name__ == "__main__":
    main()
