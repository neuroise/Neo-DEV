# NEURØISE / Neo-DEV — Anchor Grammar Prototype Branch

## Branch

`prototype/anchor-grammar-director`

## Status

Prototype / experimental branch.

This branch contains the current AWS sandbox work around Director generation, continuity-thread control, anchor grammar, Gemini provider support and generation export tooling.

It is not intended as a final production merge yet. The goal is to make the current prototype visible and reviewable by the UNIPI development team without modifying `main`.

---

## 1. Why this branch exists

During the first playground tests, the Director was able to generate valid structured outputs, but the resulting video prompts were often too atmospheric and weakly connected across the three scenes.

The issue was not mainly JSON validity or basic LLM availability. The issue was narrative structure and archetype-specific visual control.

Baseline generations often behaved like:

```text
START = mood board
EVOLVE = another mood board
END = beautiful closing atmosphere

The desired behavior is instead:

START = one visible sign appears
EVOLVE = the same sign changes or is reread
END = the sign resolves into a coherent micro-story

This branch introduces a more controlled generation framework based on continuity anchors.

2. Core concept: continuity anchor

A continuity anchor is a single, physically observable, filmable element that persists across:

START → EVOLVE → END

The anchor may transform in one of three ways:

physical     = the object or phenomenon changes state
perceptual   = the same object is reread through scale, framing or context
hybrid       = both physical and perceptual transformation happen

The anchor must be:

physical
visible
specific
filmable
marine / coastal / yacht-adjacent
persistent across the triptych
archetype-specific
suitable for text-to-video generation

The anchor must not be:

a mood
a feeling
generic ocean
generic waves
generic light
generic energy
generic beauty
generic possibility
3. Problems observed in baseline testing

Baseline archetype tests produced recurring failure modes:

SAGE      → cloud gap / light column / spiritual revelation
EXPLORER  → generic drone tourism / coastline / cave
LOVER     → sunset beach / wet sand / romantic cliché
REBEL     → breaking wave / barrel / crash / surf energy
VISIONARY → prismatic glow / luminous network / submerged city / sci-fi imagery

The model tended to resolve broad archetypal concepts through familiar visual clichés.

This branch is an attempt to move from:

archetype = mood keywords

to:

archetype = controlled visual grammar + allowed anchors + forbidden failure modes
4. Main changes in this branch
4.1 Gemini provider support

The playground was extended to support Google Gemini through the OpenAI-compatible API path.

Tested models:

gemini-2.5-flash
gemini-2.5-pro

Gemini Flash is useful for quick iteration, but we observed occasional provider-side 503 high demand errors. Gemini Pro has been used as a fallback during tests.

4.2 Automatic UI export pipeline

The playground now exports generation runs automatically.

Expected output structure:

runs/ui_exports/<date_model>/
  raw_outputs.jsonl
  report.md
  summary.csv

Purpose:

- avoid manual copy/paste of generated prompts
- preserve raw structured LLM output
- support human review
- support future batch testing
- support regression comparison across prompt/config changes

runs/ should not be committed.

4.3 Director output schema extension

The Director now supports an explicit sequence_thread object:

{
  "sequence_thread": {
    "anchor": "...",
    "physical_description": "...",
    "transformation_rule": "...",
    "why_it_matches_archetype": "...",
    "forbidden_generic_substitutes": []
  }
}

Each scene also includes a thread_state field:

{
  "scene_role": "start",
  "thread_state": "...",
  "prompt": "...",
  "duration_hint": 5,
  "mood_tags": []
}

This makes it possible to evaluate whether the declared thread is actually preserved across the triptych.

4.4 ArchetypeGate prototype

A first ArchetypeGate prototype has been added.

The goal is to separate:

PolicyGate       → safety / format / broad constraints
ArchetypeGate    → cliché detection / archetype mismatch / forbidden anchors
Human Review     → final creative evaluation

This distinction matters because an output can be:

Policy GREEN
but ArchetypeGate FAIL

Example:

A Rebel output based on a breaking wave may pass general policy,
but still fail the Rebel/Catalyst visual grammar.
4.5 New anchor grammar config

A new config file was added:

core/config/anchor_grammar.json

This file contains a test-oriented anchor grammar for:

sage
explorer
lover
rebel
visionary

Each archetype includes:

reading
anchor_principles
allowed_thread_anchors
preferred_transformations
forbidden_thread_anchors
forbidden_terms
known_failure_mode
top_3_anchors

This is intentionally separated from archetypes.json.

Current conceptual split:

archetypes.json       = identity, mood, music, general visual language
anchor_grammar.json  = concrete continuity anchors, transformations, bans, failure modes
4.6 Config loader

core/config/__init__.py now includes helper functions:

load_anchor_grammar()
get_anchor_grammar(archetype)

Alias resolution supports profile labels such as:

S-01 → sage
E-01 → explorer
L-01 → lover
R-01 → rebel
V-01 → visionary
4.7 Director prompt injection from anchor grammar

The Director now injects the relevant anchor grammar into the generation prompt.

The model is instructed to:

- select one continuity anchor from the allowed list
- use that anchor across START / EVOLVE / END
- avoid inventing generic anchors
- respect forbidden anchors and terms
- avoid known failure modes

This has already improved the three most problematic archetypes.

5. Early test results
SAGE

Before:

cloud gap → light column → luminous path

After anchor grammar:

driftwood branch → aligned with coastline → planted as vertical landscape marker

Interpretation:

object → observation → landscape reading

This is much closer to the intended Sage behavior.

REBEL / CATALYST

Before:

wave crest → barrel → crash → foam aftermath

After anchor grammar:

sail tension / rigging cable / structural force line

Interpretation:

held tension → force line → controlled activation

This is much closer to the intended Rebel/Catalyst behavior and avoids surf-action clichés.

VISIONARY / MAGE

Before:

iridescent patch → glowing network → submerged city / transcendent grid

After anchor grammar:

wet dark stone → salt crystals forming → dendritic mineral geometry

Interpretation:

latent order forming through a real natural process

This is a major improvement in physical grounding.

6. Current known issues
6.1 UI thread display

The UI still has a legacy profile-level Thread field that may show the original static thread hint, for example:

single_cloud_gap

even when the actual generated sequence_thread.anchor is correct.

A safer approach is to keep the profile thread display unchanged and add a separate post-generation field:

Generated anchor: <sequence_thread.anchor>

This should be cleaned up before merging.

6.2 Gemini provider errors

Gemini Flash occasionally returns:

503 - high demand / unavailable

A UI-level clean error message and retry/fallback strategy should be added.

Recommended behavior:

- no Streamlit traceback for temporary provider errors
- user-facing message suggesting retry or model switch
- optional automatic retry
- optional fallback from flash to pro
6.3 OST vocabulary drift

Video prompts improved significantly, but OST prompts can still reuse older abstract vocabulary such as:

ethereal
revelation
light emergence
awe-inspiring
cinematic electronic

Anchor/archetype vocabulary constraints should eventually apply to the OST prompt as well.

6.4 PolicyGate alignment

The current PolicyGate may return RED/YELLOW even when the creative result is improved under the new anchor grammar.

Future UI/reporting should show separately:

PolicyGate
ArchetypeGate
Human Review

instead of treating a single flag as the full quality signal.

7. Recommended next steps
P1.3 — Stabilization
- clean generated anchor display in UI
- improve provider error handling
- ensure ArchetypeGate reads from anchor_grammar.json consistently
- remove backup/runtime files from repository
P2 — Controlled anchor test

Run one controlled generation per archetype using a specific strong anchor:

SAGE      → bare_driftwood_branch or smooth_oval_pebble_suiseki
EXPLORER  → taut_white_nautical_rope
LOVER     → hand_trailing_water_from_yacht
REBEL     → sail_in_perfect_tension or taut_rigging_cable_under_load
VISIONARY → salt_crystallization_on_dark_stone

Goal:

Verify that the Director reliably respects the selected anchor grammar.
P3 — 25-output batch

After anchor compliance is stable:

5 archetypes × 5 generations = 25 outputs

Evaluation dimensions:

JSON OK
Policy OK
ArchetypeGate PASS / FAIL
anchor fidelity
thread persistence
transformation quality
generator readiness
cliché risk
human review score
P4 — Brand and strategy layers

Only introduce brand and strategy after archetype grammar is stable.

Reason:

avoid mixing too many variables too early
8. Notes for reviewers

This branch is intended for review and parallel development.

Please treat it as:

prototype-grade
conceptually important
not yet production-clean

Key files to inspect:

core/config/anchor_grammar.json
core/config/__init__.py
core/llm/director.py
core/llm/archetype_gate.py
core/utils/run_exporter.py
app/main.py
core/llm/base.py
docker-compose.yml

Runtime outputs, backups and .env files should not be committed.

9. Summary

This branch explores a shift from archetype mood prompting to controlled archetype anchor grammar.

The most important learning so far:

The quality bottleneck was not only the model.
It was the seed layer.

By giving the Director concrete, archetype-specific anchors, the system produces more coherent, more distinctive and more video-ready triptychs.

This branch provides the first working prototype of that direction.

---

## 12. Progress update — 2026-06-09 — Review UI, Flash mode and anchor enforcement

### What changed

The prototype moved from simple prompt batch generation toward a more usable review loop:

Flash batch generation
→ controlled random anchor selection
→ hard anchor override
→ summary-level compliance checks
→ Prompt Review UI
→ manual green / yellow / red review
→ red/yellow JSON export for correction

### Prompt Review UI

A new Streamlit view was added:

app/views/prompt_review.py

The view reads prompt batches from:

runs/prompt_batches/

and allows a reviewer to select a batch, inspect each generated run, view START / EVOLVE / END prompts, see requested anchor vs generated anchor, flag each run manually as green/yellow/red, add review notes, export all reviews, and export only yellow/red items for follow-up analysis.

Review outputs are saved under:

runs/prompt_reviews/<batch_id>/
  manual_review_all.json
  manual_review_red_yellow.json

These generated review files remain local and are not committed.

### Default test model

From this point forward, fast development batches should use gemini-2.5-flash.

Gemini Pro remains reserved for milestone validation or partner-facing quality checks.

### Controlled random anchor selection

The batch runner now supports controlled random anchor selection:

--anchor-mode random
--seed <number>

This allows prompt batches to explore different anchors while remaining reproducible.

### Anchor enforcement

The Director now supports an explicit anchor_override field in the profile.

When active, the model is not allowed to choose another anchor, sequence_thread.anchor must exactly match the requested anchor, and every scene must use that requested anchor as the physical continuity element.

The batch summary now records:

requested_anchor
anchor
anchor_override_status
retry_count

This makes anchor mismatch visible immediately.

### JSON parsing robustness

Gemini Flash sometimes returns valid JSON wrapped in markdown code fences.

The Director fallback parser now cleans common wrappers before attempting json.loads().

This reduced parse failures in Flash mode.

### Current batch result

A Flash random-anchor batch completed with:

15 / 15 generated outputs parsed successfully
15 / 15 anchor overrides respected
1 / 15 ArchetypeGate fail

The remaining fail was useful: Visionary generated the banned word ethereal inside a real video prompt for the sea_smoke_vertical_columns anchor.

This confirms that the gate is catching meaningful prompt-language issues rather than only structural failures.

### Important design decision: video prompt gate vs OST gate

The next validation logic should separate video-prompt constraints from OST constraints.

Video prompts should remain strict. If a forbidden keyword appears inside START / EVOLVE / END prompts, the system should either retry the generation with an explicit correction message, or apply a hard substitution / sanitization rule when the replacement is safe and deterministic.

Forbidden terms should not silently pass into final video-generation prompts.

OST prompts should not use the same forbidden-language policy. For music generation, poetic or abstract vocabulary can be useful and is often handled well by downstream music tools.

The OST check should focus on musical control parameters only:

- BPM / tempo range
- energy level
- mood family
- genre / instrumentation coherence
- archetype consistency

The OST should not fail only because it uses words that would be risky inside a video prompt.

### Next recommended implementation step

Implement a split validation layer:

VideoPromptGate:
  strict on forbidden visual terms
  strict on raw anchor IDs in scene prompts
  strict on anchor continuity
  strict on visible physical transformation

OSTGate:
  light validation
  check BPM, energy, mood and genre only

Then add one of these policies for forbidden video prompt terms:

--forbidden-policy retry
--forbidden-policy replace

Recommended first implementation: retry first, hard replace only for safe lexical substitutions.
