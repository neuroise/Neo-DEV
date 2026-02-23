"""
Append-only Event Log for NEURØISE.

Allineato con Framework NoNoise v2.
Permette tracciabilità completa e replay delle sessioni.

Example:
    >>> log = EventLog()
    >>> event_id = log.append(
    ...     event_type=EventTypes.GENERATION_START,
    ...     session_id="S-01_20260125",
    ...     payload={"model": "claude-sonnet-4", "profile_id": "S-01"}
    ... )
    >>> events = log.query(session_id="S-01_20260125")
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from dataclasses import dataclass


class EventTypes:
    """Tipi di evento standardizzati per il sistema."""

    # Session lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_ERROR = "session_error"

    # Profile handling
    PROFILE_RECEIVED = "profile_received"
    PROFILE_VALIDATED = "profile_validated"
    PROFILE_REJECTED = "profile_rejected"

    # Generation pipeline
    GENERATION_START = "generation_start"
    GENERATION_COMPLETE = "generation_complete"
    GENERATION_ERROR = "generation_error"

    # Policy/Gating
    POLICY_CHECK = "policy_check"
    POLICY_PASS = "policy_pass"
    POLICY_FAIL = "policy_fail"

    # Metrics
    METRICS_COMPUTED = "metrics_computed"
    METRICS_AGGREGATED = "metrics_aggregated"

    # Feedback
    FEEDBACK_RECEIVED = "feedback_received"
    FEEDBACK_PROCESSED = "feedback_processed"

    # State machine
    STATE_TRANSITION = "state_transition"

    # Experiments
    EXPERIMENT_START = "experiment_start"
    EXPERIMENT_END = "experiment_end"
    EXPERIMENT_RUN = "experiment_run"

    # System
    SYSTEM_INFO = "system_info"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Event:
    """Singolo evento nel log."""

    event_id: str
    timestamp: datetime
    event_type: str
    session_id: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Serializza l'evento."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "session_id": self.session_id,
            "payload": self.payload,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """Deserializza un evento."""
        return cls(
            event_id=data["event_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=data["event_type"],
            session_id=data["session_id"],
            payload=data.get("payload", {}),
            metadata=data.get("metadata", {})
        )


class EventLog:
    """
    Sistema di logging append-only per eventi.

    Caratteristiche:
    - Append-only per immutabilità
    - File JSONL per semplicità e grep-ability
    - Query per session_id, event_type, time range
    - Supporto per replay di sessioni

    Attributes:
        log_dir: Directory per i file di log
        current_log_file: File di log corrente (giornaliero)
    """

    def __init__(self, log_dir: Path = None):
        """
        Inizializza il sistema di logging.

        Args:
            log_dir: Directory per i log. Default: data/logs
        """
        self.log_dir = log_dir or Path("data/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._update_log_file()

    def _update_log_file(self) -> None:
        """Aggiorna il file di log corrente (rotazione giornaliera)."""
        today = datetime.now().strftime("%Y%m%d")
        self.current_log_file = self.log_dir / f"events_{today}.jsonl"

    def append(
        self,
        event_type: str,
        session_id: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Aggiunge un evento al log.

        Args:
            event_type: Tipo di evento (usa EventTypes)
            session_id: ID della sessione
            payload: Dati dell'evento
            metadata: Metadati opzionali (user, source, etc.)

        Returns:
            event_id: ID univoco dell'evento

        Example:
            >>> event_id = log.append(
            ...     EventTypes.GENERATION_START,
            ...     "S-01_20260125",
            ...     {"model": "claude-sonnet-4"}
            ... )
        """
        self._update_log_file()

        event_id = str(uuid.uuid4())
        event = Event(
            event_id=event_id,
            timestamp=datetime.now(),
            event_type=event_type,
            session_id=session_id,
            payload=payload,
            metadata=metadata or {}
        )

        with open(self.current_log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

        return event_id

    def query(
        self,
        session_id: Optional[str] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Query eventi dal log.

        Args:
            session_id: Filtra per sessione
            event_type: Filtra per tipo evento
            start_time: Eventi dopo questo timestamp
            end_time: Eventi prima di questo timestamp
            limit: Numero massimo di eventi

        Returns:
            Lista di Event che matchano i criteri

        Example:
            >>> events = log.query(session_id="S-01_20260125")
            >>> generation_events = log.query(event_type=EventTypes.GENERATION_START)
        """
        events = []

        # Itera su tutti i file di log
        for log_file in sorted(self.log_dir.glob("events_*.jsonl")):
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        data = json.loads(line)
                        event = Event.from_dict(data)

                        # Applica filtri
                        if session_id and event.session_id != session_id:
                            continue
                        if event_type and event.event_type != event_type:
                            continue
                        if start_time and event.timestamp < start_time:
                            continue
                        if end_time and event.timestamp > end_time:
                            continue

                        events.append(event)

                        if limit and len(events) >= limit:
                            return events

                    except json.JSONDecodeError:
                        continue

        return events

    def get_session_events(self, session_id: str) -> List[Event]:
        """Shortcut per ottenere tutti gli eventi di una sessione."""
        return self.query(session_id=session_id)

    def get_session_timeline(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Timeline formattata di una sessione.

        Utile per debug e visualizzazione.
        """
        events = self.get_session_events(session_id)
        return [
            {
                "time": e.timestamp.strftime("%H:%M:%S.%f")[:-3],
                "type": e.event_type,
                "summary": self._summarize_payload(e.payload)
            }
            for e in events
        ]

    def _summarize_payload(self, payload: Dict[str, Any], max_len: int = 50) -> str:
        """Crea un riassunto del payload per visualizzazione."""
        if not payload:
            return ""

        # Prova chiavi comuni
        for key in ["model", "profile_id", "state", "score", "error", "message"]:
            if key in payload:
                value = str(payload[key])
                if len(value) > max_len:
                    value = value[:max_len] + "..."
                return f"{key}={value}"

        # Fallback: prime chiavi
        summary = ", ".join(f"{k}={v}" for k, v in list(payload.items())[:2])
        if len(summary) > max_len:
            summary = summary[:max_len] + "..."
        return summary

    def replay_session(
        self,
        session_id: str,
        callback: Optional[callable] = None
    ) -> List[Event]:
        """
        Replay di una sessione per debug/analisi.

        Args:
            session_id: Sessione da replayare
            callback: Funzione chiamata per ogni evento

        Returns:
            Lista di eventi in ordine cronologico
        """
        events = sorted(
            self.get_session_events(session_id),
            key=lambda e: e.timestamp
        )

        if callback:
            for event in events:
                callback(event)

        return events

    def count_by_type(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Dict[str, int]:
        """Conta eventi per tipo (statistiche)."""
        events = self.query(start_time=start_time, end_time=end_time)
        counts: Dict[str, int] = {}

        for event in events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1

        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def get_recent_errors(self, limit: int = 10) -> List[Event]:
        """Ottieni gli errori più recenti."""
        error_events = self.query(event_type=EventTypes.ERROR, limit=limit * 2)
        error_events += self.query(event_type=EventTypes.GENERATION_ERROR, limit=limit * 2)
        error_events += self.query(event_type=EventTypes.SESSION_ERROR, limit=limit * 2)

        # Sort by timestamp descending and limit
        error_events.sort(key=lambda e: e.timestamp, reverse=True)
        return error_events[:limit]


# Singleton per uso globale
_global_log: Optional[EventLog] = None


def get_event_log(log_dir: Optional[Path] = None) -> EventLog:
    """
    Ottieni l'istanza globale del log.

    Example:
        >>> from core.logging import get_event_log, EventTypes
        >>> log = get_event_log()
        >>> log.append(EventTypes.SESSION_START, "S-01", {})
    """
    global _global_log
    if _global_log is None:
        _global_log = EventLog(log_dir)
    return _global_log
