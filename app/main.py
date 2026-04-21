"""
NEURØISE Playground - Main Streamlit Application

Entry point per l'interfaccia web del playground.

Usage:
    streamlit run app/main.py
    # oppure
    python -m streamlit run app/main.py
"""

import os
import streamlit as st
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_archetype_colors, get_archetype_names, prefix_to_archetype

# Page modules
from app.views.analysis import render_analysis
from app.views.evaluate import render_evaluate
from app.views.experiments import render_experiments
from app.views.preview import render_preview
from app.views.profiles import render_profiles
from app.views.annotate import render_annotate

# Page config
st.set_page_config(
    page_title="NEURØISE Playground",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1E3A5F;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #5A7A9A;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
    }
    """ + "\n".join(
        f"    .archetype-{name} {{ border-left: 4px solid {color}; }}"
        for name, color in get_archetype_colors().items()
    ) + """
</style>
""", unsafe_allow_html=True)


def main():
    # Header
    st.markdown('<p class="main-header">🌊 NEURØISE Playground</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="sub-header">Intelligent Storytelling Engine</p>',
        unsafe_allow_html=True
    )

    # Sidebar navigation
    st.sidebar.title("Navigation")

    page = st.sidebar.radio(
        "Select Page",
        [
            "🏠 Home",
            "🎬 Generate",
            "📊 Evaluate",
            "🧪 Experiments",
            "📈 Analysis",
            "🎥 Preview",
            "👤 Profiles",
            "✏️ Annotate",
            # "🌊 Simulation"  # Phase 2
        ]
    )

    st.sidebar.markdown("---")

    # Model selector
    st.sidebar.subheader("Model Settings")
    model_provider = st.sidebar.selectbox(
        "Provider",
        ["Ollama (Local)", "Anthropic (Claude)", "OpenAI (GPT)"]
    )

    if model_provider == "Ollama (Local)":
        # Fetch available models from Ollama
        ollama_url = st.sidebar.text_input(
            "Ollama URL",
            value="http://localhost:11434"
        )
        try:
            import requests
            r = requests.get(f"{ollama_url}/api/tags", timeout=2)
            available_models = sorted([m["name"] for m in r.json().get("models", [])
                                       if m.get("size", 0) > 1e9])
        except Exception:
            available_models = ["llama3.3:70b", "qwen3:32b", "gemma3:27b", "qwen3:14b"]
        model = st.sidebar.selectbox("Model", available_models)
    elif model_provider == "Anthropic (Claude)":
        model = st.sidebar.selectbox(
            "Model",
            ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-haiku-20240307"]
        )
    else:
        model = st.sidebar.selectbox(
            "Model",
            ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]
        )

    # Video model selector
    st.sidebar.markdown("---")
    st.sidebar.subheader("Video Generation")
    video_gen_url = st.sidebar.text_input(
        "Video Gen URL",
        value=os.environ.get("VIDEO_GEN_URL", "http://localhost:8000"),
        key="video_gen_url",
    )
    try:
        from core.generation import VideoClient
        vc = VideoClient(video_gen_url)
        video_models_info = vc.list_models()
        video_model_names = [m["id"] for m in video_models_info]
    except Exception:
        video_model_names = [
            "wan2.2-ti2v-5b", "wan2.2-t2v-a14b",
            "turbowanv2-t2v-1.3b", "turbowanv2-t2v-14b",
        ]
    video_model = st.sidebar.selectbox("Video Model", video_model_names, key="video_model")

    st.sidebar.markdown("---")
    st.sidebar.caption("NEURØISE Playground v0.1.0")
    st.sidebar.caption("© 2026 No Noise × DII UniPisa")

    # Main content based on page
    if page == "🏠 Home":
        render_home()
    elif page == "🎬 Generate":
        render_generate(model)
    elif page == "📊 Evaluate":
        render_evaluate()
    elif page == "🧪 Experiments":
        render_experiments()
    elif page == "📈 Analysis":
        render_analysis()
    elif page == "🎥 Preview":
        render_preview()
    elif page == "👤 Profiles":
        render_profiles()
    elif page == "✏️ Annotate":
        render_annotate()


def render_home():
    """Home page con overview del progetto."""

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Test Profiles", "50")
        st.caption(" · ".join(n.capitalize() for n in get_archetype_names()))

    with col2:
        st.metric("Archetypes", str(len(get_archetype_names())))
        st.caption("Jungian archetypes")

    st.markdown("---")

    # Quick start
    st.subheader("🚀 Quick Start")

    st.markdown("""
    1. **Generate**: Create video triptychs and OST prompts from user profiles
    2. **Evaluate**: Run automatic metrics on generated content
    3. **Experiments**: Batch testing with multiple models and profiles
    4. **Analysis**: Visualize results and compare performance
    5. **Preview**: See mockup visualizations of generated content
    """)

    # Status check
    st.subheader("🔧 System Status")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Components**")

        # Check profiles
        profile_dir = Path(__file__).parent.parent / "data" / "profiles" / "official"
        profile_count = len(list(profile_dir.glob("*.json"))) if profile_dir.exists() else 0
        st.write(f"✅ Profiles loaded: {profile_count}")

        # Check core modules
        try:
            from core.llm import Director
            st.write("✅ Director module")
        except ImportError as e:
            st.write(f"❌ Director module: {e}")

        try:
            from core.gating import PolicyGate
            st.write("✅ PolicyGate module")
        except ImportError as e:
            st.write(f"❌ PolicyGate module: {e}")

    with col2:
        st.markdown("**LLM Providers**")

        # Check Ollama
        try:
            import requests
            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                st.write(f"✅ Ollama: {len(models)} models")
            else:
                st.write("⚠️ Ollama: not responding")
        except Exception:
            st.write("❌ Ollama: not running")

        # Check Video Gen service
        try:
            from core.generation import VideoClient
            vc = VideoClient(os.environ.get("VIDEO_GEN_URL", "http://localhost:8000"))
            h = vc.health()
            gpu_info = f", GPU: {h.get('gpu_name', '?')}" if h.get("gpu_available") else ""
            loaded = h.get("loaded_model")
            model_info = f", loaded: {loaded}" if loaded else ""
            st.write(f"✅ Video Gen: ok{gpu_info}{model_info}")
        except Exception:
            st.write("⚠️ Video Gen: not running")

        # Check API keys
        if os.getenv("ANTHROPIC_API_KEY"):
            st.write("✅ Anthropic API key set")
        else:
            st.write("⚠️ Anthropic API key not set")

        if os.getenv("OPENAI_API_KEY"):
            st.write("✅ OpenAI API key set")
        else:
            st.write("⚠️ OpenAI API key not set")


def render_generate(model: str):
    """Page per generazione singola."""

    st.subheader("🎬 Generate Content")

    # Profile selection
    col1, col2 = st.columns([2, 1])

    with col1:
        profile_dir = Path(__file__).parent.parent / "data" / "profiles" / "official"
        profiles = sorted([p.stem for p in profile_dir.glob("*.json")]) if profile_dir.exists() else []

        selected_profile = st.selectbox(
            "Select Profile",
            profiles,
            index=0 if profiles else None
        )

    with col2:
        # Look up recommended temperature for the selected model
        RECOMMENDED_TEMPERATURES = {
            "qwen3": 0.6, "qwen2.5": 0.7, "qwen3.5": 0.6,
            "llama3": 0.6, "llama3.1": 0.6, "llama3.2": 0.6, "llama3.3": 0.6,
            "gemma3": 1.0, "gemma2": 1.0,
            "mistral": 0.7, "mixtral": 0.7, "mistral-large": 0.7,
            "phi3": 0.0, "phi4": 0.6,
            "deepseek-r1": 0.6, "deepseek-v3": 0.6,
        }
        model_key = model.lower().split(":")[0]
        rec_temp = RECOMMENDED_TEMPERATURES.get(model_key)
        if rec_temp is None:
            for known, temp in RECOMMENDED_TEMPERATURES.items():
                if model_key.startswith(known):
                    rec_temp = temp
                    break
        default_temp = rec_temp if rec_temp is not None else 0.7
        help_text = f"Recommended: {default_temp}" if rec_temp is not None else None
        temperature = st.slider(
            "Temperature", 0.0, 1.0, default_temp, 0.1, help=help_text,
        )

    # Load and display profile
    if selected_profile:
        import json
        profile_path = profile_dir / f"{selected_profile}.json"

        with open(profile_path) as f:
            profile = json.load(f)

        with st.expander("📋 Profile Details", expanded=True):
            col1, col2, col3 = st.columns(3)

            user_profile = profile.get("user_profile", {})
            music_seed = user_profile.get("music_seed", {})

            with col1:
                archetype = user_profile.get("primary_archetype", "unknown")
                from core.config import resolve_archetype
                arch_resolved = resolve_archetype(archetype)
                st.markdown(f"**Archetype**: {arch_resolved.upper()}")

            with col2:
                st.markdown(f"**Genre**: {music_seed.get('top_genre', 'N/A')}")
                st.markdown(f"**BPM**: {music_seed.get('bpm', 'N/A')}")

            with col3:
                st.markdown(f"**Mood**: {music_seed.get('mood_tag', 'N/A')}")
                st.markdown(f"**Thread**: {user_profile.get('story_thread_hint', 'N/A')}")

    # Generate button
    if st.button("🎬 Generate", type="primary", disabled=not selected_profile):
        with st.spinner(f"Generating with {model}..."):
            try:
                from core.llm import create_adapter, Director

                # Determine kwargs based on model
                kwargs = {"temperature": temperature}
                if "llama" in model.lower() or "mistral" in model.lower():
                    kwargs["base_url"] = "http://localhost:11434"

                adapter = create_adapter(model, **kwargs)
                director = Director(adapter)

                output = director.generate(profile)

                st.success("Generation complete!")

                # Display results
                st.subheader("Video Triptych")

                cols = st.columns(3)
                for i, scene in enumerate(output.video_triptych):
                    with cols[i]:
                        role = scene.get("scene_role", f"Scene {i+1}")
                        st.markdown(f"**{role.upper()}**")
                        st.text_area(
                            f"Prompt",
                            scene.get("prompt", ""),
                            height=150,
                            key=f"prompt_{i}"
                        )
                        if scene.get("mood_tags"):
                            st.caption(f"Mood: {', '.join(scene['mood_tags'])}")

                st.subheader("OST Prompt")
                ost = output.ost_prompt
                st.text_area("Music Prompt", ost.get("prompt", ""), height=100)
                st.caption(f"Genre: {ost.get('genre', 'N/A')} | BPM: {ost.get('bpm', 'N/A')} | Mood: {ost.get('mood', 'N/A')}")

                # Policy check
                from core.gating import PolicyGate
                gate = PolicyGate()
                result = gate.check(output.to_dict(), profile)

                st.subheader("Policy Check")
                flag_color = {"green": "success", "yellow": "warning", "red": "error"}
                getattr(st, flag_color.get(result.flag.value, "info"))(
                    f"Policy Flag: {result.flag.value.upper()} ({len(result.passed_rules)} rules passed)"
                )

                if result.warnings:
                    with st.expander(f"⚠️ Warnings ({len(result.warnings)})"):
                        for w in result.warnings:
                            st.write(f"- {w.rule_name}: {w.message}")

                # Store output in session for video generation
                st.session_state["last_output"] = output

            except Exception as e:
                st.error(f"Generation failed: {e}")
                st.exception(e)

    # --- Video Generation from last output ---
    if st.session_state.get("last_output") is not None:
        st.markdown("---")
        st.subheader("Generate Videos")
        st.caption("Generate actual videos from the triptych prompts above.")

        video_gen_url = st.session_state.get("video_gen_url", os.environ.get("VIDEO_GEN_URL", "http://localhost:8000"))
        video_model = st.session_state.get("video_model", "wan2.2-ti2v-5b")

        if st.button("Generate Videos from Triptych", type="secondary"):
            last_output = st.session_state["last_output"]
            try:
                from core.generation import VideoClient
                vc = VideoClient(video_gen_url)

                scenes = []
                for scene in last_output.video_triptych:
                    scenes.append({
                        "role": scene.get("scene_role", "start"),
                        "prompt": scene.get("prompt", ""),
                    })

                with st.spinner(f"Submitting triptych to {video_model}..."):
                    tri = vc.submit_triptych(scenes, model=video_model)
                    triptych_id = tri["triptych_id"]
                    st.info(f"Triptych job submitted: `{triptych_id}`")

                progress_bar = st.progress(0.0, text="Generating videos...")
                while True:
                    import time
                    time.sleep(3)
                    status = vc.get_triptych(triptych_id)
                    progress = status.get("progress", 0)
                    progress_bar.progress(progress, text=f"Generating... {progress*100:.0f}%")
                    if status["state"] in ("completed", "failed"):
                        break

                if status["state"] == "completed":
                    st.success("All 3 videos generated!")
                    vid_cols = st.columns(3)
                    for i, scene in enumerate(status.get("scenes", [])):
                        with vid_cols[i]:
                            if scene.get("video_url"):
                                local_path = vc.download(scene["job_id"])
                                st.video(str(local_path))
                else:
                    st.error("Triptych generation failed")
                    for scene in status.get("scenes", []):
                        if scene.get("error"):
                            st.write(f"- {scene.get('prompt', '')[:60]}: {scene['error']}")
            except Exception as e:
                st.error(f"Video generation error: {e}")


if __name__ == "__main__":
    main()
