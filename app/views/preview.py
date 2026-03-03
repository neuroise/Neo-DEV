"""
Preview page - Visual mockup of generated triptych.

Shows a visual timeline with scene prompts, mood tags,
and music overlay for presentation purposes.
Supports generating and playing back actual videos via the Video Gen service.
"""

import json
import os
import time
import streamlit as st
from pathlib import Path


def _get_experiments_dir():
    return Path(__file__).parent.parent.parent / "data" / "experiments"


def _get_videos_dir():
    return Path(__file__).parent.parent.parent / "data" / "outputs" / "videos"


def _list_experiments():
    exp_dir = _get_experiments_dir()
    if not exp_dir.exists():
        return []
    return sorted([
        d.name for d in exp_dir.iterdir()
        if d.is_dir() and (d / "results.json").exists()
    ])


ARCHETYPE_STYLES = {
    "sage": {"bg": "#F3F4F6", "accent": "#6B7280", "emoji": "🧘"},
    "rebel": {"bg": "#FEF2F2", "accent": "#EF4444", "emoji": "🔥"},
    "lover": {"bg": "#FDF2F8", "accent": "#EC4899", "emoji": "💫"},
}

ROLE_ICONS = {"start": "▶", "evolve": "⟳", "end": "■"}


def _find_existing_videos(profile_id: str, experiment: str) -> list:
    """Check if videos already exist for this profile/experiment combo."""
    videos_dir = _get_videos_dir()
    # Look for videos stored under experiment/profile convention
    search_dir = videos_dir / experiment / profile_id
    if search_dir.exists():
        return sorted(search_dir.glob("*.mp4"))
    return []


