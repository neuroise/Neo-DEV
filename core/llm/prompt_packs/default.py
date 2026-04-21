"""Default prompt pack — re-exports from Director."""

from core.llm.director import build_director_system_prompt, OUTPUT_SCHEMA

SYSTEM_PROMPT = build_director_system_prompt("default")
