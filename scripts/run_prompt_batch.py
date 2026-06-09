from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.config import get_anchor_grammar
from core.llm import create_adapter
from core.llm.director import Director


PROFILE_ORDER = ["S-01", "E-01", "L-01", "R-01", "V-01"]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [jsonable(v) for v in value]
    return value


def build_profile(profile_id: str, requested_anchor: str | None = None) -> Dict[str, Any]:
    mapping = {
        "S-01": {
            "archetype": "sage",
            "story_thread_hint": "anchor_grammar_controlled",
            "music_seed": {"genre": "ambient", "bpm": 60, "mood": "soft_contemplative"},
        },
        "E-01": {
            "archetype": "explorer",
            "story_thread_hint": "anchor_grammar_controlled",
            "music_seed": {"genre": "modern_orchestral", "bpm": 90, "mood": "discovery"},
        },
        "L-01": {
            "archetype": "lover",
            "story_thread_hint": "anchor_grammar_controlled",
            "music_seed": {"genre": "warm_minimal", "bpm": 75, "mood": "intimate"},
        },
        "R-01": {
            "archetype": "rebel catalyst",
            "story_thread_hint": "anchor_grammar_controlled",
            "music_seed": {"genre": "organic_electronic", "bpm": 120, "mood": "controlled_tension"},
        },
        "V-01": {
            "archetype": "visionary mage",
            "story_thread_hint": "anchor_grammar_controlled",
            "music_seed": {"genre": "cinematic_electronic", "bpm": 100, "mood": "emergence"},
        },
    }

    if profile_id not in mapping:
        raise ValueError(f"Unknown profile_id: {profile_id}")

    profile = {
        "profile_id": profile_id,
        "user_profile": mapping[profile_id],
    }

    if requested_anchor:
        profile["anchor_override"] = requested_anchor
        profile["user_profile"]["anchor_override"] = requested_anchor

    return profile


def infer_archetype(profile_id: str) -> str:
    return {
        "S-01": "sage",
        "E-01": "explorer",
        "L-01": "lover",
        "R-01": "rebel",
        "V-01": "visionary",
    }.get(profile_id, "unknown")


def choose_requested_anchor(profile_id: str, anchor_mode: str, rng: random.Random) -> str:
    if anchor_mode == "free":
        return ""

    archetype = infer_archetype(profile_id)
    grammar = get_anchor_grammar(archetype) or {}
    allowed = grammar.get("allowed_thread_anchors", [])
    top_names = grammar.get("top_3_anchors", [])

    if top_names:
        candidates = [name for name in top_names if name]
    else:
        candidates = [a.get("name") for a in allowed if a.get("name")]

    if not candidates:
        return ""

    if anchor_mode == "random":
        return rng.choice(candidates)

    raise ValueError(f"Unknown anchor_mode: {anchor_mode}")


def extract_anchor(output: Dict[str, Any]) -> str:
    seq = output.get("sequence_thread") or {}
    if isinstance(seq, dict):
        return seq.get("anchor") or seq.get("name") or "N/A"
    if isinstance(seq, str):
        return seq
    return "N/A"


def extract_gate(output: Dict[str, Any]) -> Dict[str, Any]:
    return output.get("metadata", {}).get("archetype_gate", {}) or {}


def write_report_header(f, out_dir: Path, args: argparse.Namespace) -> None:
    profiles_label = ", ".join(args.profiles)
    f.write("# NEURØISE Prompt Batch Report\n\n")
    f.write(f"- Timestamp UTC: `{utc_timestamp()}`\n")
    f.write(f"- Model: `{args.model}`\n")
    f.write(f"- Runs per profile: `{args.runs}`\n")
    f.write(f"- Profiles: `{profiles_label}`\n")
    f.write(f"- Anchor mode: `{args.anchor_mode}`\n")
    f.write(f"- Seed: `{args.seed}`\n")
    f.write(f"- Max anchor retries: `{args.max_anchor_retries}`\n")
    f.write(f"- Output dir: `{out_dir}`\n\n")


