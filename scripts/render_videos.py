#!/usr/bin/env python3
"""
Render video triptychs for an experiment using the video-gen service.

Submits all triptychs one by one (sequential — one model load at a time),
polls until done, downloads to data/outputs/videos/{experiment}/{profile_id}/.

Usage:
    python scripts/render_videos.py --experiment baseline_30_llama70b_v3 --model wan2.2-t2v-a14b
    python scripts/render_videos.py --experiment baseline_30_llama70b_v3 --model wan2.2-ti2v-5b --profiles S-01 S-02
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.generation import VideoClient


def load_experiment(experiments_dir: str, name: str):
    path = Path(experiments_dir) / name / "results.json"
    if not path.exists():
        print(f"Experiment not found: {path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def render_profile(
    client: VideoClient,
    profile_id: str,
    output: dict,
    model: str,
    output_dir: Path,
    neg_prompt: str,
):
    """Render a single profile's triptych."""
    triptych = output.get("video_triptych", [])
    if len(triptych) < 3:
        print(f"  {profile_id}: skip (only {len(triptych)} scenes)")
        return False

    scenes = []
    for scene in triptych:
        scenes.append({
            "role": scene.get("scene_role", "start"),
            "prompt": scene.get("prompt", ""),
        })

    # Submit triptych
    try:
        result = client.submit_triptych(
            scenes=scenes,
            model=model,
            negative_prompt=neg_prompt,
            num_frames=81,       # ~3.4s at 24fps
            width=832,
            height=480,
            guidance_scale=5.0,
        )
        triptych_id = result["triptych_id"]
        print(f"  {profile_id}: submitted triptych {triptych_id}")
    except Exception as e:
        print(f"  {profile_id}: submit failed: {e}")
        return False

    # Poll until done
    try:
        status = client.poll_triptych(
            triptych_id, wait=True, interval=5.0, timeout=3600.0
        )
    except TimeoutError:
        print(f"  {profile_id}: timeout")
        return False

    if status.get("state") != "completed":
        print(f"  {profile_id}: FAILED - {status.get('state')}")
        for s in status.get("scenes", []):
            if s.get("error"):
                print(f"    {s.get('role')}: {s['error']}")
        return False

    # Download videos
    profile_dir = output_dir / profile_id
    profile_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(status.get("scenes", [])):
        if scene.get("state") == "completed" and scene.get("video_url"):
            role = scenes[i]["role"]
            dest = profile_dir / f"{role}.mp4"
            try:
                client.download(scene["job_id"], "output.mp4", dest_path=str(dest))
            except Exception as e:
                print(f"    download error ({role}): {e}")

    # Save metadata
    meta = {
        "profile_id": profile_id,
        "triptych_id": triptych_id,
        "model": model,
        "scenes": [
            {
                "role": scenes[i]["role"],
                "prompt": scenes[i]["prompt"],
                "job_id": s.get("job_id"),
                "state": s.get("state"),
            }
            for i, s in enumerate(status.get("scenes", []))
        ],
    }
    (profile_dir / "meta.json").write_text(json.dumps(meta, indent=2))

    elapsed = status.get("elapsed_seconds", "?")
    print(f"  {profile_id}: DONE ({elapsed}s)")
    return True


def main():
    parser = argparse.ArgumentParser(description="Render video triptychs")
    parser.add_argument("--experiment", "-e", required=True)
    parser.add_argument("--model", "-m", default="wan2.2-t2v-a14b")
    parser.add_argument("--video-url", default="http://localhost:8000")
    parser.add_argument("--experiments-dir", default="data/experiments")
    parser.add_argument("--output-dir", default=None,
                        help="Output dir (default: data/outputs/videos/{experiment})")
    parser.add_argument("--profiles", nargs="*", default=None,
                        help="Specific profiles to render (default: all)")
    parser.add_argument("--neg-prompt", default="blurry, low quality, distorted, watermark, text, logo",
                        help="Negative prompt")
    args = parser.parse_args()

    # Load experiment
    data = load_experiment(args.experiments_dir, args.experiment)
    runs = [r for r in data.get("results", []) if r.get("success") and r.get("output")]

    if args.profiles:
        runs = [r for r in runs if r["profile_id"] in args.profiles]

    if not runs:
        print("No runs to render.")
        sys.exit(1)

    # Output directory
    output_dir = Path(args.output_dir or f"data/outputs/videos/{args.experiment}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Skip already rendered
    already_done = set()
    for d in output_dir.iterdir():
        if d.is_dir() and (d / "meta.json").exists():
            already_done.add(d.name)

    to_render = [r for r in runs if r["profile_id"] not in already_done]
    print(f"Experiment: {args.experiment}")
    print(f"Model: {args.model}")
    print(f"Profiles: {len(runs)} total, {len(already_done)} done, {len(to_render)} to render")
    print(f"Output: {output_dir}")
    print()

    if not to_render:
        print("All profiles already rendered!")
        sys.exit(0)

    client = VideoClient(args.video_url)

    # Verify service
    try:
        h = client.health()
        print(f"Video service: {h.get('status')} (GPU: {h.get('gpu_name', '?')})")
    except Exception as e:
        print(f"Cannot reach video service at {args.video_url}: {e}")
        sys.exit(1)

    # Render one by one
    success = 0
    failed = 0
    start_time = time.time()

    for i, run in enumerate(to_render):
        pid = run["profile_id"]
        print(f"[{i+1}/{len(to_render)}] {pid}")
        ok = render_profile(
            client, pid, run["output"], args.model, output_dir, args.neg_prompt
        )
        if ok:
            success += 1
        else:
            failed += 1

    elapsed = time.time() - start_time
    print(f"\nDone: {success} rendered, {failed} failed in {elapsed/60:.1f} min")
    print(f"Avg: {elapsed/max(success,1)/60:.1f} min/profile")


if __name__ == "__main__":
    main()
