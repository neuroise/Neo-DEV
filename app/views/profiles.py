"""
Profiles page - View, edit, and create user profiles.

Allows browsing the official profiles, editing fields, and creating new profiles.
"""

import json
import streamlit as st
from pathlib import Path


from core.config import get_archetype_names, get_bpm_ranges

ARCHETYPES = get_archetype_names()
BPM_DEFAULTS = {name: (lo + hi) // 2 for name, (lo, hi) in get_bpm_ranges().items()}


def _get_profiles_dir():
    return Path(__file__).parent.parent.parent / "data" / "profiles" / "official"


def _list_profiles():
    d = _get_profiles_dir()
    if not d.exists():
        return []
    return sorted([p.stem for p in d.glob("*.json")])


def _load_profile(profile_id: str) -> dict:
    path = _get_profiles_dir() / f"{profile_id}.json"
    with open(path) as f:
        return json.load(f)


def _save_profile(profile_id: str, data: dict):
    path = _get_profiles_dir() / f"{profile_id}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def render_profiles():
    """Main profiles page."""
    st.subheader("Profiles")

    tab_browse, tab_create = st.tabs(["Browse & Edit", "Create New"])

    with tab_browse:
        _render_browser()

    with tab_create:
        _render_create()


def _render_browser():
    """Browse and edit existing profiles."""
    profiles = _list_profiles()
    if not profiles:
        st.warning("No profiles found.")
        return

    selected = st.selectbox("Select Profile", profiles)
    if not selected:
        return

    profile = _load_profile(selected)
    user_profile = profile.get("user_profile", {})
    music_seed = user_profile.get("music_seed", {})

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Identity")
        case_id = st.text_input("Case ID", value=profile.get("meta", {}).get("case_id", ""), disabled=True)
        archetype = st.selectbox(
            "Primary Archetype",
            ARCHETYPES,
            index=ARCHETYPES.index(user_profile.get("primary_archetype", "sage")),
            key="edit_archetype",
        )
        story_thread = st.text_input(
            "Story Thread Hint",
            value=user_profile.get("story_thread_hint", ""),
            key="edit_thread",
        )

    with col2:
        st.markdown("#### Music Seed")
        genre = st.text_input(
            "Top Genre",
            value=music_seed.get("top_genre", ""),
            key="edit_genre",
        )
        bpm = st.number_input(
            "BPM",
            min_value=30,
            max_value=200,
            value=music_seed.get("bpm", BPM_DEFAULTS.get(archetype, 70)),
            key="edit_bpm",
        )
        mood_tag = st.text_input(
            "Mood Tag",
            value=music_seed.get("mood_tag", ""),
            key="edit_mood",
        )

    # JSON preview
    updated = {
        "meta": {"case_id": case_id},
        "user_profile": {
            "primary_archetype": archetype,
            "music_seed": {
                "top_genre": genre,
                "bpm": bpm,
                "mood_tag": mood_tag,
            },
            "story_thread_hint": story_thread,
        }
    }

    with st.expander("JSON Preview"):
        st.json(updated)

    if st.button("Save Profile", type="primary", key="save_existing"):
        _save_profile(selected, updated)
        st.success(f"Profile {selected} saved.")


def _render_create():
    """Create a new profile."""
    st.markdown("#### New Profile")

    col1, col2 = st.columns(2)

    with col1:
        new_id = st.text_input("Case ID (e.g. S-11, R-11, L-11)", key="new_id")
        archetype = st.selectbox("Primary Archetype", ARCHETYPES, key="new_archetype")
        story_thread = st.text_input("Story Thread Hint", key="new_thread")

    with col2:
        genre = st.text_input("Top Genre", key="new_genre")
        bpm = st.number_input("BPM", min_value=30, max_value=200,
                              value=BPM_DEFAULTS.get(archetype, 70), key="new_bpm")
        mood_tag = st.text_input("Mood Tag", key="new_mood")

    if st.button("Create Profile", type="primary", key="create_new"):
        if not new_id:
            st.error("Case ID is required.")
            return

        existing = _list_profiles()
        if new_id in existing:
            st.error(f"Profile {new_id} already exists. Use the editor to modify it.")
            return

        new_profile = {
            "meta": {"case_id": new_id},
            "user_profile": {
                "primary_archetype": archetype,
                "music_seed": {
                    "top_genre": genre,
                    "bpm": bpm,
                    "mood_tag": mood_tag,
                },
                "story_thread_hint": story_thread,
            }
        }
        _save_profile(new_id, new_profile)
        st.success(f"Profile {new_id} created.")
        st.json(new_profile)