def write_record_to_report(f, record: Dict[str, Any]) -> None:
    output = record.get("output", {})
    seq = output.get("sequence_thread") or {}
    triptych = output.get("video_triptych") or []
    ost = output.get("ost_prompt") or {}
    gate = extract_gate(output)

    f.write("\n---\n\n")
    f.write(f"## {record['profile_id']} / {record['archetype']} / run {record['run_index']}\n\n")
    f.write(f"- Timestamp UTC: `{record['timestamp_utc']}`\n")
    f.write(f"- Model: `{record['model']}`\n")
    if record.get("requested_anchor"):
        f.write(f"- Requested anchor: `{record.get('requested_anchor')}`\n")
    f.write(f"- Generated anchor: `{record.get('anchor', 'N/A')}`\n")
    f.write(f"- Anchor override status: `{record.get('anchor_override_status', 'none')}`\n")
    f.write(f"- Retry count: `{record.get('retry_count', 0)}`\n")
    f.write(f"- ArchetypeGate: `{gate.get('status', 'N/A')}`\n")
    if gate.get("matched_bans"):
        f.write(f"- Matched bans: `{gate.get('matched_bans')}`\n")
    if record.get("error"):
        f.write(f"- Error: `{record.get('error')}`\n")
    f.write("\n")

    if seq:
        f.write("### Sequence thread\n\n")
        if isinstance(seq, dict):
            for k, v in seq.items():
                f.write(f"- **{k}**: {v}\n")
        else:
            f.write(str(seq) + "\n")
        f.write("\n")

    for i, scene in enumerate(triptych):
        if not isinstance(scene, dict):
            continue
        role = scene.get("scene_role") or ["start", "evolve", "end"][i]
        f.write(f"### {role}\n\n")
        if scene.get("thread_state"):
            f.write(f"**Thread state:** {scene['thread_state']}\n\n")
        f.write((scene.get("prompt") or "").strip() + "\n\n")
        if scene.get("mood_tags"):
            f.write(f"**Mood tags:** {', '.join(scene.get('mood_tags', []))}\n\n")

    if ost:
        f.write("### OST\n\n")
        f.write(f"- **Genre:** {ost.get('genre', 'N/A')}\n")
        f.write(f"- **BPM:** {ost.get('bpm', 'N/A')}\n")
        f.write(f"- **Mood:** {ost.get('mood', 'N/A')}\n")
        f.write(f"- **Prompt:** {ost.get('prompt', '')}\n\n")

    f.write("### Manual review\n\n")
    f.write("- Anchor fidelity: 1-5\n")
    f.write("- Thread persistence: 1-5\n")
    f.write("- Transformation clarity: 1-5\n")
    f.write("- Video-generation readiness: 1-5\n")
    f.write("- Archetype coherence: 1-5\n")
    f.write("- Cliché risk: low / medium / high\n")
    f.write("- Action: KEEP / WORK / REJECT\n")
    f.write("- Notes:\n")


def create_director(model: str) -> Director:
    adapter = create_adapter(model)
    return Director(adapter=adapter)


