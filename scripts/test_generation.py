#!/usr/bin/env python3
"""
Test script per prima generazione su profilo S-01.

Testa l'intera pipeline:
1. Carica profilo
2. Valida con SchemaGate
3. Genera con Director
4. Valida output con PolicyGate
5. Log eventi

Usage:
    python scripts/test_generation.py --model claude-sonnet-4
    python scripts/test_generation.py --model llama3.2:8b --ollama-url http://localhost:11434
    python scripts/test_generation.py --model gpt-4o
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm import create_adapter, Director, LLMConfig
from core.gating import PolicyGate, validate_profile, validate_output
from core.state import SessionStateMachine, SessionState, create_session
from core.logging import EventLog, EventTypes


def load_profile(profile_id: str = "S-01") -> dict:
    """Carica un profilo dalla directory official."""
    profile_path = Path(__file__).parent.parent / "data" / "profiles" / "official" / f"{profile_id}.json"

    if not profile_path.exists():
        raise FileNotFoundError(f"Profile not found: {profile_path}")

    with open(profile_path) as f:
        return json.load(f)


def run_test(
    model: str,
    profile_id: str = "S-01",
    ollama_url: str = None,
    verbose: bool = True
) -> dict:
    """
    Esegue test completo di generazione.

    Args:
        model: Nome del modello LLM
        profile_id: ID del profilo (default: S-01)
        ollama_url: URL Ollama se si usa modello locale
        verbose: Stampa output dettagliato

    Returns:
        Dict con risultati del test
    """
    results = {
        "profile_id": profile_id,
        "model": model,
        "timestamp": datetime.now().isoformat(),
        "steps": {}
    }

    # Initialize logging
    log_dir = Path(__file__).parent.parent / "data" / "logs"
    event_log = EventLog(log_dir)

    if verbose:
        print(f"\n{'='*60}")
        print(f"NEURØISE Test Generation")
        print(f"{'='*60}")
        print(f"Model: {model}")
        print(f"Profile: {profile_id}")
        print(f"{'='*60}\n")

    # Step 1: Load profile
    if verbose:
        print("📂 Step 1: Loading profile...")

    try:
        profile = load_profile(profile_id)
        results["steps"]["load_profile"] = {"status": "success"}
        if verbose:
            print(f"   ✓ Loaded {profile_id}")
            print(f"   Archetype: {profile.get('user_profile', {}).get('primary_archetype')}")
    except Exception as e:
        results["steps"]["load_profile"] = {"status": "error", "error": str(e)}
        if verbose:
            print(f"   ✗ Error: {e}")
        return results

    # Step 2: Validate profile
    if verbose:
        print("\n🔍 Step 2: Validating profile...")

    is_valid, errors = validate_profile(profile)
    results["steps"]["validate_profile"] = {
        "status": "success" if is_valid else "error",
        "errors": errors
    }
    if verbose:
        if is_valid:
            print("   ✓ Profile is valid")
        else:
            print(f"   ✗ Validation errors: {errors}")

    # Step 3: Create session
    if verbose:
        print("\n📋 Step 3: Creating session...")

    session = create_session(
        profile_id,
        archetype=profile.get("user_profile", {}).get("primary_archetype"),
        model=model
    )
    session.transition(SessionState.INTAKE, {"profile": profile})

    event_log.append(
        EventTypes.SESSION_START,
        session.session_id,
        {"profile_id": profile_id, "model": model}
    )

    results["session_id"] = session.session_id
    if verbose:
        print(f"   ✓ Session created: {session.session_id}")

    # Step 4: Initialize LLM adapter
    if verbose:
        print(f"\n🤖 Step 4: Initializing {model}...")

    try:
        kwargs = {}
        if ollama_url:
            kwargs["base_url"] = ollama_url

        adapter = create_adapter(model, temperature=0.7, **kwargs)
        results["steps"]["init_llm"] = {"status": "success"}
        if verbose:
            print(f"   ✓ Adapter initialized: {adapter}")
    except Exception as e:
        results["steps"]["init_llm"] = {"status": "error", "error": str(e)}
        if verbose:
            print(f"   ✗ Error: {e}")
            print(f"   Hint: Make sure {model} is available")
            if "ollama" in model.lower() or "llama" in model.lower():
                print(f"   Try: ollama pull {model}")
        return results

    # Step 5: Generate with Director
    if verbose:
        print("\n🎬 Step 5: Generating content...")

    session.transition(SessionState.PROFILE, {"validated": True})
    session.transition(SessionState.PLAN)
    session.transition(SessionState.GENERATE)

    event_log.append(
        EventTypes.GENERATION_START,
        session.session_id,
        {"model": model}
    )

    try:
        director = Director(adapter)
        output = director.generate(profile)

        results["steps"]["generation"] = {"status": "success"}
        results["output"] = output.to_dict()

        event_log.append(
            EventTypes.GENERATION_COMPLETE,
            session.session_id,
            {"output_preview": str(output.to_dict())[:200]}
        )

        if verbose:
            print("   ✓ Generation complete!")
            print(f"\n   Video Triptych:")
            for scene in output.video_triptych:
                role = scene.get("scene_role", "?")
                prompt_preview = scene.get("prompt", "")[:80]
                print(f"   [{role.upper()}] {prompt_preview}...")

            print(f"\n   OST Prompt:")
            ost = output.ost_prompt
            print(f"   Genre: {ost.get('genre', '?')}, BPM: {ost.get('bpm', '?')}")
            print(f"   {ost.get('prompt', '')[:100]}...")

    except Exception as e:
        results["steps"]["generation"] = {"status": "error", "error": str(e)}
        event_log.append(
            EventTypes.GENERATION_ERROR,
            session.session_id,
            {"error": str(e)}
        )
        if verbose:
            print(f"   ✗ Generation error: {e}")
        return results

    # Step 6: Validate output with PolicyGate
    if verbose:
        print("\n🛡️ Step 6: Validating output with PolicyGate...")

    policy_gate = PolicyGate()
    policy_result = policy_gate.check(output.to_dict(), profile)

    results["steps"]["policy_check"] = {
        "status": "success",
        "flag": policy_result.flag.value,
        "violations": len(policy_result.violations),
        "warnings": len(policy_result.warnings),
        "passed_rules": len(policy_result.passed_rules)
    }

    event_log.append(
        EventTypes.POLICY_CHECK,
        session.session_id,
        policy_result.to_dict()
    )

    if verbose:
        flag_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        print(f"   {flag_emoji.get(policy_result.flag.value, '?')} Flag: {policy_result.flag.value.upper()}")
        print(f"   Passed: {len(policy_result.passed_rules)} rules")

        if policy_result.violations:
            print(f"   ⚠️ Violations ({len(policy_result.violations)}):")
            for v in policy_result.violations[:3]:
                print(f"      - {v.rule_name}: {v.message}")

        if policy_result.warnings:
            print(f"   ⚠️ Warnings ({len(policy_result.warnings)}):")
            for w in policy_result.warnings[:3]:
                print(f"      - {w.rule_name}: {w.message}")

    # Step 7: Finalize session
    session.transition(SessionState.DELIVER)
    session.transition(SessionState.ARCHIVE)

    event_log.append(
        EventTypes.SESSION_END,
        session.session_id,
        {"final_flag": policy_result.flag.value}
    )

    # Summary
    results["success"] = policy_result.is_ok
    results["final_flag"] = policy_result.flag.value

    if verbose:
        print(f"\n{'='*60}")
        print(f"TEST {'PASSED' if results['success'] else 'FAILED'}")
        print(f"Session: {session.session_id}")
        print(f"{'='*60}\n")

    # Save results
    output_dir = Path(__file__).parent.parent / "data" / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"test_{profile_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    if verbose:
        print(f"Results saved to: {output_file}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Test NEURØISE generation pipeline")
    parser.add_argument(
        "--model", "-m",
        default="llama3.2:8b",
        help="Model to use (claude-sonnet-4, gpt-4o, llama3.2:8b, etc.)"
    )
    parser.add_argument(
        "--profile", "-p",
        default="S-01",
        help="Profile ID to test (default: S-01)"
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Ollama server URL (default: http://localhost:11434)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output"
    )

    args = parser.parse_args()

    results = run_test(
        model=args.model,
        profile_id=args.profile,
        ollama_url=args.ollama_url,
        verbose=not args.quiet
    )

    # Exit code based on success
    sys.exit(0 if results.get("success") else 1)


if __name__ == "__main__":
    main()
