"""
Ollama adapter for local LLM inference.

Supporta qualsiasi modello disponibile in Ollama (llama, mistral, qwen, etc.)
Ideale per development locale su Mac e deployment su DGX con Docker.

Example:
    >>> config = LLMConfig(model="llama3.2", base_url="http://localhost:11434")
    >>> adapter = OllamaAdapter(config)
    >>> response = adapter.generate("Describe a calm sea")

Docker usage:
    docker run -d --gpus all -v ollama:/root/.ollama -p 11434:11434 ollama/ollama
"""

import os
import time
import json
import logging
import requests
from typing import Any, Dict, List, Optional

from .base import LLMAdapter, LLMConfig, LLMResponse

logger = logging.getLogger(__name__)


class OllamaAdapter(LLMAdapter):
    """
    Adapter per Ollama API locale.

    Modelli consigliati per NEURØISE:
    - llama3.2:70b (se disponibile VRAM sufficiente)
    - llama3.1:70b
    - qwen2.5:72b
    - mistral-large
    - mixtral:8x22b

    Per Mac con Apple Silicon (M1/M2/M3):
    - llama3.2:8b
    - mistral:7b
    - qwen2.5:14b

    Attributes:
        base_url: URL del server Ollama (default: http://localhost:11434)
        model: Nome del modello Ollama
    """

    DEFAULT_URL = "http://localhost:11434"

    # Modelli consigliati per task creativo
    RECOMMENDED_MODELS = [
        "llama3.2:70b",
        "llama3.1:70b",
        "qwen2.5:72b",
        "mistral-large",
        "llama3.2:8b",
        "mistral:7b"
    ]

    # Ollama accepts temperature in [0.0, 2.0]
    MAX_TEMPERATURE = 2.0

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        self.base_url = config.base_url or self.DEFAULT_URL
        self.model = config.model

        # Clamp temperature to valid range
        if config.temperature > self.MAX_TEMPERATURE:
            logger.warning(
                "Temperature %.1f exceeds Ollama max (%.1f), clamping to %.1f",
                config.temperature, self.MAX_TEMPERATURE, self.MAX_TEMPERATURE,
            )
            config.temperature = self.MAX_TEMPERATURE
        elif config.temperature < 0.0:
            logger.warning(
                "Temperature %.1f is negative, clamping to 0.0",
                config.temperature,
            )
            config.temperature = 0.0

        self._verify_connection()

    def _verify_connection(self) -> None:
        """Verifica connessione a Ollama server."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise ConnectionError(f"Ollama server returned {response.status_code}")
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. "
                f"Start Ollama with: ollama serve"
            )

    def list_models(self) -> List[str]:
        """Lista modelli disponibili su Ollama."""
        response = requests.get(f"{self.base_url}/api/tags")
        if response.status_code == 200:
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
        return []

    def pull_model(self, model_name: str) -> bool:
        """
        Scarica un modello (se non presente).

        Args:
            model_name: Nome del modello da scaricare

        Returns:
            True se successo
        """
        print(f"Pulling model {model_name}...")
        response = requests.post(
            f"{self.base_url}/api/pull",
            json={"name": model_name},
            stream=True
        )

        for line in response.iter_lines():
            if line:
                data = json.loads(line)
                if "status" in data:
                    print(f"  {data['status']}")
                if data.get("status") == "success":
                    return True

        return response.status_code == 200

    def generate(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Genera risposta con modello Ollama locale.

        Args:
            user_prompt: Prompt utente
            system_prompt: System prompt (opzionale)
            **kwargs: Parametri extra (num_ctx, num_predict, etc.)

        Returns:
            LLMResponse
        """
        start_time = time.time()

        # Costruisci payload
        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
                "top_p": self.config.top_p,
            }
        }

        if system_prompt:
            payload["system"] = system_prompt

        # Aggiungi opzioni extra
        if "num_ctx" in kwargs:
            payload["options"]["num_ctx"] = kwargs["num_ctx"]

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            # Ollama restituisce token counts in eval_count e prompt_eval_count
            llm_response = LLMResponse(
                content=data.get("response", ""),
                model=data.get("model", self.model),
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                finish_reason="stop" if data.get("done") else "length",
                latency_ms=latency_ms,
                raw_response={
                    "total_duration": data.get("total_duration"),
                    "load_duration": data.get("load_duration"),
                    "eval_duration": data.get("eval_duration"),
                    "context": data.get("context")
                }
            )

            self._update_stats(llm_response)
            return llm_response

        except requests.exceptions.Timeout:
            raise RuntimeError(f"Ollama request timed out after {self.config.timeout}s")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama API error: {e}")

    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> LLMResponse:
        """
        Genera con formato chat (multi-turn).

        Args:
            messages: Lista di messaggi [{"role": "user", "content": "..."}]
            **kwargs: Parametri extra

        Returns:
            LLMResponse
        """
        start_time = time.time()

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            data = response.json()

            latency_ms = (time.time() - start_time) * 1000

            llm_response = LLMResponse(
                content=data.get("message", {}).get("content", ""),
                model=data.get("model", self.model),
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
                finish_reason="stop" if data.get("done") else "length",
                latency_ms=latency_ms
            )

            self._update_stats(llm_response)
            return llm_response

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Ollama chat error: {e}")

    def generate_structured(
        self,
        user_prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera output JSON strutturato.

        Usa format: json per forzare output JSON valido.

        Args:
            user_prompt: Prompt con istruzioni
            output_schema: Schema JSON atteso
            system_prompt: System prompt base

        Returns:
            Dict parsato dal JSON
        """
        # Aggiungi schema al prompt
        schema_instruction = f"""

You MUST respond with valid JSON matching this schema:
```json
{json.dumps(output_schema, indent=2)}
```

Respond ONLY with the JSON, no other text or explanation."""

        full_system = (system_prompt or "") + schema_instruction

        # Usa format: json per Ollama
        start_time = time.time()

        payload = {
            "model": self.model,
            "prompt": user_prompt,
            "system": full_system,
            "stream": False,
            "format": "json",  # Forza output JSON
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            }
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            data = response.json()

            content = data.get("response", "")
            logger.info(f"Ollama structured response length={len(content)}, first 300 chars: {content[:300]}")

            # Parse JSON
            return json.loads(content)

        except json.JSONDecodeError as e:
            # Fallback: prova a estrarre JSON
            try:
                # Cerca JSON nel contenuto
                content = data.get("response", "")
                start_idx = content.find("{")
                end_idx = content.rfind("}") + 1
                if start_idx != -1 and end_idx > start_idx:
                    return json.loads(content[start_idx:end_idx])
            except:
                pass
            raise ValueError(f"Failed to parse JSON: {e}\nContent: {content[:500]}")

    def get_model_info(self) -> Dict[str, Any]:
        """Ottieni info sul modello corrente."""
        response = requests.post(
            f"{self.base_url}/api/show",
            json={"name": self.model}
        )
        if response.status_code == 200:
            return response.json()
        return {}


# Factory function per creare adapter Ollama
def create_ollama_adapter(
    model: str = "llama3.2:8b",
    base_url: str = None,
    **kwargs
) -> OllamaAdapter:
    """
    Crea un adapter Ollama.

    Args:
        model: Nome modello Ollama
        base_url: URL server (default: localhost:11434)
        **kwargs: Altri parametri per LLMConfig

    Returns:
        OllamaAdapter configurato

    Example:
        >>> adapter = create_ollama_adapter("mistral:7b")
        >>> adapter = create_ollama_adapter("llama3.2:70b", base_url="http://dgx:11434")
    """
    config = LLMConfig(
        model=model,
        base_url=base_url or OllamaAdapter.DEFAULT_URL,
        **kwargs
    )
    return OllamaAdapter(config)