def generate_once(
    director: Director,
    profile_id: str,
    requested_anchor: str,
) -> Tuple[Dict[str, Any], str]:
    profile = build_profile(profile_id, requested_anchor=requested_anchor or None)
    output_obj = director.generate(profile)
    output = jsonable(output_obj)
    anchor = extract_anchor(output)
    return output, anchor


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NEURØISE prompt batch tests.")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("--profiles", default="S-01,E-01,L-01,R-01,V-01")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--anchor-mode", choices=["free", "random"], default="free")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--max-anchor-retries", type=int, default=1)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    args.profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    rng = random.Random(args.seed)

    model_slug = args.model.replace(":", "-").replace("/", "-")
    out_dir = Path(args.out) if args.out else ROOT / "runs" / "prompt_batches" / f"{utc_timestamp()}_{model_slug}"
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "raw_outputs.jsonl"
    report_path = out_dir / "report.md"
    summary_path = out_dir / "summary.csv"

    director = create_director(args.model)

    summary_fields = [
        "timestamp_utc",
        "profile_id",
        "archetype",
        "model",
        "run_index",
        "status",
        "requested_anchor",
        "anchor",
        "anchor_override_status",
        "retry_count",
        "archetype_gate_status",
        "matched_bans",
        "error",
    ]

    with raw_path.open("w", encoding="utf-8") as raw_f, \
         report_path.open("w", encoding="utf-8") as report_f, \
         summary_path.open("w", encoding="utf-8", newline="") as csv_f:

        writer = csv.DictWriter(csv_f, fieldnames=summary_fields)
        writer.writeheader()
        write_report_header(report_f, out_dir, args)

        for profile_id in args.profiles:
            for run_index in range(1, args.runs + 1):
                ts = datetime.now(timezone.utc).isoformat()
                archetype = infer_archetype(profile_id)
                requested_anchor = choose_requested_anchor(profile_id, args.anchor_mode, rng)

                anchor_note = f" / requested anchor: {requested_anchor}" if requested_anchor else ""
                print(
                    f"[{ts}] Generating {profile_id} run {run_index}/{args.runs} "
                    f"with {args.model}{anchor_note}...",
                    flush=True,
                )

                record = {
                    "timestamp_utc": ts,
                    "profile_id": profile_id,
                    "archetype": archetype,
                    "model": args.model,
                    "run_index": run_index,
                    "status": "ok",
                    "requested_anchor": requested_anchor,
                    "retry_count": 0,
                    "error": "",
                }

                try:
                    output: Dict[str, Any] = {}
                    generated_anchor = ""

                    for attempt in range(args.max_anchor_retries + 1):
                        output, generated_anchor = generate_once(
                            director=director,
                            profile_id=profile_id,
                            requested_anchor=requested_anchor,
                        )

                        if not requested_anchor or generated_anchor == requested_anchor:
                            record["retry_count"] = attempt
                            break

                        record["retry_count"] = attempt

                        if attempt < args.max_anchor_retries:
                            print(
                                f"ANCHOR MISMATCH: requested `{requested_anchor}`, "
                                f"got `{generated_anchor}`. Retrying...",
                                flush=True,
                            )
                            time.sleep(max(args.sleep, 0.5))

                    record["output"] = output
                    record["anchor"] = generated_anchor

                    if requested_anchor:
                        if generated_anchor == requested_anchor:
                            record["anchor_override_status"] = "pass"
                        else:
                            record["anchor_override_status"] = "fail"
                            record["status"] = "anchor_mismatch"
                            record["error"] = (
                                f"Requested anchor `{requested_anchor}` but generated "
                                f"`{generated_anchor}` after {record['retry_count']} retry attempt(s)."
                            )
                    else:
                        record["anchor_override_status"] = "none"

                    gate = extract_gate(output)
                    record["archetype_gate_status"] = gate.get("status", "N/A")
                    record["matched_bans"] = json.dumps(gate.get("matched_bans", []), ensure_ascii=False)

                    raw_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    raw_f.flush()

                    write_record_to_report(report_f, record)
                    report_f.flush()

                    writer.writerow({k: record.get(k, "") for k in summary_fields})
                    csv_f.flush()

                except Exception as e:
                    record["status"] = "error"
                    record["error"] = str(e)
                    record["anchor"] = ""
                    record["anchor_override_status"] = "fail" if requested_anchor else "none"
                    record["archetype_gate_status"] = ""
                    record["matched_bans"] = ""

                    raw_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    raw_f.flush()

                    writer.writerow({k: record.get(k, "") for k in summary_fields})
                    csv_f.flush()

                    report_f.write(f"\n---\n\n## {profile_id} / {archetype} / run {run_index} ERROR\n\n")
                    report_f.write(f"`{record['error']}`\n\n")
                    report_f.flush()

                    print(f"ERROR: {record['error']}", flush=True)

                if args.sleep:
                    time.sleep(args.sleep)

    print("\nBatch complete.", flush=True)
    print(f"Raw: {raw_path}", flush=True)
    print(f"Report: {report_path}", flush=True)
    print(f"Summary: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
