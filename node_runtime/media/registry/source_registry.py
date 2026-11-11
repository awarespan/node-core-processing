"""
AWARESPAN — Media Source Registry
Thread-safe central registry for all active, standby, and disconnected media sources.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import threading
import time
from typing import Dict, List, Optional

from shared.logging.logger import get_logger
from node_runtime.media.lifecycle.state_machine import SourceStateMachine
from node_runtime.media.sources.source import MediaSource, SourceOrigin, SourceState, SourceType

log = get_logger("node_runtime.media.registry")


class MediaSourceRegistry:
    """Manages active and historical media sources on the edge node."""

    def __init__(self, state_machine: Optional[SourceStateMachine] = None):
        self.sm = state_machine or SourceStateMachine()
        self.state_machine = self.sm
        self._sources: Dict[str, MediaSource] = {}
        self._lock = threading.RLock()

    def get_all_sources(self) -> List[MediaSource]:
        with self._lock:
            return list(self._sources.values())

    def deregister_source(self, source_id: str, reason: str = "Unregistered") -> bool:
        return self.remove_source(source_id, reason=reason)

    def update_heartbeat(self, source_id: str) -> None:
        self.record_heartbeat(source_id)

    def register_source(self, source: MediaSource) -> bool:
        """Register a new media source."""
        with self._lock:
            self._sources[source.source_id] = source
            log.info("Registered media source %s (%s, %s)", source.source_id, source.source_type.value, source.source_origin.value)
            return True

    def get_source(self, source_id: str) -> Optional[MediaSource]:
        with self._lock:
            return self._sources.get(source_id)

    def update_state(self, source_id: str, target_state: SourceState, reason: str = "") -> bool:
        with self._lock:
            source = self._sources.get(source_id)
            if not source:
                log.warning("Cannot update state: source %s not found", source_id)
                return False
            return self.sm.transition(source, target_state, reason=reason)

    def record_heartbeat(self, source_id: str) -> None:
        with self._lock:
            source = self._sources.get(source_id)
            if source:
                source.record_heartbeat()

    def list_sources(
        self,
        source_type: Optional[SourceType] = None,
        origin: Optional[SourceOrigin] = None,
        active_only: bool = False,
    ) -> List[MediaSource]:
        with self._lock:
            results = list(self._sources.values())
            if source_type:
                results = [s for s in results if s.source_type == source_type]
            if origin:
                results = [s for s in results if s.source_origin == origin]
            if active_only:
                results = [s for s in results if s.connection_state in (SourceState.ACTIVE, SourceState.DEGRADED)]
            return results

    def remove_source(self, source_id: str, reason: str = "Unregistered") -> bool:
        with self._lock:
            source = self._sources.get(source_id)
            if not source:
                return False
            if source.connection_state not in (SourceState.DISCONNECTED, SourceState.EXPIRED, SourceState.REJECTED):
                self.sm.transition(source, SourceState.DISCONNECTED, reason=reason)
            del self._sources[source_id]
            log.info("Removed source %s (%s)", source_id, reason)
            return True

    def check_stale_sources(self, timeout_sec: float = 30.0) -> List[MediaSource]:
        """
        Identify active sources that have not reported a heartbeat within timeout_sec.
        Transitions them to EXPIRED.
        """
        now = time.time()
        stale_sources: List[MediaSource] = []

        with self._lock:
            for s in self._sources.values():
                if s.connection_state in (SourceState.ACTIVE, SourceState.CONNECTING, SourceState.DEGRADED):
                    if (now - s.last_seen_at) > timeout_sec:
                        stale_sources.append(s)

            for s in stale_sources:
                self.sm.transition(s, SourceState.EXPIRED, reason=f"Heartbeat timed out after {timeout_sec}s")

        return stale_sources


_GLOBAL_SOURCE_REGISTRY: Optional[MediaSourceRegistry] = None


def get_source_registry() -> MediaSourceRegistry:
    """Singleton getter for MediaSourceRegistry."""
    global _GLOBAL_SOURCE_REGISTRY
    if _GLOBAL_SOURCE_REGISTRY is None:
        _GLOBAL_SOURCE_REGISTRY = MediaSourceRegistry()
    return _GLOBAL_SOURCE_REGISTRY
