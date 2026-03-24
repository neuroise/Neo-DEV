"""
Annotate page - Fast human evaluation for paper data collection.

Single-screen layout: read prompts on top, click scores below, submit & auto-advance.
Dark-mode compatible. Detailed scoring guidelines with examples.
"""

import csv
import io
import json
import streamlit as st
from pathlib import Path
from typing import List

from core.metrics.manual.human_eval import (
    HumanEvalStore,
    HumanEvaluation,
    EVAL_DIMENSIONS,
)

# Detailed dimension config: label, short description, full guide with scale anchors
DIM_CONFIG = {
    "visual_clarity": {
        "label": "Visual Clarity",
        "short": "Can a video AI generate this?",
        "guide": (
            "Does the prompt describe a **concrete, filmable scene**? "
            "Look for: specific subjects (waves, horizon, reef), camera info "
            "(aerial, close-up, tracking), lighting (golden hour, overcast), movement (slow pan, descending).\n\n"
            "- **5** = Reads like a shot list: subject, framing, camera, lighting all specified\n"
            "- **4** = Mostly concrete, one element vague (e.g. no camera direction)\n"
            "- **3** = Mix of concrete and abstract; an AI could try but might guess wrong\n"
            "- **2** = Mostly abstract/poetic, hard to visualize a specific shot\n"
            "- **1** = Pure metaphor or narration, impossible to render as video"
        ),
    },
    "archetype_alignment": {
        "label": "Archetype Fit",
        "short": "Does it match the archetype?",
        "guide": (
            "Does the visual language match the archetype shown in the header?\n\n"
            "**Sage** = contemplative, minimal, slow, still water, horizons, geometric patterns\n"
            "**Rebel** = dynamic, bold, high energy, crashing waves, dramatic weather, speed\n"
            "**Lover** = warm, intimate, sensual, sunset reflections, gentle waves, textures\n\n"
            "- **5** = Unmistakably this archetype; someone could guess it from the prompts alone\n"
            "- **4** = Clearly this archetype, minor overlap with another\n"
            "- **3** = Generic marine scene, could be any archetype\n"
            "- **2** = Leans toward a different archetype\n"
            "- **1** = Completely wrong archetype (e.g. 'crashing waves' for Sage)"
        ),
    },
    "narrative_coherence": {
        "label": "Story Coherence",
        "short": "Do the 3 scenes tell a story?",
        "guide": (
            "Read START -> EVOLVE -> END as a sequence. Is there a **narrative arc**? "
            "Does it feel like a beginning, development, and conclusion?\n\n"
            "- **5** = Clear progression: tone/intensity/subject evolves across scenes, satisfying closure\n"
            "- **4** = Progression exists but one transition is weak\n"
            "- **3** = Scenes are thematically related but could be reordered without losing meaning\n"
            "- **2** = Scenes feel disconnected, only loosely related\n"
            "- **1** = Random scenes with no narrative connection"
        ),
    },
    "emotional_resonance": {
        "label": "Emotional Impact",
        "short": "Does it evoke the intended feeling?",
        "guide": (
            "Imagine watching these 3 videos in sequence on a yacht. "
            "Does the overall experience **evoke an emotion** aligned with the archetype?\n\n"
            "Sage -> serenity, contemplation, awe | "
            "Rebel -> thrill, freedom, power | "
            "Lover -> warmth, intimacy, romance\n\n"
            "- **5** = Strongly evocative, you can almost feel it\n"
            "- **4** = Clearly sets a mood, minor distractions\n"
            "- **3** = Some emotional tone but generic\n"
            "- **2** = Flat, technical descriptions without emotional pull\n"
            "- **1** = Wrong emotion or no emotional content at all"
        ),
    },
    "marine_adherence": {
        "label": "Marine Compliance",
        "short": "Marine/coastal only? No red flags?",
        "guide": (
            "Everything must be **marine or coastal**: sea, ocean, shore, sky, boats. "
            "**Red flags** (instant fail to 1):\n\n"
            "- Urban elements: city, buildings, cars, traffic\n"
            "- People: recognizable faces, crowds\n"
            "- Non-marine nature: forests, mountains, deserts, snow\n"
            "- Violence, danger, brand logos, text overlays\n\n"
            "- **5** = Pure marine/coastal, rich ocean vocabulary, zero issues\n"
            "- **4** = All marine, but thin on marine-specific detail\n"
            "- **3** = Marine but with a borderline element (e.g. 'distant cliffs')\n"
            "- **2** = Contains a non-marine element that doesn't belong\n"
            "- **1** = Red flag present (urban, faces, violence, etc.)"
        ),
    },
}

