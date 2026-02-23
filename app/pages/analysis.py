"""
Analysis page - Visualize experiment results.

Shows radar charts, per-archetype breakdown, heatmaps, and tables
from completed experiment runs.
"""

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from pathlib import Path


# Short labels for metrics
METRIC_LABELS = {
    "M_AUTO_01_schema_compliance": "Schema",
    "M_AUTO_02_archetype_consistency": "Archetype",
    "M_AUTO_03_role_sequence_valid": "Sequence",
    "M_AUTO_04_story_thread_presence": "Thread",
    "M_AUTO_05_red_flag_score": "Red Flags",
    "M_AUTO_06_prompt_length_valid": "Length",
    "M_AUTO_07_archetype_lexical_fit": "Lexical Fit",
    "M_AUTO_08_cross_scene_coherence": "Coherence",
    "M_AUTO_09_prompt_specificity": "Specificity",
    "M_AUTO_10_marine_vocabulary_ratio": "Marine Vocab",
    "M_AUTO_11_score_narrative_coherence": "Narrative",
    "M_AUTO_12_llm_judge_quality": "LLM Judge",
    "M_AUTO_13_pacing_progression": "Pacing",
}

ARCHETYPE_COLORS = {
    "sage": "#6B7280",
    "rebel": "#EF4444",
    "lover": "#EC4899",
}


def get_experiments_dir():
    return Path(__file__).parent.parent.parent / "data" / "experiments"


def list_experiments():
    """List available experiment directories."""
    exp_dir = get_experiments_dir()
    if not exp_dir.exists():
        return []
    experiments = []
    for d in sorted(exp_dir.iterdir()):
        if d.is_dir() and (d / "summary.json").exists():
            experiments.append(d.name)
    return experiments


def load_experiment(name):
    """Load experiment results and summary."""
    exp_dir = get_experiments_dir() / name
    with open(exp_dir / "summary.json") as f:
        summary = json.load(f)
    try:
        with open(exp_dir / "results.json") as f:
            results = json.load(f)
    except json.JSONDecodeError:
        # Handle truncated/corrupt results files (e.g. from crash during write)
        results = {"results": []}
    return summary, results


def build_dataframe(results):
    """Build a pandas DataFrame from experiment results."""
    rows = []
    for run in results.get("results", []):
        row = {
            "profile_id": run["profile_id"],
            "model": run.get("model", "unknown"),
            "success": run.get("success", False),
            "latency_ms": run.get("latency_ms", 0),
            "policy_flag": run.get("policy_flag", "unknown"),
        }
        # Determine archetype from profile ID prefix
        prefix = run["profile_id"].split("-")[0]
        row["archetype"] = {"S": "sage", "R": "rebel", "L": "lover"}.get(prefix, "unknown")

        # Add metrics
        for k, v in run.get("metrics", {}).items():
            if isinstance(v, (int, float)):
                row[k] = v
        rows.append(row)
    return pd.DataFrame(rows)


def render_analysis():
    """Main analysis page."""
    st.subheader("Analysis")

    experiments = list_experiments()
    if not experiments:
        st.warning("No experiments found. Run an experiment first from the Experiments page.")
        return

    # Experiment selector
    col1, col2 = st.columns([3, 1])
    with col1:
        selected = st.selectbox("Select Experiment", experiments, index=len(experiments) - 1)
    with col2:
        compare_mode = st.checkbox("Compare experiments", value=False)

    if compare_mode:
        compare_with = st.multiselect(
            "Compare with",
            [e for e in experiments if e != selected],
            default=[]
        )
    else:
        compare_with = []

    summary, results = load_experiment(selected)
    df = build_dataframe(results)

    if df.empty:
        st.error("No results in this experiment.")
        return

    # --- Summary cards ---
    st.markdown("---")
    _render_summary_cards(summary, df)

    # --- Tabs for different views ---
    tab_radar, tab_archetype, tab_heatmap, tab_table = st.tabs([
        "Radar Chart", "Per-Archetype", "Heatmap", "Data Table"
    ])

    with tab_radar:
        if compare_with:
            _render_radar_comparison(selected, compare_with)
        else:
            _render_radar(summary)

    with tab_archetype:
        _render_archetype_breakdown(df)

    with tab_heatmap:
        _render_heatmap(df)

    with tab_table:
        _render_table(df)


