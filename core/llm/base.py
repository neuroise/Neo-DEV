"""
Base classes for LLM adapters.

Defines the interface that all LLM adapters must implement.

Example:
    >>> config = LLMConfig(model="claude-sonnet-4", temperature=0.7)
    >>> adapter = AnthropicAdapter(config)
    >>> response = adapter.generate(user_prompt="Hello")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import json


@dataclass
class LLMConfig:
    """Configurazione per un adapter LLM."""

    model: str
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0
    stop_sequences: Optional[List[str]] = None
    timeout: int = 300  # secondi (5 min per modelli grandi)

    # Provider-specific
    api_key: Optional[str] = None  # Se None, usa env var
    base_url: Optional[str] = None  # Per endpoint custom

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "stop_sequences": self.stop_sequences,
            "timeout": self.timeout
        }


@dataclass
class LLMResponse:
    """Risposta da un LLM."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    finish_reason: str
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

    # Raw response per debug
    raw_response: Optional[Dict[str, Any]] = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "finish_reason": self.finish_reason,
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp.isoformat()
        }

    def parse_json(self) -> Optional[Dict[str, Any]]:
        """Prova a parsare il contenuto come JSON."""
        try:
            # Cerca JSON nel contenuto (può essere in code block)
            content = self.content.strip()

            # Rimuovi markdown code block se presente
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            return json.loads(content.strip())
        except json.JSONDecodeError:
            return None


class LLMAdapter(ABC):
    """
    Interfaccia base per adapter LLM.

    Tutti gli adapter (Anthropic, OpenAI, etc.) devono implementare
    questa interfaccia per garantire intercambiabilità.
    """

    def __init__(self, config: LLMConfig):
        """
        Inizializza l'adapter.

        Args:
            config: Configurazione LLM
        """
        self.config = config
        self._call_count = 0
        self._total_tokens = 0

    @abstractmethod
    def generate(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Genera una risposta dal LLM.

        Args:
            user_prompt: Prompt dell'utente
            system_prompt: System prompt opzionale
            **kwargs: Parametri aggiuntivi provider-specific

        Returns:
            LLMResponse con il contenuto generato
        """
        pass

    @abstractmethod
    def generate_structured(
        self,
        user_prompt: str,
        output_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Genera output JSON strutturato.

        Args:
            user_prompt: Prompt dell'utente
            output_schema: JSON schema per l'output atteso
            system_prompt: System prompt opzionale

        Returns:
            Dict parsato dal JSON generato

        Raises:
            ValueError: Se il parsing JSON fallisce
        """
        pass

    def get_stats(self) -> Dict[str, Any]:
        """Statistiche di utilizzo dell'adapter."""
        return {
            "model": self.config.model,
            "call_count": self._call_count,
            "total_tokens": self._total_tokens,
            "avg_tokens_per_call": (
                self._total_tokens / self._call_count
                if self._call_count > 0 else 0
            )
        }

    def _update_stats(self, response: LLMResponse) -> None:
        """Aggiorna le statistiche interne."""
        self._call_count += 1
        self._total_tokens += response.total_tokens

    @property
    def model_name(self) -> str:
        """Nome del modello in uso."""
        return self.config.model

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model})"


# Utility per creare adapter dal nome del modello
def create_adapter(model: str, **kwargs) -> LLMAdapter:
    """
    Factory per creare adapter dal nome del modello.

    Args:
        model: Nome del modello (es. "claude-sonnet-4", "gpt-4o", "llama3.2:8b")
        **kwargs: Parametri aggiuntivi per LLMConfig

    Returns:
        LLMAdapter appropriato

    Example:
        >>> adapter = create_adapter("claude-sonnet-4", temperature=0.5)
        >>> adapter = create_adapter("llama3.2:8b", base_url="http://localhost:11434")
        >>> adapter = create_adapter("ollama:mistral:7b")  # Prefisso esplicito
    """
    from .anthropic_adapter import AnthropicAdapter
    from .openai_adapter import OpenAIAdapter
    from .ollama_adapter import OllamaAdapter

    # Provider detection
    model_lower = model.lower()

    # Ollama: modelli con prefisso "ollama:" o pattern tipici Ollama
    ollama_patterns = ["llama", "mistral", "qwen", "phi", "gemma", "codellama", "vicuna"]
    is_ollama = (
        model_lower.startswith("ollama:") or
        (any(p in model_lower for p in ollama_patterns) and ":" in model)
    )

    if model_lower.startswith("ollama:"):
        # Rimuovi prefisso
        actual_model = model[7:]
        config = LLMConfig(model=actual_model, **kwargs)
        return OllamaAdapter(config)
    elif "claude" in model_lower or "anthropic" in model_lower:
        config = LLMConfig(model=model, **kwargs)
        return AnthropicAdapter(config)
    elif "gpt" in model_lower or "openai" in model_lower:
        config = LLMConfig(model=model, **kwargs)
        return OpenAIAdapter(config)
    elif is_ollama:
        config = LLMConfig(model=model, **kwargs)
        return OllamaAdapter(config)
    else:
        # Default: prova Ollama per modelli sconosciuti
        config = LLMConfig(model=model, **kwargs)
        try:
            return OllamaAdapter(config)
        except ConnectionError:
            raise ValueError(
                f"Unknown model provider for: {model}. "
                f"Use prefix 'ollama:', 'claude-', or 'gpt-'"
            )