def render_preview():
    """Main preview page."""
    st.subheader("Triptych Preview")

    experiments = _list_experiments()
    if not experiments:
        st.warning("No experiments found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        selected_exp = st.selectbox("Experiment", experiments, index=len(experiments) - 1, key="preview_exp")

    exp_path = _get_experiments_dir() / selected_exp / "results.json"
    with open(exp_path) as f:
        results = json.load(f)

    runs = results.get("results", [])
    profile_ids = [r["profile_id"] for r in runs]

    with col2:
        selected_profile = st.selectbox("Profile", profile_ids, key="preview_profile")

    run = next((r for r in runs if r["profile_id"] == selected_profile), None)
    if not run:
        return

    output = run.get("output", {})
    triptych = output.get("video_triptych", [])
    ost = output.get("ost_prompt", {})

    prefix = selected_profile.split("-")[0]
    archetype = {"S": "sage", "R": "rebel", "L": "lover"}.get(prefix, "sage")
    style = ARCHETYPE_STYLES.get(archetype, ARCHETYPE_STYLES["sage"])

    # --- Visual Timeline ---
    st.markdown("---")

    # Archetype header
    st.markdown(
        f'<div style="text-align:center;padding:15px;background:{style["bg"]};'
        f'border-radius:10px;margin-bottom:20px">'
        f'<span style="font-size:2em">{style["emoji"]}</span> '
        f'<span style="font-size:1.3em;font-weight:700;color:{style["accent"]}">'
        f'{archetype.upper()} Experience</span>'
        f'</div>',
        unsafe_allow_html=True
    )

    if not triptych:
        st.warning("No triptych data available.")
        return

    # --- Check for existing generated videos ---
    existing_videos = _find_existing_videos(selected_profile, selected_exp)

    # Scene cards with timeline
    cols = st.columns(3)
    for i, scene in enumerate(triptych):
        role = scene.get("scene_role", f"scene_{i}")
        prompt = scene.get("prompt", "")
        mood_tags = scene.get("mood_tags", [])
        duration = scene.get("duration_hint", "?")
        icon = ROLE_ICONS.get(role, "●")

        with cols[i]:
            # Show video if available
            if i < len(existing_videos):
                st.video(str(existing_videos[i]))

            # Scene card
            st.markdown(
                f'<div style="background:white;border:2px solid {style["accent"]};'
                f'border-radius:12px;padding:20px;min-height:300px;'
                f'box-shadow:0 2px 8px rgba(0,0,0,0.08)">'
                f'<div style="text-align:center;margin-bottom:12px">'
                f'<span style="font-size:1.5em">{icon}</span> '
                f'<span style="font-size:1.1em;font-weight:700;color:{style["accent"]}">'
                f'{role.upper()}</span>'
                f'<span style="font-size:0.8em;color:#999;margin-left:8px">{duration}s</span>'
                f'</div>'
                f'<div style="font-size:0.9em;color:#333;line-height:1.5;'
                f'font-style:italic;padding:10px;background:{style["bg"]};'
                f'border-radius:8px">'
                f'{prompt}'
                f'</div>'
                f'<div style="margin-top:12px;text-align:center">'
                + "".join(
                    f'<span style="display:inline-block;background:{style["accent"]}22;'
                    f'color:{style["accent"]};padding:2px 8px;border-radius:12px;'
                    f'font-size:0.75em;margin:2px">{tag}</span>'
                    for tag in mood_tags
                )
                + f'</div></div>',
                unsafe_allow_html=True
            )

    # Timeline connector
    st.markdown(
        f'<div style="text-align:center;margin:10px 0;font-size:0.9em;color:{style["accent"]}">'
        f'▶ ──────── ⟳ ──────── ■'
        f'</div>',
        unsafe_allow_html=True
    )

    # --- Video Generation ---
    st.markdown("---")
    st.markdown("#### Generate Videos")

    video_gen_url = st.session_state.get(
        "video_gen_url",
        os.environ.get("VIDEO_GEN_URL", "http://localhost:8000"),
    )
    video_model = st.session_state.get("video_model", "wan2.2-ti2v-5b")

    # Check service availability
    video_available = False
    try:
        from core.generation import VideoClient
        vc = VideoClient(video_gen_url)
        video_available = vc.is_available()
    except Exception:
        pass

    if not video_available:
        st.caption(f"Video Gen service not available at `{video_gen_url}`")

    gen_disabled = not video_available or not triptych
    if st.button(
        "Generate Videos",
        type="primary",
        disabled=gen_disabled,
        key="preview_gen_btn",
    ):
        scenes = []
        for scene in triptych:
            scenes.append({
                "role": scene.get("scene_role", "start"),
                "prompt": scene.get("prompt", ""),
            })

        with st.spinner(f"Submitting triptych to {video_model}..."):
            tri = vc.submit_triptych(scenes, model=video_model)
            triptych_id = tri["triptych_id"]

        st.info(f"Triptych job: `{triptych_id}`")
        progress_bar = st.progress(0.0, text="Generating videos...")

        while True:
            time.sleep(3)
            status = vc.get_triptych(triptych_id)
            progress = status.get("progress", 0)
            progress_bar.progress(progress, text=f"Generating... {progress*100:.0f}%")
            if status["state"] in ("completed", "failed"):
                break

        if status["state"] == "completed":
            st.success("All 3 videos generated!")

            # Download and save videos
            dest_dir = _get_videos_dir() / selected_exp / selected_profile
            dest_dir.mkdir(parents=True, exist_ok=True)

            vid_cols = st.columns(3)
            for i, scene_status in enumerate(status.get("scenes", [])):
                role = triptych[i].get("scene_role", f"scene_{i}") if i < len(triptych) else f"scene_{i}"
                with vid_cols[i]:
                    if scene_status.get("video_url"):
                        dest_path = dest_dir / f"{role}.mp4"
                        vc.download(scene_status["job_id"], dest_path=str(dest_path))
                        st.video(str(dest_path))
                        st.caption(f"{role.upper()} - {scene_status.get('elapsed_seconds', '?')}s")
        else:
            st.error("Triptych generation failed")
            for scene_status in status.get("scenes", []):
                if scene_status.get("error"):
                    st.write(f"- {scene_status['error']}")

    # --- OST Section ---
    if ost:
        st.markdown("---")
        st.markdown(
            f'<div style="background:linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);'
            f'padding:20px;border-radius:12px;color:white;margin-top:10px">'
            f'<div style="font-size:0.8em;opacity:0.7">♪ SOUNDTRACK</div>'
            f'<div style="font-size:1em;margin:8px 0;font-style:italic">'
            f'{ost.get("prompt", "N/A")}</div>'
            f'<div style="font-size:0.85em;opacity:0.8">'
            f'Genre: {ost.get("genre", "N/A")} · '
            f'BPM: {ost.get("bpm", "N/A")} · '
            f'Mood: {ost.get("mood", "N/A")}'
            f'</div></div>',
            unsafe_allow_html=True
        )

    # --- Metrics summary ---
    metrics = run.get("metrics", {})
    if metrics:
        st.markdown("---")
        st.markdown("#### Quality Scores")
        score_cols = st.columns(5)
        key_metrics = [
            ("Aggregate", metrics.get("aggregate_score", 0)),
            ("Coherence", metrics.get("M_AUTO_08_cross_scene_coherence", 0)),
            ("Narrative", metrics.get("M_AUTO_11_score_narrative_coherence", 0)),
            ("LLM Judge", metrics.get("M_AUTO_12_llm_judge_quality", 0)),
            ("Pacing", metrics.get("M_AUTO_13_pacing_progression", 0)),
        ]
        for idx, (label, val) in enumerate(key_metrics):
            with score_cols[idx]:
                st.metric(label, f"{val:.3f}")
