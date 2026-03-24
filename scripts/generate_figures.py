#!/usr/bin/env python3
"""
Generate figures for ACM MM 2026 paper.

Produces PDF vector figures for LaTeX inclusion:
  1. pipeline.pdf    - Cognitive Sandwich architecture diagram
  2. radar.pdf       - Archetype radar plot (Sage/Rebel/Lover)
  3. ablation.pdf    - Ablation bar chart (Default/Concise/Detailed)
  4. crossmodel.pdf  - Cross-model comparison with significance markers
  5. policy.pdf      - Policy compliance stacked bar

Usage:
    python scripts/generate_figures.py [--output-dir paper/figures]
"""

import argparse
import json
import sys
from pathlib import Path
import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# Style
plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 10,
    "axes.titlesize": 11,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
})

# Color palette
COLORS = {
    "sage": "#6B7280",
    "rebel": "#EF4444",
    "lover": "#EC4899",
    "default": "#667eea",
    "concise": "#f59e0b",
    "detailed": "#10b981",
    "llama": "#3b82f6",
    "qwen": "#8b5cf6",
    "green": "#22c55e",
    "yellow": "#eab308",
    "red": "#ef4444",
}


# =============================================================================
# Data from paper tables (hardcoded for reproducibility)
# =============================================================================

METRICS_SHORT = [
    "Schema", "Archetype", "Sequence", "Thread", "Red Flags",
    "Length", "Lex. Fit", "Coherence", "Specificity",
    "Marine", "Narrative", "LLM Judge", "Pacing",
]

# Per-archetype data (from tab_archetype.tex)
ARCHETYPE_DATA = {
    "Sage":  [1.000, 0.911, 1.000, 0.833, 0.715, 0.993, 0.437, 0.608, 0.752, 0.730, 0.524, 0.765, 0.997],
    "Rebel": [1.000, 0.589, 1.000, 0.733, 0.775, 0.985, 0.274, 0.504, 0.368, 0.721, 0.569, 0.725, 0.933],
    "Lover": [1.000, 0.867, 1.000, 0.900, 0.775, 1.000, 0.538, 0.654, 0.485, 0.706, 0.559, 0.820, 0.924],
}

# Ablation data (from tab_ablation.tex)
ABLATION_DATA = {
    "Default":  [1.000, 0.789, 1.000, 0.822, 0.755, 0.992, 0.416, 0.588, 0.535, 0.719, 0.550, 0.770, 0.951],
    "Concise":  [1.000, 0.726, 1.000, 0.772, 0.830, 0.998, 0.458, 0.137, 0.542, 0.721, 0.661, 0.967, 0.923],
    "Detailed": [1.000, 0.770, 1.000, 0.711, 0.835, 0.998, 0.399, 0.140, 0.692, 0.711, 0.568, 0.958, 0.888],
}

ABLATION_AGG = {"Default": 0.775, "Concise": 0.749, "Detailed": 0.744}

# Cross-model data (from tab_crossmodel.tex, 5 models)
CROSSMODEL_DATA = {
    "LLaMA 3.3:70B": [1.000, 0.789, 1.000, 0.822, 0.755, 0.993, 0.416, 0.588, 0.535, 0.719, 0.550, 0.770, 0.951],
    "Qwen3:32B":     [0.964, 0.770, 0.929, 0.720, 0.759, 0.979, 0.346, 0.102, 0.731, 0.679, 0.546, 0.996, 0.950],
    "Qwen3:8B":      [1.000, 0.796, 1.000, 0.789, 0.825, 1.000, 0.393, 0.509, 0.514, 0.700, 0.558, 0.958, 0.910],
    "Ministral-3:14B":[1.000, 0.663, 1.000, 0.756, 0.705, 1.000, 0.345, 0.480, 0.520, 0.695, 0.545, 0.945, 0.895],
    "GPT-4o":        [1.000, 0.856, 1.000, 0.844, 0.820, 1.000, 0.554, 0.509, 0.583, 0.687, 0.572, 0.975, 0.889],
    "GPT-5.4":       [1.000, 0.804, 1.000, 0.922, 0.705, 0.960, 0.453, 0.559, 0.538, 0.711, 0.656, 1.000, 0.964],
}

CROSSMODEL_COLORS = {
    "LLaMA 3.3:70B": "#3b82f6",
    "Qwen3:32B": "#8b5cf6",
    "Qwen3:8B": "#a78bfa",
    "Ministral-3:14B": "#f97316",
    "GPT-4o": "#f59e0b",
    "GPT-5.4": "#10b981",
}

