"""
Evaluate page - Detailed metric evaluation for individual outputs.

Shows per-output metrics, prompts, and LLM Judge details.
"""

import json
import streamlit as st
import plotly.graph_objects as go
from pathlib import Path


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
    "M_AUTO_12_llm_judge_quality": "LLM Judge Quality",
    "M_AUTO_13_pacing_progression": "Pacing Progression",
}

METRIC_DESCRIPTIONS = {
    "M_AUTO_01_schema_compliance": "Valid JSON with all required fields (triptych, scenes, OST)",
    "M_AUTO_02_archetype_consistency": "Archetype keywords present across all scenes",
    "M_AUTO_03_role_sequence_valid": "Correct start -> evolve -> end sequence",
    "M_AUTO_04_story_thread_presence": "Story thread hint words reflected in prompts",
    "M_AUTO_05_red_flag_score": "No policy violations (urban, faces, logos, etc.)",
    "M_AUTO_06_prompt_length_valid": "Prompts within length constraints (50-500 chars)",
    "M_AUTO_07_archetype_lexical_fit": "Weighted archetype keyword density",
    "M_AUTO_08_cross_scene_coherence": "Embedding similarity between scenes",
    "M_AUTO_09_prompt_specificity": "Concrete visual details vs abstract language",
    "M_AUTO_10_marine_vocabulary_ratio": "Marine/coastal term density",
    "M_AUTO_11_score_narrative_coherence": "Entity persistence + temporal flow + progression",
    "M_AUTO_12_llm_judge_quality": "LLM evaluation on 5 quality dimensions",
    "M_AUTO_13_pacing_progression": "Duration/intensity curve matches archetype",
}


def _get_experiments_dir():
    return Path(__file__).parent.parent.parent / "data" / "experiments"


def _list_experiments():
    exp_dir = _get_experiments_dir()
    if not exp_dir.exists():
        return []
    return sorted([
        d.name for d in exp_dir.iterdir()
        if d.is_dir() and (d / "results.json").exists()
    ])


def render_evaluate():
    """Main evaluate page."""
    st.subheader("Evaluate Output")

    experiments = _list_experiments()
    if not experiments:
        st.warning("No experiments found. Run an experiment first.")
        return

    # Select experiment and profile
    col1, col2 = st.columns(2)
    with col1:
        selected_exp = st.selectbox("Experiment", experiments, index=len(experiments) - 1)

    exp_path = _get_experiments_dir() / selected_exp / "results.json"
    with open(exp_path) as f:
        results = json.load(f)

    runs = results.get("results", [])
    profile_ids = [r["profile_id"] for r in runs]

    with col2:
        selected_profile = st.selectbox("Profile", profile_ids)

    run = next((r for r in runs if r["profile_id"] == selected_profile), None)
    if not run:
        st.error("Profile not found in results.")
        return

    # --- Metric Overview ---
    st.markdown("---")
    metrics = run.get("metrics", {})
    aggregate = metrics.get("aggregate_score", 0)

    # Aggregate score with gauge
    col_gauge, col_info = st.columns([1, 2])
    with col_gauge:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=aggregate,
            title={"text": "Aggregate Score"},
            gauge={
                "axis": {"range": [0, 1]},
                "bar": {"color": "#667eea"},
                "steps": [
                    {"range": [0, 0.4], "color": "#f8d7da"},
                    {"range": [0.4, 0.7], "color": "#fff3cd"},
                    {"range": [0.7, 1.0], "color": "#d4edda"},
                ],
            },
            number={"valueformat": ".3f"},
        ))
        fig.update_layout(height=250, margin=dict(t=50, b=0, l=30, r=30))
        st.plotly_chart(fig, use_container_width=True)

    with col_info:
        prefix = selected_profile.split("-")[0]
        archetype = {"S": "sage", "R": "rebel", "L": "lover"}.get(prefix, "unknown")
        st.markdown(f"**Profile**: {selected_profile}")
        st.markdown(f"**Archetype**: {archetype.capitalize()}")
        st.markdown(f"**Model**: {run.get('model', 'unknown')}")
        st.markdown(f"**Policy**: {run.get('policy_flag', 'N/A').upper()}")
        st.markdown(f"**Latency**: {run.get('latency_ms', 0) / 1000:.1f}s")

    # --- Individual metrics ---
    st.markdown("---")
    st.markdown("#### Metric Details")

    metric_keys = [k for k in METRIC_LABELS if k in metrics]
    cols_per_row = 3

    for i in range(0, len(metric_keys), cols_per_row):
        cols = st.columns(cols_per_row)
        for j, col in enumerate(cols):
            idx = i + j
            if idx >= len(metric_keys):
                break
            k = metric_keys[idx]
            v = metrics[k]
            label = METRIC_LABELS[k]
            desc = METRIC_DESCRIPTIONS.get(k, "")

            with col:
                # Color based on score
                if v >= 0.8:
                    color = "#28a745"
                elif v >= 0.6:
                    color = "#ffc107"
                elif v >= 0.4:
                    color = "#fd7e14"
                else:
                    color = "#dc3545"

                st.markdown(
                    f'<div style="padding:12px;border-radius:8px;border-left:4px solid {color};'
                    f'background:#f8f9fa;margin-bottom:8px">'
                    f'<div style="font-size:0.8em;color:#666">{label}</div>'
                    f'<div style="font-size:1.8em;font-weight:700;color:{color}">{v:.3f}</div>'
                    f'<div style="font-size:0.7em;color:#999">{desc}</div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

    # --- Output content ---
    st.markdown("---")
    st.markdown("#### Generated Content")

    output = run.get("output", {})
    triptych = output.get("video_triptych", [])

    if triptych:
        cols = st.columns(3)
        for i, scene in enumerate(triptych):
            with cols[i]:
                role = scene.get("scene_role", f"Scene {i+1}")
                st.markdown(f"**{role.upper()}**")
                st.text_area(
                    "Prompt",
                    scene.get("prompt", ""),
                    height=150,
                    key=f"eval_prompt_{i}",
                    disabled=True,
                )
                if scene.get("mood_tags"):
                    st.caption(f"Mood: {', '.join(scene['mood_tags'])}")
                if scene.get("duration_hint"):
                    st.caption(f"Duration: {scene['duration_hint']}s")

    ost = output.get("ost_prompt", {})
    if ost:
        st.markdown("**OST Prompt**")
        st.text_area("Music", ost.get("prompt", ""), height=80, disabled=True, key="eval_ost")
        st.caption(
            f"Genre: {ost.get('genre', 'N/A')} | "
            f"BPM: {ost.get('bpm', 'N/A')} | "
            f"Mood: {ost.get('mood', 'N/A')}"
        )
