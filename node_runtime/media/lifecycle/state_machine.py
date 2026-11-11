"""
AWARESPAN — Media Source State Machine
Handles explicit, idempotent source state transitions and lifecycle event hooks.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Set

from shared.logging.logger import get_logger
from node_runtime.media.sources.source import MediaSource, SourceState, SourceType

log = get_logger("node_runtime.media.lifecycle")

VALID_TRANSITIONS: Dict[SourceState, Set[SourceState]] = {
    SourceState.REGISTERED: {SourceState.AUTHENTICATING, SourceState.CONNECTING, SourceState.REJECTED},
    SourceState.AUTHENTICATING: {SourceState.CONNECTING, SourceState.REJECTED, SourceState.EXPIRED},
    SourceState.CONNECTING: {SourceState.ACTIVE, SourceState.DEGRADED, SourceState.DISCONNECTED, SourceState.REJECTED},
    SourceState.ACTIVE: {SourceState.DEGRADED, SourceState.DISCONNECTING, SourceState.DISCONNECTED, SourceState.EXPIRED},
    SourceState.DEGRADED: {SourceState.ACTIVE, SourceState.DISCONNECTING, SourceState.DISCONNECTED, SourceState.EXPIRED},
    SourceState.DISCONNECTING: {SourceState.DISCONNECTED},
    SourceState.DISCONNECTED: {SourceState.CONNECTING, SourceState.REGISTERED},
    SourceState.EXPIRED: {SourceState.REGISTERED, SourceState.CONNECTING},
    SourceState.REJECTED: {SourceState.REGISTERED},
}


class SourceStateMachine:
    """Coordinates lifecycle transitions and triggers lifecycle event hooks."""

    def __init__(self):
        self._listeners: List[Callable[[MediaSource, SourceState, SourceState, str], None]] = []

    def subscribe(self, callback: Callable[[MediaSource, SourceState, SourceState, str], None]) -> None:
        """Register an observer for source transition events (e.g. Telegram, MQTT)."""
        self._listeners.append(callback)

    def add_listener(self, callback: Callable[[MediaSource, SourceState, SourceState, str], None]) -> None:
        """Alias for subscribe."""
        self.subscribe(callback)

    def transition(
        self,
        source: MediaSource,
        target_state: SourceState,
        reason: str = "",
        force: bool = False,
    ) -> bool:
        """
        Transition a MediaSource to target_state.
        Idempotent: if already in target_state, returns True without duplicate events.
        """
        current = source.connection_state
        if current == target_state:
            return True

        if not force and target_state not in VALID_TRANSITIONS.get(current, set()):
            log.warning(
                "Illegal state transition rejected for source %s: %s -> %s (reason: %s)",
                source.source_id, current.value, target_state.value, reason
            )
            return False

        # Apply state change
        source.connection_state = target_state
        now_iso = datetime.now(timezone.utc).isoformat()

        if target_state == SourceState.ACTIVE:
            if not source.connected_at:
                source.connected_at = now_iso
            source.disconnected_at = None

        elif target_state in (SourceState.DISCONNECTED, SourceState.EXPIRED, SourceState.REJECTED):
            source.disconnected_at = now_iso
            source.camera_active = False
            source.mic_active = False

        log.info(
            "Source %s transitioned %s -> %s (reason: %s, camera=%s, mic=%s)",
            source.source_id, current.value, target_state.value, reason, source.camera_active, source.mic_active
        )

        # Notify subscribers
        for listener in self._listeners:
            try:
                listener(source, current, target_state, reason)
            except Exception as exc:
                log.warning("Lifecycle listener error for source %s: %s", source.source_id, exc)

        return True

    def update_component_state(
        self,
        source: MediaSource,
        camera_active: Optional[bool] = None,
        mic_active: Optional[bool] = None,
    ) -> None:
        """
        Fine-grained component state tracking for COMBINED sources.
        """
        if camera_active is not None:
            source.camera_active = camera_active
        if mic_active is not None:
            source.mic_active = mic_active

        # If both are inactive and was active -> degraded or disconnect
        if source.source_type == SourceType.COMBINED:
            if source.camera_active and source.mic_active:
                if source.connection_state != SourceState.ACTIVE:
                    self.transition(source, SourceState.ACTIVE, reason="Both camera and mic active")
            elif source.camera_active or source.mic_active:
                if source.connection_state == SourceState.ACTIVE:
                    self.transition(source, SourceState.DEGRADED, reason="One media track inactive")
            else:
                if source.connection_state in (SourceState.ACTIVE, SourceState.DEGRADED):
                    self.transition(source, SourceState.DISCONNECTING, reason="All media tracks ended")