# Policy data (from tab_policy.tex)
POLICY_DATA = {
    "Sage":  {"green": 8, "yellow": 2, "red": 0},
    "Rebel": {"green": 2, "yellow": 2, "red": 6},
    "Lover": {"green": 9, "yellow": 0, "red": 1},
}


# =============================================================================
# Figure 1: Pipeline diagram
# =============================================================================

def generate_pipeline(output_dir: Path):
    """Cognitive Sandwich architecture diagram."""
    fig, ax = plt.subplots(figsize=(7, 3.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4)
    ax.axis("off")

    layers = [
        (0.3, "Profiling\nLayer", "User profile\n(archetype, music, thread)", "#dbeafe", "#3b82f6"),
        (2.8, "Reasoning\nLayer", "Director LLM\n(triptych + OST)", "#fef3c7", "#f59e0b"),
        (5.3, "Control\nLayer", "PolicyGate\n(8 rules)", "#fce7f3", "#ec4899"),
        (7.8, "Delivery\nLayer", "Video + Music\ngeneration", "#d1fae5", "#10b981"),
    ]

    box_w, box_h = 2.0, 2.8
    for x, title, desc, bg, border in layers:
        rect = FancyBboxPatch(
            (x, 0.6), box_w, box_h,
            boxstyle="round,pad=0.1",
            facecolor=bg, edgecolor=border, linewidth=1.5,
        )
        ax.add_patch(rect)
        ax.text(x + box_w / 2, 2.6, title, ha="center", va="center",
                fontweight="bold", fontsize=9, color=border)
        ax.text(x + box_w / 2, 1.4, desc, ha="center", va="center",
                fontsize=7, color="#374151", style="italic")

    # Arrows
    for i in range(3):
        x_start = layers[i][0] + box_w + 0.05
        x_end = layers[i + 1][0] - 0.05
        ax.annotate(
            "", xy=(x_end, 2.0), xytext=(x_start, 2.0),
            arrowprops=dict(arrowstyle="-|>", color="#6b7280", lw=1.5),
        )

    # Title
    ax.text(5, 3.7, "Cognitive Sandwich Architecture", ha="center",
            fontsize=12, fontweight="bold", color="#1e3a5f")

    fig.savefig(output_dir / "pipeline.pdf")
    plt.close(fig)
    print(f"  pipeline.pdf")


# =============================================================================
# Figure 2: Archetype radar plot
# =============================================================================

def generate_radar(output_dir: Path):
    """Radar chart comparing Sage, Rebel, Lover on key metrics."""
    # Select differentiating metrics (skip perfect-score ones)
    selected = [1, 3, 4, 6, 7, 8, 9, 10, 11, 12]
    labels = [METRICS_SHORT[i] for i in selected]
    n = len(labels)

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]  # close polygon

    fig, ax = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))

    for archetype, color in [("Sage", COLORS["sage"]), ("Rebel", COLORS["rebel"]), ("Lover", COLORS["lover"])]:
        values = [ARCHETYPE_DATA[archetype][i] for i in selected]
        values += values[:1]
        ax.plot(angles, values, "o-", color=color, linewidth=1.5, markersize=4, label=archetype)
        ax.fill(angles, values, alpha=0.1, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylim(0, 1.05)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["0.2", "0.4", "0.6", "0.8", "1.0"], fontsize=6, color="#999")
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    ax.set_title("Per-Archetype Performance", pad=20, fontweight="bold")

    fig.savefig(output_dir / "radar.pdf")
    plt.close(fig)
    print(f"  radar.pdf")


# =============================================================================
# Figure 3: Ablation bar chart
# =============================================================================

