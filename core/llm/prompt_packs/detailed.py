"""Detailed prompt pack — extended instructions with per-archetype examples and rubric."""

from core.llm.director import build_director_system_prompt, OUTPUT_SCHEMA

SYSTEM_PROMPT = build_director_system_prompt("detailed")
