"""
Anthropic Claude adapter.

Supporta tutti i modelli Claude via API Anthropic.

Example:
    >>> config = LLMConfig(model="claude-sonnet-4-20250514")
    >>> adapter = AnthropicAdapter(config)
    >>> response = adapter.generate("Describe a calm sea at dawn")
"""

import os
import time
import json
from typing import Any, Dict, Optional

from .base import LLMAdapter, LLMConfig, LLMResponse


class AnthropicAdapter(LLMAdapter):
    """
    Adapter per Anthropic Claude API.

    Modelli supportati:
    - claude-sonnet-4-20250514 (consigliato per bilanciamento costo/qualità)
    - claude-opus-4-20250514 (massima qualità)
    - claude-3-opus-20240229
    - claude-3-sonnet-20240229
    - claude-3-haiku-20240307
    """

    # Mapping nomi brevi -> nomi completi
    MODEL_ALIASES = {
        "claude-sonnet-4": "claude-sonnet-4-20250514",
        "claude-opus-4": "claude-opus-4-20250514",
        "claude-3-opus": "claude-3-opus-20240229",
        "claude-3-sonnet": "claude-3-sonnet-20240229",
        "claude-3-haiku": "claude-3-haiku-20240307",
    }

    def __init__(self, config: LLMConfig):
        super().__init__(config)

        # Risolvi alias del modello
        self.model = self.MODEL_ALIASES.get(config.model, config.model)

        # Lazy import per evitare errore se non installato
        try:
            import anthropic
            self.client = anthropic.Anthropic(
                api_key=config.api_key or os.getenv("ANTHROPIC_API_KEY")
            )
        except ImportError:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

    def generate(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Genera risposta con Claude.

        Args:
            user_prompt: Prompt utente
            system_prompt: System prompt (opzionale)
            **kwargs: Parametri extra (es. prefill per assistant)

        Returns:
            LLMResponse
        """
        start_time = time.time()

        messages = [{"role": "user", "content": user_prompt}]

        # Supporto per prefill (inizia risposta assistant)
        if "prefill" in kwargs:
            messages.append({
                "role": "assistant",
                "content": kwargs.pop("prefill")
            })

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system_prompt or "",
                messages=messages,
                **kwargs
            )

            latency_ms = (time.time() - start_time) * 1000

            llm_response = LLMResponse(
                content=response.content[0].text,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=response.stop_reason or "stop",
                latency_ms=latency_ms,
                raw_response={
                    "id": response.id,
                    "type": response.type,
                    "role": response.role
                }
            )

            self._update_stats(llm_response)
            return llm_response

        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {e}")

    def generate_structured(
        self,
        user_prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera output JSON strutturato.

        Usa prefill per forzare output JSON valido.

        Args:
            user_prompt: Prompt con istruzioni
            output_schema: Schema JSON atteso
            system_prompt: System prompt base

        Returns:
            Dict parsato dal JSON

        Raises:
            ValueError: Se parsing fallisce
        """
        # Aggiungi schema al system prompt
        schema_instruction = f"""

You MUST respond with valid JSON matching this schema:
```json
{json.dumps(output_schema, indent=2)}
```

Respond ONLY with the JSON, no other text."""

        full_system = (system_prompt or "") + schema_instruction

        # Usa prefill per forzare JSON
        response = self.generate(
            user_prompt=user_prompt,
            system_prompt=full_system,
            prefill="{",
            **kwargs
        )

        # Ricostruisci JSON (prefill era "{")
        json_str = "{" + response.content

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            # Prova a estrarre JSON dal contenuto
            parsed = response.parse_json()
            if parsed:
                return parsed
            raise ValueError(f"Failed to parse JSON response: {e}\nContent: {json_str[:500]}")

    def count_tokens(self, text: str) -> int:
        """
        Conta i token in un testo.

        Utile per stimare costi prima della generazione.
        """
        try:
            return self.client.count_tokens(text)
        except Exception:
            # Fallback: stima approssimativa
            return len(text) // 4
