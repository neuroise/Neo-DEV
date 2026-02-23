"""
OpenAI GPT adapter.

Supporta GPT-4, GPT-4o e altri modelli OpenAI.

Example:
    >>> config = LLMConfig(model="gpt-4o")
    >>> adapter = OpenAIAdapter(config)
    >>> response = adapter.generate("Describe a stormy sea")
"""

import os
import time
import json
from typing import Any, Dict, Optional

from .base import LLMAdapter, LLMConfig, LLMResponse


class OpenAIAdapter(LLMAdapter):
    """
    Adapter per OpenAI API.

    Modelli supportati:
    - gpt-4o (consigliato)
    - gpt-4o-mini (economico)
    - gpt-4-turbo
    - gpt-4
    - gpt-3.5-turbo
    """

    # Mapping nomi brevi -> nomi completi
    MODEL_ALIASES = {
        "gpt4": "gpt-4",
        "gpt4o": "gpt-4o",
        "gpt4-turbo": "gpt-4-turbo",
        "gpt35": "gpt-3.5-turbo",
    }

    def __init__(self, config: LLMConfig):
        super().__init__(config)

        # Risolvi alias del modello
        self.model = self.MODEL_ALIASES.get(config.model, config.model)

        # Lazy import
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=config.api_key or os.getenv("OPENAI_API_KEY"),
                base_url=config.base_url
            )
        except ImportError:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

    def generate(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Genera risposta con GPT.

        Args:
            user_prompt: Prompt utente
            system_prompt: System prompt (opzionale)
            **kwargs: Parametri extra per API

        Returns:
            LLMResponse
        """
        start_time = time.time()

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": user_prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                **kwargs
            )

            latency_ms = (time.time() - start_time) * 1000

            choice = response.choices[0]

            llm_response = LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                input_tokens=response.usage.prompt_tokens if response.usage else 0,
                output_tokens=response.usage.completion_tokens if response.usage else 0,
                finish_reason=choice.finish_reason or "stop",
                latency_ms=latency_ms,
                raw_response={
                    "id": response.id,
                    "created": response.created,
                    "system_fingerprint": getattr(response, 'system_fingerprint', None)
                }
            )

            self._update_stats(llm_response)
            return llm_response

        except Exception as e:
            raise RuntimeError(f"OpenAI API error: {e}")

    def generate_structured(
        self,
        user_prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera output JSON strutturato.

        Usa response_format per JSON mode se disponibile.

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

        # Usa JSON mode se supportato
        response_format = None
        if "gpt-4" in self.model or "gpt-3.5-turbo" in self.model:
            response_format = {"type": "json_object"}

        response = self.generate(
            user_prompt=user_prompt,
            system_prompt=full_system,
            response_format=response_format,
            **kwargs
        )

        try:
            return json.loads(response.content)
        except json.JSONDecodeError as e:
            # Prova a estrarre JSON dal contenuto
            parsed = response.parse_json()
            if parsed:
                return parsed
            raise ValueError(f"Failed to parse JSON response: {e}\nContent: {response.content[:500]}")

    def generate_with_functions(
        self,
        user_prompt: str,
        functions: list,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera con function calling.

        Utile per output strutturati complessi.

        Args:
            user_prompt: Prompt utente
            functions: Lista di function definitions
            system_prompt: System prompt opzionale

        Returns:
            Dict con function_name e arguments
        """
        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[{"type": "function", "function": f} for f in functions],
                tool_choice="auto",
                **kwargs
            )

            choice = response.choices[0]

            if choice.message.tool_calls:
                tool_call = choice.message.tool_calls[0]
                return {
                    "function_name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                }

            # Fallback se nessuna function call
            return {
                "function_name": None,
                "content": choice.message.content
            }

        except Exception as e:
            raise RuntimeError(f"OpenAI function calling error: {e}")
