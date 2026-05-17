"""
Smoke test: generate videos with LTX 2.3 Distilled from existing experiment prompts.

Usage (from within the video-gen container or from host with API running):
    python3 scripts/test_ltx_generation.py --url http://localhost:8000

Or via Docker:
    docker exec neuroise-video-gen python3 /app/scripts/test_ltx_generation.py
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests


def compose_ltx_prompt(visual_prompt: str, ost: dict) -> str:
    parts = [visual_prompt]
    audio_parts = []
    if ost.get("prompt"):
        audio_parts.append(ost["prompt"])
    if ost.get("genre"):
        audio_parts.append(f"Genre: {ost['genre']}")
    if ost.get("bpm"):
        audio_parts.append(f"{ost['bpm']} BPM")
    if ost.get("mood"):
        audio_parts.append(f"Mood: {ost['mood']}")
    if ost.get("instruments_hint"):
        audio_parts.append(f"Instruments: {ost['instruments_hint']}")
    if audio_parts:
        parts.append("Background music: " + ", ".join(audio_parts))
    return ". ".join(parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--results-file", default="/app/../data/experiments/baseline_30_llama70b_v3/results.jsonl")
    parser.add_argument("--entry-index", type=int, default=0)
    parser.add_argument("--model", default="ltx-2.3-distilled")
    parser.add_argument("--num-frames", type=int, default=25)
    parser.add_argument("--width", type=int, default=512)
    parser.add_argument("--height", type=int, default=512)
    args = parser.parse_args()

    results_path = Path(args.results_file)
    if not results_path.exists():
        for candidate in [
            Path("/app/data/experiments/baseline_30_llama70b_v3/results.jsonl"),
            Path("data/experiments/baseline_30_llama70b_v3/results.jsonl"),
        ]:
            if candidate.exists():
                results_path = candidate
                break

    print(f"Reading entry {args.entry_index} from {results_path}")
    with open(results_path) as f:
        for i, line in enumerate(f):
            if i == args.entry_index:
                entry = json.loads(line)
                break
        else:
            print(f"Entry {args.entry_index} not found")
            sys.exit(1)

    output = entry.get("output", {})
    triptych = output.get("video_triptych", [])
    ost = output.get("ost_prompt", {})
    profile_id = entry.get("profile_id", "unknown")
    archetype = output.get("metadata", {}).get("archetype_detected", "unknown")

    print(f"Profile: {profile_id}, Archetype: {archetype}")
    print(f"Model: {args.model}, Frames: {args.num_frames}, Size: {args.width}x{args.height}")
    print()

    # Health check
    try:
        r = requests.get(f"{args.url}/health", timeout=5)
        health = r.json()
        print(f"Service: {health.get('status')}, GPU: {health.get('gpu_name', 'N/A')}")
    except Exception as e:
        print(f"Service not available: {e}")
        sys.exit(1)

    # Build triptych request
    scenes = []
    for scene in triptych:
        visual = scene.get("prompt", "")
        prompt = compose_ltx_prompt(visual, ost)
        scenes.append({"role": scene.get("scene_role", "start"), "prompt": prompt})
        print(f"[{scene.get('scene_role')}] {visual[:80]}...")

    print()
    payload = {
        "scenes": scenes,
        "model": args.model,
        "num_frames": args.num_frames,
        "width": args.width,
        "height": args.height,
        "audio_enabled": True,
        "use_fp8": False,
    }

    print("Submitting triptych...")
    r = requests.post(f"{args.url}/generate/triptych", json=payload, timeout=30)
    r.raise_for_status()
    tri = r.json()
    triptych_id = tri["triptych_id"]
    print(f"Triptych ID: {triptych_id}")

    # Poll until done
    start = time.time()
    while True:
        time.sleep(5)
        r = requests.get(f"{args.url}/triptych/{triptych_id}", timeout=10)
        status = r.json()
        state = status.get("state")
        progress = status.get("progress", 0)
        elapsed = time.time() - start
        print(f"  [{elapsed:.0f}s] State: {state}, Progress: {progress*100:.0f}%")

        if state in ("completed", "failed"):
            break
        if elapsed > 3600:
            print("TIMEOUT")
            sys.exit(1)

    print()
    if state == "completed":
        print("SUCCESS!")
        for i, scene in enumerate(status.get("scenes", [])):
            audio = "with audio" if scene.get("audio_included") else "no audio"
            print(f"  Scene {i+1}: {scene.get('video_url')} ({audio}, {scene.get('elapsed_seconds', '?')}s)")
    else:
        print("FAILED!")
        for scene in status.get("scenes", []):
            if scene.get("error"):
                print(f"  Error: {scene['error'][:200]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
