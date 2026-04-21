"""Concise prompt pack — minimal instructions, same rules."""

from core.llm.director import build_director_system_prompt, OUTPUT_SCHEMA

SYSTEM_PROMPT = build_director_system_prompt("concise")
