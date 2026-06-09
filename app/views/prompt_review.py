"""
Prompt Review page - fast manual review for prompt batches.

Reads runs/prompt_batches/<batch_id>/raw_outputs.jsonl
and lets a reviewer mark each generated triptych as:
green / yellow / red, with notes.

Exports:
runs/prompt_reviews/<batch_id>/manual_review_all.json
runs/prompt_reviews/<batch_id>/manual_review_red_yellow.json
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st


PROJECT_ROOT = Path(__file__).parent.parent.parent
PROMPT_BATCHES_DIR = PROJECT_ROOT / "runs" / "prompt_batches"
PROMPT_REVIEWS_DIR = PROJECT_ROOT / "runs" / "prompt_reviews"

STATUS_OPTIONS = ["unreviewed", "green", "yellow", "red"]
STATUS_LABELS = {
    "unreviewed": "⚪ Unreviewed",
    "green": "🟢 Green — usable",
    "yellow": "🟡 Yellow — needs work",
    "red": "🔴 Red — reject",
}


def _list_batches() -> List[Path]:
    if not PROMPT_BATCHES_DIR.exists():
        return []
    return sorted(
        [
            d for d in PROMPT_BATCHES_DIR.iterdir()
            if d.is_dir() and (d / "raw_outputs.jsonl").exists()
        ],
        key=lambda p: p.stat().st_mtime,
    )


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                # Keep UI resilient if one row is malformed.
                rows.append({
                    "status": "parse_error",
                    "error": f"Could not parse JSONL line: {line[:200]}",
                })
    return rows


def _review_dir(batch_id: str) -> Path:
    return PROMPT_REVIEWS_DIR / batch_id


def _review_all_path(batch_id: str) -> Path:
    return _review_dir(batch_id) / "manual_review_all.json"


def _review_red_yellow_path(batch_id: str) -> Path:
    return _review_dir(batch_id) / "manual_review_red_yellow.json"


def _review_key(row: Dict[str, Any], index: int) -> str:
    return "|".join([
        str(row.get("profile_id", "unknown")),
        str(row.get("archetype", "unknown")),
        str(row.get("run_index", index + 1)),
        str(index),
    ])


def _load_existing_reviews(batch_id: str) -> Dict[str, Dict[str, Any]]:
    path = _review_all_path(batch_id)
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    reviews = {}
    for item in data.get("items", []):
        key = item.get("review_key")
        if key:
            reviews[key] = item
    return reviews


def _scene_prompt(scene: Dict[str, Any]) -> str:
    return scene.get("prompt") or scene.get("visual_prompt") or scene.get("description") or ""


def _compact_item(
    row: Dict[str, Any],
    index: int,
    manual_status: str,
    manual_notes: str,
) -> Dict[str, Any]:
    output = row.get("output") or {}
    triptych = output.get("video_triptych") or []
    sequence_thread = output.get("sequence_thread") or {}
    ost_prompt = output.get("ost_prompt") or {}
    metadata = output.get("metadata") or {}

    scenes = []
    for scene in triptych:
        scenes.append({
            "scene_role": scene.get("scene_role"),
            "thread_state": scene.get("thread_state"),
            "prompt": _scene_prompt(scene),
            "duration_hint": scene.get("duration_hint"),
            "mood_tags": scene.get("mood_tags", []),
            "camera_hints": scene.get("camera_hints"),
        })

    return {
        "review_key": _review_key(row, index),
        "profile_id": row.get("profile_id"),
        "archetype": row.get("archetype"),
        "model": row.get("model"),
        "run_index": row.get("run_index"),
        "status": row.get("status"),
        "anchor": row.get("anchor") or sequence_thread.get("anchor"),
        "archetype_gate_status": row.get("archetype_gate_status"),
        "matched_bans": row.get("matched_bans"),
        "error": row.get("error"),
        "manual_status": manual_status,
        "manual_notes": manual_notes.strip(),
        "sequence_thread": sequence_thread,
        "scenes": scenes,
        "ost_prompt": ost_prompt,
        "metadata": {
            "archetype_detected": metadata.get("archetype_detected"),
            "story_thread_used": metadata.get("story_thread_used"),
            "coherence_notes": metadata.get("coherence_notes"),
        },
    }


def _write_review_files(batch_id: str, items: List[Dict[str, Any]]) -> Dict[str, Path]:
    out_dir = _review_dir(batch_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    all_payload = {
        "batch_id": batch_id,
        "export_type": "manual_review_all",
        "created_at_utc": now,
        "total_items": len(items),
        "items": items,
    }

    red_yellow_items = [
        item for item in items
        if item.get("manual_status") in {"yellow", "red"}
    ]

    red_yellow_payload = {
        "batch_id": batch_id,
        "export_type": "manual_review_red_yellow_only",
        "created_at_utc": now,
        "total_items": len(red_yellow_items),
        "items": red_yellow_items,
    }

    all_path = _review_all_path(batch_id)
    red_yellow_path = _review_red_yellow_path(batch_id)

    all_path.write_text(
        json.dumps(all_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    red_yellow_path.write_text(
        json.dumps(red_yellow_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "all": all_path,
        "red_yellow": red_yellow_path,
    }


def _status_counts(items: List[Dict[str, Any]]) -> Dict[str, int]:
    counts = {status: 0 for status in STATUS_OPTIONS}
    for item in items:
        status = item.get("manual_status", "unreviewed")
        counts[status] = counts.get(status, 0) + 1
    return counts


def render_prompt_review():
    st.subheader("🟡 Prompt Review")
    st.caption("Fast human review for prompt batches generated in `runs/prompt_batches/`.")

    batches = _list_batches()
    if not batches:
        st.warning("No prompt batches found. Run `scripts/run_prompt_batch.py` first.")
        return

    batch_labels = [b.name for b in batches]

    selected_label = st.selectbox(
        "Batch",
        batch_labels,
        index=len(batch_labels) - 1,
        key="prompt_review_batch",
    )
    selected_batch = PROMPT_BATCHES_DIR / selected_label
    raw_path = selected_batch / "raw_outputs.jsonl"

    rows = _read_jsonl(raw_path)
    if not rows:
        st.warning("No rows found in raw_outputs.jsonl.")
        return

    existing_reviews = _load_existing_reviews(selected_label)

    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Batch rows", len(rows))
    col2.metric("Model", rows[0].get("model", "unknown"))
    col3.metric("Profiles", len(set(r.get("profile_id") for r in rows)))
    col4.metric("Output", selected_label)

    st.caption(f"Raw: `{raw_path}`")

    profile_filter_options = ["all"] + sorted(set(str(r.get("profile_id", "unknown")) for r in rows))
    status_filter_options = ["all"] + STATUS_OPTIONS

    f1, f2 = st.columns(2)
    with f1:
        profile_filter = st.selectbox("Filter profile", profile_filter_options, key="prompt_review_profile_filter")
    with f2:
        status_filter = st.selectbox("Filter manual status", status_filter_options, key="prompt_review_status_filter")

    review_items: List[Dict[str, Any]] = []

    st.markdown("---")

    for index, row in enumerate(rows):
        key = _review_key(row, index)
        previous = existing_reviews.get(key, {})

        default_status = previous.get("manual_status", "unreviewed")
        if default_status not in STATUS_OPTIONS:
            default_status = "unreviewed"

        default_notes = previous.get("manual_notes", "")

        status_key = f"review_status_{selected_label}_{index}"
        notes_key = f"review_notes_{selected_label}_{index}"

        if status_key not in st.session_state:
            st.session_state[status_key] = default_status
        if notes_key not in st.session_state:
            st.session_state[notes_key] = default_notes

        current_status = st.session_state[status_key]

        if profile_filter != "all" and str(row.get("profile_id", "unknown")) != profile_filter:
            review_items.append(_compact_item(row, index, current_status, st.session_state[notes_key]))
            continue

        if status_filter != "all" and current_status != status_filter:
            review_items.append(_compact_item(row, index, current_status, st.session_state[notes_key]))
            continue

        output = row.get("output") or {}
        triptych = output.get("video_triptych") or []
        sequence_thread = output.get("sequence_thread") or {}

        title = (
            f"{row.get('profile_id', 'unknown')} / "
            f"{row.get('archetype', 'unknown')} / "
            f"run {row.get('run_index', index + 1)} / "
            f"anchor: {row.get('anchor') or sequence_thread.get('anchor', 'unknown')}"
        )

        with st.expander(title, expanded=current_status in {"yellow", "red"}):
            top = st.columns([1, 1, 1, 2])
            top[0].markdown(f"**Status:** `{row.get('status', 'unknown')}`")
            top[1].markdown(f"**Gate:** `{row.get('archetype_gate_status', 'n/a')}`")
            top[2].markdown(f"**Bans:** `{row.get('matched_bans', '[]')}`")
            top[3].markdown(f"**Model:** `{row.get('model', 'unknown')}`")

            if row.get("error"):
                st.error(row["error"])

            st.markdown("#### Sequence thread")
            st.write(f"**Anchor:** `{sequence_thread.get('anchor', row.get('anchor', 'unknown'))}`")
            st.write(f"**Physical description:** {sequence_thread.get('physical_description', '')}")
            st.write(f"**Transformation rule:** {sequence_thread.get('transformation_rule', '')}")

            st.markdown("#### START / EVOLVE / END prompts")

            if triptych:
                tabs = st.tabs([
                    str(scene.get("scene_role", f"scene {i+1}")).upper()
                    for i, scene in enumerate(triptych)
                ])
                for tab, scene in zip(tabs, triptych):
                    with tab:
                        st.markdown(f"**Thread state:** {scene.get('thread_state', '')}")
                        st.text_area(
                            "Prompt",
                            value=_scene_prompt(scene),
                            height=150,
                            disabled=True,
                            key=f"prompt_text_{selected_label}_{index}_{scene.get('scene_role', 'scene')}",
                        )
                        st.caption(f"Camera: {scene.get('camera_hints', '')}")
                        st.caption(f"Mood tags: {', '.join(scene.get('mood_tags', []))}")
            else:
                st.warning("No video_triptych found.")

            st.markdown("#### Manual review")
            st.radio(
                "Manual status",
                STATUS_OPTIONS,
                format_func=lambda x: STATUS_LABELS.get(x, x),
                horizontal=True,
                key=status_key,
            )
            st.text_area(
                "Notes",
                height=90,
                placeholder="Why yellow/red? Example: too poetic, anchor unclear, not standalone for Kling, bad camera movement...",
                key=notes_key,
            )

        review_items.append(
            _compact_item(
                row,
                index,
                st.session_state[status_key],
                st.session_state[notes_key],
            )
        )

    st.markdown("---")

    counts = _status_counts(review_items)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Unreviewed", counts.get("unreviewed", 0))
    c2.metric("Green", counts.get("green", 0))
    c3.metric("Yellow", counts.get("yellow", 0))
    c4.metric("Red", counts.get("red", 0))

    if st.button("Save review JSON", type="primary"):
        paths = _write_review_files(selected_label, review_items)
        st.success("Review exported.")
        st.code(f"All: {paths['all']}\nRed/Yellow: {paths['red_yellow']}")

    red_yellow_payload = {
        "batch_id": selected_label,
        "export_type": "manual_review_red_yellow_only_preview",
        "items": [
            item for item in review_items
            if item.get("manual_status") in {"yellow", "red"}
        ],
    }

    st.download_button(
        "Download red/yellow JSON",
        data=json.dumps(red_yellow_payload, indent=2, ensure_ascii=False),
        file_name=f"{selected_label}_manual_review_red_yellow.json",
        mime="application/json",
    )

    with st.expander("Red/yellow JSON preview"):
        st.json(red_yellow_payload)