ARCHETYPE_COLORS = {"sage": "#6B7280", "rebel": "#EF4444", "lover": "#EC4899"}
ARCHETYPE_MAP = {"S": "sage", "R": "rebel", "L": "lover"}

PAPER_EXPERIMENTS = [
    "baseline_30_llama70b_v3",
    "baseline_30_qwen32b",
    "baseline_30_qwen3_8b",
    "baseline_30_ministral3_14b",
    "baseline_30_gpt4o",
    "baseline_30_gpt54",
]


def _get_experiments_dir() -> Path:
    return Path(__file__).parent.parent.parent / "data" / "experiments"


def _list_experiments() -> List[str]:
    exp_dir = _get_experiments_dir()
    if not exp_dir.exists():
        return []
    return sorted([
        d.name for d in exp_dir.iterdir()
        if d.is_dir() and (d / "results.json").exists()
    ])


def _load_experiment_runs(experiment: str) -> List[dict]:
    exp_path = _get_experiments_dir() / experiment / "results.json"
    if not exp_path.exists():
        return []
    with open(exp_path) as f:
        data = json.load(f)
    return [r for r in data.get("results", []) if r.get("success")]


def _get_annotated_profiles(store: HumanEvalStore, experiment: str, rater_id: str) -> set:
    evals = store.load_for_experiment(experiment)
    return {e.profile_id for e in evals if e.rater_id == rater_id}