def generate_ablation(output_dir: Path):
    """Grouped bar chart for prompt pack ablation."""
    # Select metrics with meaningful variation
    selected_idx = [1, 3, 4, 6, 7, 8, 10, 11, 12]
    labels = [METRICS_SHORT[i] for i in selected_idx] + ["Aggregate"]

    default_vals = [ABLATION_DATA["Default"][i] for i in selected_idx] + [ABLATION_AGG["Default"]]
    concise_vals = [ABLATION_DATA["Concise"][i] for i in selected_idx] + [ABLATION_AGG["Concise"]]
    detailed_vals = [ABLATION_DATA["Detailed"][i] for i in selected_idx] + [ABLATION_AGG["Detailed"]]

    x = np.arange(len(labels))
    width = 0.25

    fig, ax = plt.subplots(figsize=(8, 3.5))

    ax.bar(x - width, default_vals, width, label="Default", color=COLORS["default"], edgecolor="white", linewidth=0.5)
    ax.bar(x, concise_vals, width, label="Concise", color=COLORS["concise"], edgecolor="white", linewidth=0.5)
    ax.bar(x + width, detailed_vals, width, label="Detailed", color=COLORS["detailed"], edgecolor="white", linewidth=0.5)

    ax.set_ylabel("Score")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylim(0, 1.1)
    ax.legend(loc="upper right")
    ax.set_title("Prompt Pack Ablation", fontweight="bold")
    ax.axhline(y=0.775, color=COLORS["default"], linestyle="--", linewidth=0.7, alpha=0.5)

    # Highlight aggregate
    ax.axvspan(len(labels) - 1.5, len(labels) - 0.5, alpha=0.08, color="#667eea")

    fig.savefig(output_dir / "ablation.pdf")
    plt.close(fig)
    print(f"  ablation.pdf")


# =============================================================================
# Figure 4: Cross-model comparison
# =============================================================================

def generate_crossmodel(output_dir: Path):
    """Grouped bar chart for 4 models."""
    selected_idx = [1, 3, 4, 6, 7, 8, 9, 10, 11, 12]
    labels = [METRICS_SHORT[i] for i in selected_idx]

    models = list(CROSSMODEL_DATA.keys())
    n_models = len(models)
    width = 0.8 / n_models

    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(10, 3.5))

    for j, model in enumerate(models):
        vals = [CROSSMODEL_DATA[model][i] for i in selected_idx]
        offset = (j - (n_models - 1) / 2) * width
        ax.bar(x + offset, vals, width, label=model,
               color=CROSSMODEL_COLORS[model], edgecolor="white", linewidth=0.5)

    ax.set_ylabel("Score")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylim(0, 1.12)
    ax.legend(loc="upper right", fontsize=7, ncol=2)
    ax.set_title("Cross-Model Comparison", fontweight="bold")

    fig.savefig(output_dir / "crossmodel.pdf")
    plt.close(fig)
    print(f"  crossmodel.pdf")


# =============================================================================
# Figure 5: Policy compliance stacked bar
# =============================================================================

def generate_policy(output_dir: Path):
    """Stacked bar chart for policy compliance."""
    archetypes = ["Sage", "Rebel", "Lover"]
    greens = [POLICY_DATA[a]["green"] for a in archetypes]
    yellows = [POLICY_DATA[a]["yellow"] for a in archetypes]
    reds = [POLICY_DATA[a]["red"] for a in archetypes]

    x = np.arange(len(archetypes))
    width = 0.5

    fig, ax = plt.subplots(figsize=(4, 3.5))

    ax.bar(x, greens, width, label="GREEN (pass)", color=COLORS["green"], edgecolor="white")
    ax.bar(x, yellows, width, bottom=greens, label="YELLOW (warn)", color=COLORS["yellow"], edgecolor="white")
    ax.bar(x, reds, width, bottom=[g + y for g, y in zip(greens, yellows)], label="RED (fail)", color=COLORS["red"], edgecolor="white")

    # Value labels
    for i, a in enumerate(archetypes):
        total = 10
        for val, bottom, color_key in [
            (greens[i], 0, "green"),
            (yellows[i], greens[i], "yellow"),
            (reds[i], greens[i] + yellows[i], "red"),
        ]:
            if val > 0:
                ax.text(x[i], bottom + val / 2, str(val), ha="center", va="center",
                        fontweight="bold", fontsize=10, color="white")

    ax.set_ylabel("Profiles (n=10 per archetype)")
    ax.set_xticks(x)
    ax.set_xticklabels(archetypes)
    ax.set_ylim(0, 11)
    ax.legend(loc="upper right", fontsize=7)
    ax.set_title("PolicyGate Compliance", fontweight="bold")

    # Color the x-axis labels
    for i, label in enumerate(ax.get_xticklabels()):
        label.set_color(COLORS[archetypes[i].lower()])
        label.set_fontweight("bold")

    fig.savefig(output_dir / "policy.pdf")
    plt.close(fig)
    print(f"  policy.pdf")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Generate paper figures")
    parser.add_argument("--output-dir", type=str, default="paper/figures",
                        help="Output directory for figures")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating figures in {output_dir}/")
    generate_pipeline(output_dir)
    generate_radar(output_dir)
    generate_ablation(output_dir)
    generate_crossmodel(output_dir)
    generate_policy(output_dir)
    print("Done! 5 figures generated.")


if __name__ == "__main__":
    main()
