# Changelog

## [0.2.0] - 2026-03-03

### Added
- **Profile Editor** (`app/pages/profiles.py`): Browse, edit, and create user profiles from the UI
- **Profiles** navigation entry in sidebar
- **JSONL export** for experiment results (one line per run for quick inspection)
- **Run Details** tab in Analysis page: navigate individual runs with metrics and generated content
- **Expandable run history** in Experiments page with per-run details and JSONL download
- **R008 BPM policy rule**: RED if `bpm` missing from OST, YELLOW if BPM outside archetype range

### Changed
- **Director system prompt**: added PROMPT FORMAT RULES section enforcing concise shot-list style (subject + framing + movement + light, no audio/metaphors/narration)
- **Director system prompt**: added explicit BPM requirement for OST with archetype ranges
- **Director user prompt**: emphasizes mandatory BPM field with profile reference value
- **Director `_parse_result()`**: BPM fallback — if LLM omits `bpm`, pulls from profile `music_seed.bpm`

### Fixed
- **Temperature clamp** in `OllamaAdapter`: values > 2.0 or < 0.0 are now clamped with a warning log (prevents Ollama API errors with high temperature values)

## [0.1.0] - 2026-02-23

### Added
- Initial release: NEUROISE Playground
- Director (Creative Director LLM)
- Ollama, Anthropic, OpenAI adapters
- PolicyGate with 7 validation rules
- Experiment runner with batch execution
- Streamlit UI: Home, Generate, Evaluate, Experiments, Analysis, Preview
- 30 official profiles (10 Sage, 10 Rebel, 10 Lover)
- Video generation microservice integration