def render_annotate():
    """Main annotate page."""

    # Dark-mode compatible CSS using Streamlit CSS variables
    st.markdown("""
    <style>
    .scene-box {
        font-size: 0.95rem;
        line-height: 1.6;
        padding: 14px;
        background: var(--secondary-background-color);
        color: var(--text-color);
        border-radius: 8px;
        margin-bottom: 8px;
        min-height: 80px;
    }
    .scene-box.start  { border-left: 4px solid #3b82f6; }
    .scene-box.evolve { border-left: 4px solid #f59e0b; }
    .scene-box.end    { border-left: 4px solid #10b981; }
    .ost-box {
        font-size: 0.9rem;
        line-height: 1.5;
        padding: 10px 14px;
        background: var(--secondary-background-color);
        color: var(--text-color);
        border-radius: 8px;
        border-left: 4px solid #f59e0b;
        margin-top: 4px;
    }
    .ost-meta { color: #a78bfa; font-size: 0.85rem; }
    .profile-hdr {
        font-size: 1.4rem;
        font-weight: 700;
        margin: 0;
        padding: 4px 0;
        color: var(--text-color);
    }
    .dim-row-label {
        font-size: 0.9rem;
        font-weight: 600;
        color: var(--text-color);
    }
    .dim-row-desc {
        font-size: 0.75rem;
        color: gray;
    }
    </style>
    """, unsafe_allow_html=True)

    experiments = _list_experiments()
    if not experiments:
        st.warning("No experiments found.")
        return

    store = HumanEvalStore()

    # === SETUP BAR ===
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        raters = ["tiberio", "nicola", "jacopo"]
        rater_id = st.selectbox("Rater", raters + ["other..."], key="ann_rater_sel")
        if rater_id == "other...":
            rater_id = st.text_input("Custom ID", key="ann_rater_custom")
    with c2:
        paper_avail = [e for e in PAPER_EXPERIMENTS if e in experiments]
        other_avail = [e for e in experiments if e not in PAPER_EXPERIMENTS]
        all_exp = paper_avail + other_avail
        selected_exp = st.selectbox("Experiment", all_exp, index=0, key="ann_exp")
    with c3:
        st.markdown("<br>", unsafe_allow_html=True)
        model_name = selected_exp.replace("baseline_30_", "").replace("_", " ")
        st.caption(f"Model: **{model_name}**")

    if not rater_id:
        st.info("Select your name to start.")
        return

    # === LOAD DATA ===
    runs = _load_experiment_runs(selected_exp)
    if not runs:
        st.warning("No successful runs in this experiment.")
        return

    profile_ids = [r["profile_id"] for r in runs]
    annotated = _get_annotated_profiles(store, selected_exp, rater_id)
    remaining = [pid for pid in profile_ids if pid not in annotated]

    n_done = len(annotated & set(profile_ids))
    n_total = len(profile_ids)
    st.progress(n_done / n_total if n_total else 0, text=f"{n_done}/{n_total} done")

    if not remaining:
        st.success("All done for this experiment!")
        _render_export(store, selected_exp)
        return

    # === NAVIGATION ===
    state_key = f"ann_profile_{selected_exp}"
    if state_key not in st.session_state or st.session_state[state_key] not in remaining:
        st.session_state[state_key] = remaining[0]

    current_profile = st.session_state[state_key]
    current_idx = remaining.index(current_profile)

    nav1, nav2, nav3, nav4, nav5 = st.columns([1, 1, 1, 3, 2])
    with nav1:
        if st.button("< Prev", disabled=current_idx == 0, use_container_width=True):
            st.session_state[state_key] = remaining[current_idx - 1]
            st.rerun()
    with nav2:
        if st.button("Next >", disabled=current_idx >= len(remaining) - 1, use_container_width=True):
            st.session_state[state_key] = remaining[current_idx + 1]
            st.rerun()
    with nav3:
        if st.button("Skip", use_container_width=True):
            next_idx = min(current_idx + 1, len(remaining) - 1)
            st.session_state[state_key] = remaining[next_idx]
            st.rerun()
    with nav4:
        jump = st.selectbox("Go to", remaining, index=current_idx, key="ann_jump", label_visibility="collapsed")
        if jump != current_profile:
            st.session_state[state_key] = jump
            st.rerun()
    with nav5:
        st.markdown(f"**{current_idx + 1}** / {len(remaining)} remaining")

    run = next((r for r in runs if r["profile_id"] == current_profile), None)
    if not run:
        st.error(f"Profile {current_profile} not found.")
        return

    # === CONTENT ===
    prefix = current_profile.split("-")[0]
    archetype = ARCHETYPE_MAP.get(prefix, "unknown")
    color = ARCHETYPE_COLORS.get(archetype, "#666")

    st.markdown(
        f'<p class="profile-hdr">{current_profile} '
        f'<span style="color:{color}">[{archetype.upper()}]</span></p>',
        unsafe_allow_html=True,
    )

    output = run.get("output", {})
    triptych = output.get("video_triptych", [])

    # Check if rendered videos exist for this profile
    video_dir = Path(__file__).parent.parent.parent / "data" / "outputs" / "videos" / selected_exp / current_profile
    has_videos = video_dir.exists() and any(video_dir.glob("*.mp4"))

    if triptych:
        cols = st.columns(3)
        role_cls = ["start", "evolve", "end"]
        for i, scene in enumerate(triptych):
            with cols[i]:
                role = scene.get("scene_role", role_cls[i]).upper()
                cls = role_cls[i] if i < 3 else "start"
                prompt_text = scene.get("prompt", "")
                mood = ", ".join(scene.get("mood_tags", []))
                st.markdown(f"**{role}**" + (f"  ·  _{mood}_" if mood else ""))
                # Show video if available
                video_path = video_dir / f"{role_cls[i]}.mp4" if has_videos else None
                if video_path and video_path.exists():
                    st.video(str(video_path))
                st.markdown(f'<div class="scene-box {cls}">{prompt_text}</div>', unsafe_allow_html=True)

    ost = output.get("ost_prompt", {})
    if ost:
        ost_text = ost.get("prompt", "")
        meta = f"{ost.get('genre', '?')} · {ost.get('bpm', '?')} BPM · {ost.get('mood', '?')}"
        st.markdown(
            f'<div class="ost-box"><b>OST</b>: {ost_text} '
            f'<span class="ost-meta">({meta})</span></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")

    # === SCORING ===
    scores = {}
    score_pfx = f"ann_s_{selected_exp}_{current_profile}"

    for dim in EVAL_DIMENSIONS:
        cfg = DIM_CONFIG[dim]
        score_key = f"{score_pfx}_{dim}"
        if score_key not in st.session_state:
            st.session_state[score_key] = 3

        col_label, col1, col2, col3, col4, col5, col_info = st.columns([3, 0.6, 0.6, 0.6, 0.6, 0.6, 0.5])

        with col_label:
            st.markdown(
                f'<div class="dim-row-label">{cfg["label"]}</div>'
                f'<div class="dim-row-desc">{cfg["short"]}</div>',
                unsafe_allow_html=True,
            )

        current_score = st.session_state[score_key]
        for val, col in [(1, col1), (2, col2), (3, col3), (4, col4), (5, col5)]:
            with col:
                btn_type = "primary" if current_score == val else "secondary"
                if st.button(str(val), key=f"{score_key}_b{val}", type=btn_type, use_container_width=True):
                    st.session_state[score_key] = val
                    st.rerun()

        with col_info:
            with st.popover("?"):
                st.markdown(cfg["guide"])

        scores[dim] = st.session_state[score_key]

    # Notes + Submit
    col_notes, col_submit = st.columns([3, 1])
    with col_notes:
        notes = st.text_input(
            "notes", key=f"ann_n_{selected_exp}_{current_profile}",
            label_visibility="collapsed", placeholder="Optional notes...",
        )
    with col_submit:
        if st.button("Submit & Next", type="primary", use_container_width=True):
            evaluation = HumanEvaluation(
                experiment=selected_exp,
                profile_id=current_profile,
                rater_id=rater_id,
                scores=scores,
                notes=notes,
            )
            store.save(evaluation)
            st.toast(f"Saved {current_profile}")
            for dim in EVAL_DIMENSIONS:
                sk = f"{score_pfx}_{dim}"
                if sk in st.session_state:
                    del st.session_state[sk]
            next_remaining = [p for p in remaining if p != current_profile]
            if next_remaining:
                st.session_state[state_key] = next_remaining[min(current_idx, len(next_remaining) - 1)]
            st.rerun()

    # Export collapsed
    with st.expander("Export & Agreement"):
        _render_export(store, selected_exp)


def _render_export(store: HumanEvalStore, experiment: str):
    """CSV export and inter-rater agreement."""
    evals = store.load_for_experiment(experiment)
    if not evals:
        st.info("No evaluations yet.")
        return

    raters = sorted(set(e.rater_id for e in evals))
    st.caption(f"Raters: {', '.join(raters)} ({len(evals)} evaluations)")

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["experiment", "profile_id", "rater_id", *EVAL_DIMENSIONS, "mean_score", "notes", "timestamp"])
    for ev in evals:
        writer.writerow([
            ev.experiment, ev.profile_id, ev.rater_id,
            *[ev.scores.get(d, "") for d in EVAL_DIMENSIONS],
            f"{ev.mean_score:.2f}", ev.notes, ev.timestamp,
        ])
    st.download_button("Download CSV", data=buf.getvalue(), file_name=f"human_eval_{experiment}.csv", mime="text/csv")

    if len(raters) >= 2:
        st.markdown("**Inter-Rater Agreement**")
        if len(raters) == 2:
            overall_k = store.cohens_kappa(experiment, raters[0], raters[1])
            cols = st.columns(len(EVAL_DIMENSIONS) + 1)
            with cols[0]:
                st.metric("Overall", f"{overall_k:.3f}")
            for i, dim in enumerate(EVAL_DIMENSIONS):
                k = store.cohens_kappa(experiment, raters[0], raters[1], dimension=dim)
                with cols[i + 1]:
                    st.metric(DIM_CONFIG[dim]["label"][:10], f"{k:.3f}")
        else:
            fk = store.fleiss_kappa(experiment)
            cols = st.columns(len(EVAL_DIMENSIONS) + 1)
            with cols[0]:
                st.metric(f"Fleiss K ({len(raters)}r)", f"{fk:.3f}")
            for i, dim in enumerate(EVAL_DIMENSIONS):
                fk_d = store.fleiss_kappa(experiment, dimension=dim)
                with cols[i + 1]:
                    st.metric(DIM_CONFIG[dim]["label"][:10], f"{fk_d:.3f}")
