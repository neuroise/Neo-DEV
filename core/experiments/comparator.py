"""
Experiment Comparator — statistical comparison of experiment runs.

Supports paired (Wilcoxon) and unpaired (Mann-Whitney) tests,
effect size (Cohen's d), and LaTeX table export.

Example:
    >>> comp = ExperimentComparator("data/experiments")
    >>> df = comp.compare_paired("baseline_qwen", "ablation_concise")
    >>> latex = comp.to_latex(df, "Baseline", "Concise")
"""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class ExperimentComparator:
    """Compare two experiment runs with statistical tests."""

    def __init__(self, experiments_dir: str = "data/experiments"):
        self.experiments_dir = Path(experiments_dir)

    def load(self, name: str) -> pd.DataFrame:
        """Load experiment results into a DataFrame.

        Args:
            name: Experiment directory name

        Returns:
            DataFrame with profile_id, model, archetype, and all metric columns
        """
        results_path = self.experiments_dir / name / "results.json"
        with open(results_path) as f:
            data = json.load(f)

        rows = []
        prefix_map = {"S": "sage", "R": "rebel", "L": "lover"}

        for run in data.get("results", []):
            if not run.get("success"):
                continue
            pid = run["profile_id"]
            prefix = pid.split("-")[0]
            row = {
                "profile_id": pid,
                "model": run.get("model", "unknown"),
                "archetype": prefix_map.get(prefix, "unknown"),
            }
            for k, v in run.get("metrics", {}).items():
                if isinstance(v, (int, float)):
                    row[k] = v
            rows.append(row)

        return pd.DataFrame(rows)

    def compare_paired(
        self, exp_a: str, exp_b: str, metric_cols: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Paired comparison using Wilcoxon signed-rank test.

        Matches by profile_id. Returns a DataFrame with:
        mean_a, std_a, mean_b, std_b, p_value, cohens_d, significant

        Args:
            exp_a: First experiment name
            exp_b: Second experiment name
            metric_cols: Specific metrics to compare (default: all M_AUTO + aggregate)
        """
        from scipy.stats import wilcoxon

        df_a = self.load(exp_a)
        df_b = self.load(exp_b)

        if metric_cols is None:
            metric_cols = [
                c for c in df_a.columns
                if c.startswith("M_AUTO") or c == "aggregate_score"
            ]

        # Merge on profile_id for paired comparison
        merged = df_a.merge(df_b, on="profile_id", suffixes=("_a", "_b"))

        rows = []
        for col in metric_cols:
            col_a = f"{col}_a"
            col_b = f"{col}_b"
            if col_a not in merged or col_b not in merged:
                continue

            vals_a = merged[col_a].dropna()
            vals_b = merged[col_b].dropna()

            # Align indices
            common = vals_a.index.intersection(vals_b.index)
            a = vals_a.loc[common].values
            b = vals_b.loc[common].values

            if len(a) < 3:
                continue

            mean_a, std_a = a.mean(), a.std(ddof=1)
            mean_b, std_b = b.mean(), b.std(ddof=1)

            # Wilcoxon test (two-sided)
            try:
                diff = a - b
                if all(d == 0 for d in diff):
                    p_val = 1.0
                else:
                    _, p_val = wilcoxon(a, b)
            except Exception:
                p_val = 1.0

            # Cohen's d
            pooled_std = math.sqrt((std_a**2 + std_b**2) / 2)
            d = (mean_a - mean_b) / pooled_std if pooled_std > 0 else 0.0

            rows.append({
                "metric": col,
                "mean_a": mean_a,
                "std_a": std_a,
                "mean_b": mean_b,
                "std_b": std_b,
                "p_value": p_val,
                "cohens_d": d,
                "significant": p_val < 0.05,
                "n_pairs": len(common),
            })

        return pd.DataFrame(rows)

    def compare_unpaired(
        self, exp_a: str, exp_b: str, metric_cols: Optional[List[str]] = None
    ) -> pd.DataFrame:
        """Unpaired comparison using Mann-Whitney U test.

        Returns same format as compare_paired.
        """
        from scipy.stats import mannwhitneyu

        df_a = self.load(exp_a)
        df_b = self.load(exp_b)

        if metric_cols is None:
            metric_cols = [
                c for c in df_a.columns
                if c.startswith("M_AUTO") or c == "aggregate_score"
            ]

        rows = []
        for col in metric_cols:
            if col not in df_a or col not in df_b:
                continue

            a = df_a[col].dropna().values
            b = df_b[col].dropna().values

            if len(a) < 2 or len(b) < 2:
                continue

            mean_a, std_a = a.mean(), a.std(ddof=1)
            mean_b, std_b = b.mean(), b.std(ddof=1)

            try:
                _, p_val = mannwhitneyu(a, b, alternative="two-sided")
            except Exception:
                p_val = 1.0

            pooled_std = math.sqrt((std_a**2 + std_b**2) / 2)
            d = (mean_a - mean_b) / pooled_std if pooled_std > 0 else 0.0

            rows.append({
                "metric": col,
                "mean_a": mean_a,
                "std_a": std_a,
                "mean_b": mean_b,
                "std_b": std_b,
                "p_value": p_val,
                "cohens_d": d,
                "significant": p_val < 0.05,
                "n_a": len(a),
                "n_b": len(b),
            })

        return pd.DataFrame(rows)

    @staticmethod
    def _significance_stars(p: float) -> str:
        """Return significance stars for p-value."""
        if p < 0.001:
            return "***"
        elif p < 0.01:
            return "**"
        elif p < 0.05:
            return "*"
        return ""

    @staticmethod
    def _short_metric_name(metric: str) -> str:
        """Shorten M_AUTO_XX_name to readable label."""
        labels = {
            "M_AUTO_01_schema_compliance": "Schema",
            "M_AUTO_02_archetype_consistency": "Archetype",
            "M_AUTO_03_role_sequence_valid": "Sequence",
            "M_AUTO_04_story_thread_presence": "Thread",
            "M_AUTO_05_red_flag_score": "Red Flags",
            "M_AUTO_06_prompt_length_valid": "Length",
            "M_AUTO_07_archetype_lexical_fit": "Lexical Fit",
            "M_AUTO_08_cross_scene_coherence": "Coherence",
            "M_AUTO_09_prompt_specificity": "Specificity",
            "M_AUTO_10_marine_vocabulary_ratio": "Marine",
            "M_AUTO_11_score_narrative_coherence": "Narrative",
            "M_AUTO_12_llm_judge_quality": "LLM Judge",
            "M_AUTO_13_pacing_progression": "Pacing",
            "aggregate_score": "Aggregate",
        }
        return labels.get(metric, metric)

    def to_latex(
        self,
        df: pd.DataFrame,
        label_a: str = "Condition A",
        label_b: str = "Condition B",
        caption: str = "Experiment comparison",
        table_label: str = "tab:comparison",
    ) -> str:
        """Generate a LaTeX table from comparison DataFrame.

        Bold best mean, significance stars on p-values.

        Args:
            df: Output from compare_paired or compare_unpaired
            label_a: Display label for experiment A
            label_b: Display label for experiment B
            caption: LaTeX table caption
            table_label: LaTeX label for referencing

        Returns:
            Complete LaTeX table string
        """
        lines = [
            r"\begin{table}[ht]",
            r"\centering",
            rf"\caption{{{caption}}}",
            rf"\label{{{table_label}}}",
            r"\begin{tabular}{lcccc}",
            r"\toprule",
            rf"Metric & {label_a} & {label_b} & $p$ & $d$ \\",
            r"\midrule",
        ]

        for _, row in df.iterrows():
            name = self._short_metric_name(row["metric"])
            ma, sa = row["mean_a"], row["std_a"]
            mb, sb = row["mean_b"], row["std_b"]
            p = row["p_value"]
            d = row["cohens_d"]
            stars = self._significance_stars(p)

            # Bold the better mean
            if ma >= mb:
                cell_a = rf"\textbf{{{ma:.3f}}} {{\scriptsize$\pm${sa:.3f}}}"
                cell_b = rf"{mb:.3f} {{\scriptsize$\pm${sb:.3f}}}"
            else:
                cell_a = rf"{ma:.3f} {{\scriptsize$\pm${sa:.3f}}}"
                cell_b = rf"\textbf{{{mb:.3f}}} {{\scriptsize$\pm${sb:.3f}}}"

            p_str = f"{p:.3f}{stars}" if p >= 0.001 else f"<.001{stars}"
            d_str = f"{d:+.2f}"

            lines.append(rf"{name} & {cell_a} & {cell_b} & {p_str} & {d_str} \\")

        lines.extend([
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
        ])

        return "\n".join(lines)
