"""
Prompt Packs for ablation studies.

Each pack provides a (system_prompt, output_schema) pair.
Available packs: default, concise, detailed.
"""

from typing import Tuple

AVAILABLE_PACKS = ["default", "concise", "detailed"]


def load_prompt_pack(name: str) -> Tuple[str, dict]:
    """Load a prompt pack by name.

    Args:
        name: Pack name (default, concise, detailed)

    Returns:
        Tuple of (system_prompt, output_schema)

    Raises:
        ValueError: If pack name is unknown
    """
    if name == "default":
        from .default import SYSTEM_PROMPT, OUTPUT_SCHEMA
    elif name == "concise":
        from .concise import SYSTEM_PROMPT, OUTPUT_SCHEMA
    elif name == "detailed":
        from .detailed import SYSTEM_PROMPT, OUTPUT_SCHEMA
    else:
        raise ValueError(
            f"Unknown prompt pack: {name}. Available: {AVAILABLE_PACKS}"
        )
    return SYSTEM_PROMPT, OUTPUT_SCHEMA
