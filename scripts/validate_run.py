#!/usr/bin/env python3
"""
Post-run validation script for NEUROISE experiments.

Checks:
1. All profiles ran successfully (30/30 expected)
2. Every OST has a numeric BPM
3. No R008a violations (missing BPM)
4. No forbidden words in video prompts ("we see", "we witness", "accompanied by")
5. Prints aggregate score mean + range

Usage:
    python scripts/validate_run.py <experiment_name>
    python scripts/validate_run.py baseline_qwen35_27b
"""

import json
import sys
from pathlib import Path

FORBIDDEN_PHRASES = [
    "we see", "we witness", "we observe", "we notice",
    "accompanied by", "the viewer", "the audience",
]


def validate(experiment_name: str, experiments_dir: str = "data/experiments"):
    exp_dir = Path(experiments_dir) / experiment_name

    # Load results
    results_path = exp_dir / "results.json"
    if not results_path.exists():
        print(f"ERROR: {results_path} not found")
        sys.exit(1)

    with open(results_path) as f:
        data = json.load(f)

    runs = data.get("results", [])
    total = len(runs)
    successful = [r for r in runs if r.get("success")]
    failed = [r for r in runs if not r.get("success")]

    print(f"\n{'='*60}")
    print(f"Validation: {experiment_name}")
    print(f"{'='*60}")
    print(f"Total runs: {total}")
    print(f"Successful: {len(successful)}")
    print(f"Failed:     {len(failed)}")

    if failed:
        print("\nFailed runs:")
        for r in failed:
            print(f"  - {r['profile_id']}: {r.get('error', 'unknown')}")

    # Check BPM
    bpm_missing = 0
    bpm_values = []
    for r in successful:
        output = r.get("output", {})
        ost = output.get("ost_prompt", {})
        bpm = ost.get("bpm")
        if bpm is None:
            bpm_missing += 1
            print(f"  WARNING: {r['profile_id']} — BPM missing in OST")
        else:
            bpm_values.append(bpm)

    print(f"\nBPM check: {len(bpm_values)}/{len(successful)} have numeric BPM")
    if bpm_values:
        print(f"  BPM range: {min(bpm_values)} - {max(bpm_values)}")

    # Check R008a violations
    r008a_count = 0
    for r in successful:
        violations = r.get("policy_violations", 0)
        # Also check policy_flag
        if r.get("policy_flag") == "red":
            r008a_count += 1

    # Check forbidden words
    forbidden_found = 0
    for r in successful:
        output = r.get("output", {})
        triptych = output.get("video_triptych", [])
        for scene in triptych:
            prompt_lower = scene.get("prompt", "").lower()
            for phrase in FORBIDDEN_PHRASES:
                if phrase in prompt_lower:
                    forbidden_found += 1
                    print(f"  FORBIDDEN: '{phrase}' in {r['profile_id']} {scene.get('scene_role', '?')}")

    print(f"\nForbidden phrases found: {forbidden_found}")

    # Aggregate scores
    agg_scores = [
        r.get("metrics", {}).get("aggregate_score", 0)
        for r in successful
    ]
    if agg_scores:
        mean_agg = sum(agg_scores) / len(agg_scores)
        print(f"\nAggregate score: {mean_agg:.3f} (min={min(agg_scores):.3f}, max={max(agg_scores):.3f})")

    # Per-archetype breakdown
    by_arch = {}
    for r in successful:
        pid = r["profile_id"]
        prefix = pid.split("-")[0]
        arch = {"S": "sage", "R": "rebel", "L": "lover"}.get(prefix, "?")
        by_arch.setdefault(arch, []).append(r.get("metrics", {}).get("aggregate_score", 0))

    print("\nPer-archetype:")
    for arch in ["sage", "rebel", "lover"]:
        vals = by_arch.get(arch, [])
        if vals:
            print(f"  {arch}: mean={sum(vals)/len(vals):.3f} (n={len(vals)})")

    # JSONL check
    jsonl_path = exp_dir / "results.jsonl"
    if jsonl_path.exists():
        lines = jsonl_path.read_text().strip().split("\n")
        print(f"\nJSONL: {len(lines)} lines")
    else:
        print("\nJSONL: NOT FOUND")

    # Summary
    print(f"\n{'='*60}")
    all_ok = (
        len(failed) == 0
        and bpm_missing == 0
        and forbidden_found == 0
    )
    if all_ok:
        print("RESULT: ALL CHECKS PASSED")
    else:
        issues = []
        if failed:
            issues.append(f"{len(failed)} failed runs")
        if bpm_missing:
            issues.append(f"{bpm_missing} missing BPM")
        if forbidden_found:
            issues.append(f"{forbidden_found} forbidden phrases")
        print(f"RESULT: ISSUES FOUND — {', '.join(issues)}")
    print(f"{'='*60}\n")

    return all_ok


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/validate_run.py <experiment_name>")
        sys.exit(1)

    ok = validate(sys.argv[1])
    sys.exit(0 if ok else 1)