def _render_summary_cards(summary, df):
    """Render summary metric cards."""
    cols = st.columns(5)

    total = summary.get("total_runs", 0)
    success = summary.get("successful_runs", 0)
    fail = summary.get("failed_runs", 0)

    # Get aggregate from first model
    models = summary.get("models", {})
    model_name = list(models.keys())[0] if models else "unknown"
    model_data = models.get(model_name, {})
    agg = model_data.get("aggregate_score", {})

    with cols[0]:
        st.metric("Runs", f"{success}/{total}", f"-{fail} failed" if fail else None)
    with cols[1]:
        st.metric("Model", model_name.split(":")[0], model_name.split(":")[-1] if ":" in model_name else None)
    with cols[2]:
        mean_agg = agg.get("mean", 0)
        st.metric("Aggregate Score", f"{mean_agg:.3f}")
    with cols[3]:
        std_agg = agg.get("std", agg.get("max", 0) - agg.get("min", 0))
        st.metric("Score Range", f"{agg.get('min', 0):.3f} - {agg.get('max', 0):.3f}")
    with cols[4]:
        avg_latency = df["latency_ms"].mean() / 1000 if "latency_ms" in df else 0
        st.metric("Avg Latency", f"{avg_latency:.1f}s")


def _render_radar(summary):
    """Render radar chart for metric means."""
    models = summary.get("models", {})
    model_name = list(models.keys())[0] if models else None
    if not model_name:
        return

    model_data = models[model_name]
    metric_keys = [k for k in METRIC_LABELS if k in model_data]
    labels = [METRIC_LABELS[k] for k in metric_keys]
    values = [model_data[k].get("mean", 0) for k in metric_keys]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values + [values[0]],
        theta=labels + [labels[0]],
        fill='toself',
        name=model_name,
        line=dict(color='#667eea', width=2),
        fillcolor='rgba(102, 126, 234, 0.25)'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1], tickvals=[0.25, 0.5, 0.75, 1.0]),
        ),
        showlegend=True,
        title=f"Metric Overview - {model_name}",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_radar_comparison(selected, compare_with):
    """Render overlapping radar charts for experiment comparison."""
    colors = ['#667eea', '#EF4444', '#10B981', '#F59E0B']

    fig = go.Figure()
    all_names = [selected] + compare_with

    for idx, exp_name in enumerate(all_names):
        summary, _ = load_experiment(exp_name)
        models = summary.get("models", {})
        model_name = list(models.keys())[0] if models else None
        if not model_name:
            continue

        model_data = models[model_name]
        metric_keys = [k for k in METRIC_LABELS if k in model_data]
        labels = [METRIC_LABELS[k] for k in metric_keys]
        values = [model_data[k].get("mean", 0) for k in metric_keys]
        color = colors[idx % len(colors)]

        fig.add_trace(go.Scatterpolar(
            r=values + [values[0]],
            theta=labels + [labels[0]],
            fill='toself',
            name=f"{exp_name} ({model_name})",
            line=dict(color=color, width=2),
            fillcolor=color.replace(')', ', 0.1)').replace('rgb', 'rgba') if 'rgb' in color else f"rgba{tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (0.1,)}"
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1]),
        ),
        showlegend=True,
        title="Experiment Comparison",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_archetype_breakdown(df):
    """Render per-archetype analysis."""
    metric_cols = [c for c in df.columns if c.startswith("M_AUTO")]
    if not metric_cols:
        st.warning("No metrics data available.")
        return

    # Compute per-archetype means
    archetype_means = df.groupby("archetype")[metric_cols].mean()

    # Bar chart comparison
    fig = go.Figure()
    for archetype in ["sage", "rebel", "lover"]:
        if archetype not in archetype_means.index:
            continue
        values = archetype_means.loc[archetype]
        labels = [METRIC_LABELS.get(k, k.replace("M_AUTO_", "")) for k in values.index]
        fig.add_trace(go.Bar(
            name=archetype.capitalize(),
            x=labels,
            y=values.values,
            marker_color=ARCHETYPE_COLORS.get(archetype, "#666"),
        ))

    fig.update_layout(
        barmode='group',
        title="Metrics by Archetype",
        yaxis=dict(range=[0, 1], title="Score"),
        xaxis=dict(title="Metric", tickangle=-45),
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Per-archetype radar
    st.markdown("#### Per-Archetype Radar")
    fig2 = go.Figure()
    for archetype in ["sage", "rebel", "lover"]:
        if archetype not in archetype_means.index:
            continue
        values = archetype_means.loc[archetype]
        labels = [METRIC_LABELS.get(k, k) for k in values.index]
        fig2.add_trace(go.Scatterpolar(
            r=list(values.values) + [values.values[0]],
            theta=labels + [labels[0]],
            fill='toself',
            name=archetype.capitalize(),
            line=dict(color=ARCHETYPE_COLORS.get(archetype), width=2),
        ))

    fig2.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        showlegend=True,
        height=500,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Aggregate by archetype
    st.markdown("#### Aggregate Scores")
    if "aggregate_score" in df.columns:
        agg_by_arch = df.groupby("archetype")["aggregate_score"].agg(["mean", "std", "min", "max"])
        st.dataframe(agg_by_arch.style.format("{:.3f}"), use_container_width=True)


def _render_heatmap(df):
    """Render profile x metric heatmap."""
    metric_cols = [c for c in df.columns if c.startswith("M_AUTO")]
    if not metric_cols:
        st.warning("No metrics data available.")
        return

    # Build heatmap data
    heatmap_df = df.set_index("profile_id")[metric_cols].copy()
    heatmap_df.columns = [METRIC_LABELS.get(c, c) for c in heatmap_df.columns]

    fig = px.imshow(
        heatmap_df.values,
        x=list(heatmap_df.columns),
        y=list(heatmap_df.index),
        color_continuous_scale="RdYlGn",
        zmin=0, zmax=1,
        aspect="auto",
        title="Profile x Metric Heatmap",
    )
    fig.update_layout(height=max(400, len(heatmap_df) * 25))
    st.plotly_chart(fig, use_container_width=True)


def _render_table(df):
    """Render full data table."""
    st.markdown("#### Full Results Table")

    # Column selection
    metric_cols = [c for c in df.columns if c.startswith("M_AUTO") or c == "aggregate_score"]
    display_cols = ["profile_id", "archetype", "model", "policy_flag", "latency_ms"] + metric_cols

    display_df = df[[c for c in display_cols if c in df.columns]].copy()

    # Rename metric columns for readability
    rename_map = {k: METRIC_LABELS.get(k, k) for k in metric_cols}
    rename_map["aggregate_score"] = "Aggregate"
    display_df = display_df.rename(columns=rename_map)

    # Style: color-code metric values (deduplicate to avoid pandas Series ambiguity)
    metric_display_cols = [rename_map.get(c, c) for c in metric_cols] + ["Aggregate"]
    existing_metric_cols = list(dict.fromkeys(c for c in metric_display_cols if c in display_df.columns))

    def color_score(val):
        try:
            v = float(val)
        except (TypeError, ValueError):
            return ""
        if v >= 0.8:
            return "background-color: #d4edda"
        elif v >= 0.6:
            return "background-color: #fff3cd"
        elif v >= 0.4:
            return "background-color: #ffeeba"
        else:
            return "background-color: #f8d7da"

    styled = display_df.style.map(color_score, subset=existing_metric_cols).format(
        {c: "{:.3f}" for c in existing_metric_cols if c in display_df.columns}
    )
    st.dataframe(styled, use_container_width=True, height=600)

    # Download button
    csv = display_df.to_csv(index=False)
    st.download_button(
        "Download CSV",
        csv,
        file_name="experiment_results.csv",
        mime="text/csv"
    )
