from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def _to_jsonable(obj: Any) -> Any:
    """Convert dataclasses, pydantic objects, custom classes and nested values to JSON-safe data."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj

    if is_dataclass(obj):
        return _to_jsonable(asdict(obj))

    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]

    if hasattr(obj, "model_dump"):
        try:
            return _to_jsonable(obj.model_dump())
        except Exception:
            pass

    if hasattr(obj, "dict"):
        try:
            return _to_jsonable(obj.dict())
        except Exception:
            pass

    if hasattr(obj, "__dict__"):
        try:
            return _to_jsonable(vars(obj))
        except Exception:
            pass

    return str(obj)


def _safe_slug(value: str) -> str:
    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "-")
        .replace("/", "-")
        .replace(":", "-")
        .replace("_", "-")
    )


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _profile_id(profile: Any) -> str:
    profile = _to_jsonable(profile)
    return (
        _get(profile, "case_id")
        or _get(profile, "id")
        or _get(profile, "profile_id")
        or _get(_get(profile, "meta", {}), "case_id")
        or "unknown-profile"
    )


def _primary_archetype(profile: Any) -> str:
    profile = _to_jsonable(profile)
    return (
        _get(profile, "primary_archetype")
        or _get(_get(profile, "user_profile", {}), "primary_archetype")
        or _get(_get(profile, "meta", {}), "primary_archetype")
        or "unknown-archetype"
    )



def _extract_sequence_thread(output: Any) -> Any:
    output = _to_jsonable(output)

    if isinstance(output, dict):
        for key in ["sequence_thread", "continuity_thread", "thread"]:
            if key in output:
                return output[key]

        for wrapper_key in ["data", "content", "result", "output"]:
            nested = output.get(wrapper_key)
            if isinstance(nested, dict):
                for key in ["sequence_thread", "continuity_thread", "thread"]:
                    if key in nested:
                        return nested[key]

    return None


def _extract_triptych(output: Any) -> List[Any]:
    output = _to_jsonable(output)

    if isinstance(output, dict):
        for key in ["video_triptych", "scenes", "triptych"]:
            value = output.get(key)
            if isinstance(value, list):
                return value

        # Some DirectorOutput wrappers may store the useful payload inside these keys
        for wrapper_key in ["data", "content", "result", "output"]:
            nested = output.get(wrapper_key)
            if isinstance(nested, dict):
                for key in ["video_triptych", "scenes", "triptych"]:
                    value = nested.get(key)
                    if isinstance(value, list):
                        return value

    return []


def _scene_text(scene: Any) -> str:
    scene = _to_jsonable(scene)

    if isinstance(scene, dict):
        return (
            scene.get("visual_prompt")
            or scene.get("prompt")
            or scene.get("description")
            or json.dumps(scene, ensure_ascii=False, indent=2)
        )

    return str(scene)


def _scene_role(scene: Any, index: int) -> str:
    scene = _to_jsonable(scene)
    defaults = ["START", "EVOLVE", "END"]

    if isinstance(scene, dict):
        return (
            scene.get("scene_role")
            or scene.get("phase")
            or scene.get("role")
            or (defaults[index] if index < len(defaults) else f"SCENE {index + 1}")
        )

    return defaults[index] if index < len(defaults) else f"SCENE {index + 1}"


def save_generation_run(
    output: Any,
    profile: Any,
    model: str,
    provider: str = "",
    base_dir: str = "runs/ui_exports",
) -> Dict[str, str]:
    now = datetime.utcnow()

    output_json = _to_jsonable(output)
    profile_json = _to_jsonable(profile)

    profile_id = _profile_id(profile_json)
    archetype = _primary_archetype(profile_json)

    run_slug = f"{now.strftime('%Y%m%d')}_{_safe_slug(model)}"
    run_dir = Path(base_dir) / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp_utc": now.isoformat(timespec="seconds") + "Z",
        "profile_id": profile_id,
        "archetype": archetype,
        "model": model,
        "provider": provider,
        "profile": profile_json,
        "output": output_json,
    }

    raw_path = run_dir / "raw_outputs.jsonl"
    with raw_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary_path = run_dir / "summary.csv"
    summary_exists = summary_path.exists()
    with summary_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp_utc",
                "profile_id",
                "archetype",
                "model",
                "provider",
                "json_ok",
                "policy_ok",
                "archetype_score",
                "continuity_score",
                "generator_readiness",
                "cliche_risk",
                "action",
                "notes",
            ],
        )
        if not summary_exists:
            writer.writeheader()

        writer.writerow(
            {
                "timestamp_utc": record["timestamp_utc"],
                "profile_id": profile_id,
                "archetype": archetype,
                "model": model,
                "provider": provider,
                "json_ok": "OK",
                "policy_ok": "OK",
                "archetype_score": "",
                "continuity_score": "",
                "generator_readiness": "",
                "cliche_risk": "",
                "action": "",
                "notes": "",
            }
        )

    report_path = run_dir / "report.md"
    triptych = _extract_triptych(output_json)
    sequence_thread = _extract_sequence_thread(output_json)

    with report_path.open("a", encoding="utf-8") as f:
        f.write("\n\n---\n\n")
        f.write(f"## {profile_id} / {archetype}\n\n")
        f.write(f"- Timestamp UTC: `{record['timestamp_utc']}`\n")
        f.write(f"- Provider: `{provider}`\n")
        f.write(f"- Model: `{model}`\n")
        f.write("- JSON: OK\n")
        f.write("- Policy: OK\n\n")

        if sequence_thread:
            f.write("### Sequence thread\n\n")
            if isinstance(sequence_thread, dict):
                for k, v in sequence_thread.items():
                    f.write(f"- **{k}**: {v}\n")
                f.write("\n")
            else:
                f.write(str(sequence_thread).strip() + "\n\n")

        if triptych:
            for i, scene in enumerate(triptych):
                role = _scene_role(scene, i)
                text = _scene_text(scene)
                f.write(f"### {role}\n\n")
                scene_json = _to_jsonable(scene)
                if isinstance(scene_json, dict) and scene_json.get("thread_state"):
                    f.write(f"**Thread state:** {scene_json.get('thread_state')}\n\n")
                f.write(text.strip())
                f.write("\n\n")
        else:
            f.write("### Raw output\n\n")
            f.write("```json\n")
            f.write(json.dumps(output_json, ensure_ascii=False, indent=2))
            f.write("\n```\n\n")

        f.write("### Manual review\n\n")
        f.write("- Archetype score: \n")
        f.write("- Thread exists: yes/no\n")
        f.write("- Thread is physical: 1-5\n")
        f.write("- Thread persists across scenes: 1-5\n")
        f.write("- Thread transforms: 1-5\n")
        f.write("- Generator readiness: \n")
        f.write("- Cliché risk: \n")
        f.write("- Action: KEEP / WORK / REJECT\n")
        f.write("- Notes: \n")

    return {
        "run_dir": str(run_dir),
        "raw_outputs": str(raw_path),
        "summary": str(summary_path),
        "report": str(report_path),
    }
