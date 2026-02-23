"""
State Machine for NEURØISE session tracking.

Allineato con Framework NoNoise v2.
Gestisce le transizioni di stato delle sessioni di generazione.

States:
    IDLE -> INTAKE -> PROFILE -> PLAN -> GENERATE -> DELIVER -> FEEDBACK -> ARCHIVE

Example:
    >>> sm = SessionStateMachine("session_001")
    >>> sm.transition(SessionState.INTAKE, {"profile_id": "S-01"})
    True
    >>> sm.current_state
    <SessionState.INTAKE: 'intake'>
"""

from enum import Enum
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
import uuid


class SessionState(Enum):
    """Stati possibili di una sessione di generazione."""

    IDLE = "idle"           # Sistema in attesa
    INTAKE = "intake"       # Ricezione profilo utente
    PROFILE = "profile"     # Validazione profilo
    PLAN = "plan"           # Pianificazione creativa
    GENERATE = "generate"   # Generazione LLM
    DELIVER = "deliver"     # Consegna output
    FEEDBACK = "feedback"   # Raccolta feedback
    ARCHIVE = "archive"     # Sessione archiviata


@dataclass
class StateTransition:
    """Record di una transizione di stato."""

    from_state: SessionState
    to_state: SessionState
    timestamp: datetime
    payload: Optional[Dict[str, Any]] = None
    transition_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def to_dict(self) -> Dict[str, Any]:
        """Serializza la transizione per logging/storage."""
        return {
            "transition_id": self.transition_id,
            "from": self.from_state.value,
            "to": self.to_state.value,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload
        }


class SessionStateMachine:
    """
    Gestisce le transizioni di stato per una sessione.

    Implementa il pattern State Machine con validazione delle transizioni
    e audit trail completo per tracciabilità.

    Attributes:
        session_id: Identificatore univoco della sessione
        current_state: Stato corrente
        history: Lista di tutte le transizioni effettuate
        metadata: Metadati della sessione (profilo, config, etc.)
    """

    # Transizioni valide: from_state -> [to_states]
    VALID_TRANSITIONS: Dict[SessionState, List[SessionState]] = {
        SessionState.IDLE: [SessionState.INTAKE],
        SessionState.INTAKE: [SessionState.PROFILE, SessionState.IDLE],
        SessionState.PROFILE: [SessionState.PLAN, SessionState.INTAKE],
        SessionState.PLAN: [SessionState.GENERATE, SessionState.PROFILE],
        SessionState.GENERATE: [SessionState.DELIVER, SessionState.PLAN],
        SessionState.DELIVER: [SessionState.FEEDBACK, SessionState.GENERATE],
        SessionState.FEEDBACK: [SessionState.ARCHIVE, SessionState.GENERATE],
        SessionState.ARCHIVE: [SessionState.IDLE],
    }

    def __init__(
        self,
        session_id: str,
        initial_state: SessionState = SessionState.IDLE,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Inizializza una nuova sessione.

        Args:
            session_id: ID univoco per questa sessione
            initial_state: Stato iniziale (default: IDLE)
            metadata: Metadati opzionali della sessione
        """
        self.session_id = session_id
        self.current_state = initial_state
        self.history: List[StateTransition] = []
        self.metadata = metadata or {}
        self.created_at = datetime.now()

    def can_transition(self, to_state: SessionState) -> bool:
        """Verifica se una transizione è valida."""
        valid_targets = self.VALID_TRANSITIONS.get(self.current_state, [])
        return to_state in valid_targets

    def transition(
        self,
        to_state: SessionState,
        payload: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Esegue una transizione di stato.

        Args:
            to_state: Stato di destinazione
            payload: Dati associati alla transizione

        Returns:
            True se transizione riuscita, False altrimenti

        Example:
            >>> sm.transition(SessionState.INTAKE, {"profile": profile_data})
        """
        if not self.can_transition(to_state):
            return False

        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=datetime.now(),
            payload=payload
        )

        self.history.append(transition)
        self.current_state = to_state
        return True

    def force_transition(
        self,
        to_state: SessionState,
        payload: Optional[Dict[str, Any]] = None,
        reason: str = "forced"
    ) -> None:
        """
        Forza una transizione (per recovery/debug).

        Usa con cautela - bypassa la validazione.
        """
        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=datetime.now(),
            payload={"_forced": True, "_reason": reason, **(payload or {})}
        )

        self.history.append(transition)
        self.current_state = to_state

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Restituisce l'audit trail completo delle transizioni."""
        return [t.to_dict() for t in self.history]

    def get_duration(self, from_state: SessionState, to_state: SessionState) -> Optional[float]:
        """
        Calcola la durata tra due stati (in secondi).

        Utile per metriche di performance.
        """
        from_time = None
        to_time = None

        for t in self.history:
            if t.to_state == from_state and from_time is None:
                from_time = t.timestamp
            if t.to_state == to_state and to_time is None:
                to_time = t.timestamp

        if from_time and to_time:
            return (to_time - from_time).total_seconds()
        return None

    def reset(self) -> None:
        """Reset della sessione a IDLE (mantiene history)."""
        self.transition(SessionState.IDLE, {"_reset": True})

    def to_dict(self) -> Dict[str, Any]:
        """Serializza lo stato completo della sessione."""
        return {
            "session_id": self.session_id,
            "current_state": self.current_state.value,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "history": self.get_audit_trail(),
            "transition_count": len(self.history)
        }

    def __repr__(self) -> str:
        return f"SessionStateMachine(id={self.session_id}, state={self.current_state.value})"


# Convenience function per creare sessioni
def create_session(profile_id: str, **metadata) -> SessionStateMachine:
    """
    Factory per creare una nuova sessione.

    Args:
        profile_id: ID del profilo utente
        **metadata: Metadati aggiuntivi

    Returns:
        SessionStateMachine inizializzata

    Example:
        >>> session = create_session("S-01", archetype="sage")
    """
    session_id = f"{profile_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    return SessionStateMachine(
        session_id=session_id,
        metadata={"profile_id": profile_id, **metadata}
    )
