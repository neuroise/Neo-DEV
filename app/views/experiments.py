"""
Experiments page - Configure and run batch experiments.

Allows selecting models, profiles, and running batch experiments
with progress tracking.
"""

import json
import streamlit as st
from pathlib import Path
from datetime import datetime


def _get_profiles_dir():
    return Path(__file__).parent.parent.parent / "data" / "profiles" / "official"


def _get_experiments_dir():
    return Path(__file__).parent.parent.parent / "data" / "experiments"


def _list_profiles():
    profile_dir = _get_profiles_dir()
    if not profile_dir.exists():
        return []
    return sorted([p.stem for p in profile_dir.glob("*.json")])


def _get_available_models():
    """Fetch available models from Ollama."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return [m["name"] for m in models if m.get("size", 0) > 1e9]
    except Exception:
        pass
    return ["llama3.3:70b", "qwen3:32b", "gemma3:27b"]


def _list_past_experiments():
    exp_dir = _get_experiments_dir()
    if not exp_dir.exists():
        return []
    experiments = []
    for d in sorted(exp_dir.iterdir()):
        if d.is_dir() and (d / "summary.json").exists():
            with open(d / "summary.json") as f:
                summary = json.load(f)
            experiments.append({
                "name": d.name,
                "total": summary.get("total_runs", 0),
                "success": summary.get("successful_runs", 0),
                "models": list(summary.get("models", {}).keys()),
            })
    return experiments


def render_experiments():
    """Main experiments page."""
    st.subheader("Experiments")

    tab_new, tab_history = st.tabs(["New Experiment", "History"])

    with tab_new:
        _render_new_experiment()

    with tab_history:
        _render_history()


def _render_new_experiment():
    """Configure and launch a new experiment."""
    st.markdown("#### Configure Experiment")

    col1, col2 = st.columns(2)

    with col1:
        # Experiment name
        default_name = f"exp_{datetime.now().strftime('%Y%m%d_%H%M')}"
        exp_name = st.text_input("Experiment Name", value=default_name)

        # Model selection
        available_models = _get_available_models()
        selected_models = st.multiselect(
            "Models to test",
            available_models,
            default=[available_models[0]] if available_models else [],
        )

        # Judge model
        judge_model = st.selectbox(
            "LLM Judge Model",
            ["qwen3:32b", "gemma3:27b", "llama3.3:70b", "qwen3:14b"],
            index=0,
        )

    with col2:
        # Profile selection
        all_profiles = _list_profiles()
        archetype_filter = st.multiselect(
            "Archetype Filter",
            ["Sage (S-*)", "Rebel (R-*)", "Lover (L-*)"],
            default=["Sage (S-*)", "Rebel (R-*)", "Lover (L-*)"],
        )

        # Filter profiles
        prefixes = []
        if "Sage (S-*)" in archetype_filter:
            prefixes.append("S-")
        if "Rebel (R-*)" in archetype_filter:
            prefixes.append("R-")
        if "Lover (L-*)" in archetype_filter:
            prefixes.append("L-")

        filtered_profiles = [p for p in all_profiles if any(p.startswith(px) for px in prefixes)]
        st.caption(f"{len(filtered_profiles)} profiles selected")

        # Runs per profile
        runs_per_profile = st.number_input("Runs per profile", min_value=1, max_value=10, value=1)

        # Temperature
        temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    # Summary
    total_runs = len(selected_models) * len(filtered_profiles) * runs_per_profile
    st.info(
        f"**{total_runs} total runs** = "
        f"{len(selected_models)} model(s) x {len(filtered_profiles)} profiles x {runs_per_profile} run(s)"
    )

    # Run button
    if st.button("Run Experiment", type="primary", disabled=not selected_models or not filtered_profiles):
        _run_experiment(exp_name, selected_models, filtered_profiles, runs_per_profile, temperature, judge_model)


def _run_experiment(exp_name, models, profiles, runs_per_profile, temperature, judge_model):
    """Execute experiment with progress tracking."""
    import sys
    import os
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    os.environ.setdefault("HF_HOME", str(Path(__file__).parent.parent.parent / ".cache" / "huggingface"))

    try:
        from core.experiments.runner import ExperimentRunner, ExperimentConfig
    except ImportError as e:
        st.error(f"Cannot import experiment runner: {e}")
        return

    config = ExperimentConfig(
        name=exp_name,
        models=models,
        profiles=profiles,
        runs_per_profile=runs_per_profile,
        temperature=temperature,
        judge_model=judge_model,
    )

    runner = ExperimentRunner(config)
    total = len(models) * len(profiles) * runs_per_profile

    progress_bar = st.progress(0, text="Starting experiment...")
    status_text = st.empty()
    results_placeholder = st.empty()

    completed = 0
    try:
        results = runner.run(
            progress_callback=lambda msg: (
                status_text.text(msg),
                setattr(progress_bar, '_value', None),
            )
        )
    except AttributeError:
        # Fallback: run without callback
        results = runner.run()

    progress_bar.progress(1.0, text="Complete!")
    status_text.success(f"Experiment '{exp_name}' completed: {results.successful}/{results.total} successful")

    # Show quick summary
    if hasattr(results, 'summary') and results.summary:
        with results_placeholder.container():
            st.json(results.summary)


def _render_history():
    """Show past experiment history with expandable run details and JSONL download."""
    experiments = _list_past_experiments()

    if not experiments:
        st.info("No past experiments found.")
        return

    for exp in reversed(experiments):
        with st.expander(f"{exp['name']} ({exp['success']}/{exp['total']} runs)", expanded=False):
            st.markdown(f"**Models**: {', '.join(exp['models'])}")
            st.markdown(f"**Success rate**: {exp['success']}/{exp['total']}")

            exp_dir = _get_experiments_dir() / exp['name']

            # Load full summary
            try:
                with open(exp_dir / "summary.json") as f:
                    summary = json.load(f)

                for model_name, model_data in summary.get("models", {}).items():
                    agg = model_data.get("aggregate_score", {})
                    st.markdown(f"**{model_name}**: aggregate = {agg.get('mean', 0):.3f} "
                                f"(range: {agg.get('min', 0):.3f}-{agg.get('max', 0):.3f})")
            except Exception:
                pass

            # JSONL download button
            jsonl_path = exp_dir / "results.jsonl"
            if jsonl_path.exists():
                st.download_button(
                    "Download JSONL",
                    jsonl_path.read_text(),
                    file_name=f"{exp['name']}.jsonl",
                    mime="application/jsonl",
                    key=f"dl_jsonl_{exp['name']}",
                )

            # Individual run details
            results_path = exp_dir / "results.json"
            if results_path.exists():
                try:
                    with open(results_path) as f:
                        full_results = json.load(f)
                    runs = full_results.get("results", [])
                    if runs:
                        st.markdown("---")
                        st.markdown("**Individual Runs**")
                        for i, run in enumerate(runs):
                            pid = run.get("profile_id", "?")
                            model = run.get("model", "?")
                            ok = run.get("success", False)
                            label = f"{'OK' if ok else 'FAIL'} | {pid} | {model}"
                            with st.expander(label, expanded=False):
                                if ok:
                                    metrics = run.get("metrics", {})
                                    agg_score = metrics.get("aggregate_score", 0)
                                    st.markdown(f"Aggregate: **{agg_score:.3f}** | "
                                                f"Policy: {run.get('policy_flag', '?')} | "
                                                f"Latency: {run.get('latency_ms', 0)/1000:.1f}s")
                                else:
                                    st.error(run.get("error", "Unknown error"))
                except (json.JSONDecodeError, KeyError):
                    pass
