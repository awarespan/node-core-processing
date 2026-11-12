"""
AWARESPAN — Volunteer Session Manager
Issues single-use pairing credentials, enforces capability scopes, and manages volunteer lifecycles.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union

from shared.logging.logger import get_logger

log = get_logger("volunteer_gateway.sessions")


class PairingScope(str, Enum):
    CAMERA_ONLY = "camera"
    MIC_ONLY = "microphone"
    BOTH = "both"


@dataclass
class VolunteerSession:
    """Represents an active volunteer device session."""
    session_id: str
    source_id: str
    client_ip: str
    granted_capabilities: Set[str]        # {"camera", "microphone"}
    created_at: float = field(default_factory=time.time)
    last_seen_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    device_info: str = ""
    is_active: bool = True

    @property
    def can_camera(self) -> bool:
        return "camera" in self.granted_capabilities

    @property
    def can_microphone(self) -> bool:
        return "microphone" in self.granted_capabilities

    @property
    def device_name(self) -> str:
        return self.device_info

    def to_dict(self) -> Dict:
        return {
            "session_id": self.session_id,
            "source_id": self.source_id,
            "client_ip": self.client_ip,
            "granted_capabilities": list(self.granted_capabilities),
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "expires_at": self.expires_at,
            "device_info": self.device_info,
            "is_active": self.is_active,
        }


@dataclass
class PairingToken:
    """Short-lived, single-use token issued after operator TOTP verification."""
    token: str
    granted_capabilities: Set[str]        # {"camera", "microphone"}
    created_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    used: bool = False


class VolunteerSessionManager:
    """Manages volunteer pairing tokens and active session quotas."""

    def __init__(
        self,
        max_sessions: int = 5,
        max_cameras: int = 2,
        max_microphones: int = 2,
        pairing_timeout_sec: float = 300.0,
        session_timeout_sec: float = 3600.0,
    ):
        self.max_sessions = max_sessions
        self.max_cameras = max_cameras
        self.max_microphones = max_microphones
        self.pairing_timeout = pairing_timeout_sec
        self.session_timeout = session_timeout_sec

        self._pairing_tokens: Dict[str, PairingToken] = {}
        self._active_sessions: Dict[str, VolunteerSession] = {}

    def issue_pairing_token(self, capabilities: Union[Set[str], List[str], str]) -> Tuple[bool, str, str]:
        """
        Issue a single-use pairing token for a volunteer device.
        Returns (success: bool, token_or_err: str, message: str).
        """
        if isinstance(capabilities, str):
            if capabilities == "both":
                caps = {"camera", "microphone"}
            else:
                caps = {capabilities}
        else:
            caps = set(capabilities)

        # Quota check
        if len(self._active_sessions) >= self.max_sessions:
            return False, "", f"Maximum concurrent sessions ({self.max_sessions}) reached."

        token = secrets.token_urlsafe(24)
        expires = time.time() + self.pairing_timeout
        self._pairing_tokens[token] = PairingToken(
            token=token,
            granted_capabilities=caps,
            created_at=time.time(),
            expires_at=expires,
            used=False,
        )
        log.info("Issued pairing token %s... (caps: %s, expires in %ds)", token[:8], caps, int(self.pairing_timeout))
        return True, token, f"Token valid for {int(self.pairing_timeout)} seconds"

    def create_pairing_token(self, client_ip: str, scope: Union[PairingScope, str] = PairingScope.BOTH) -> str:
        """Helper creating pairing token directly."""
        scope_str = scope.value if isinstance(scope, PairingScope) else str(scope)
        if scope_str == "camera":
            caps = {"camera"}
        elif scope_str == "microphone":
            caps = {"microphone"}
        else:
            caps = {"camera", "microphone"}

        ok, token, msg = self.issue_pairing_token(caps)
        if not ok:
            raise RuntimeError(msg)
        return token

    def redeem_pairing_token(
        self,
        token: str,
        client_ip: str,
        device_info: str = "",
        device_name: Optional[str] = None,
    ) -> Tuple[bool, Optional[VolunteerSession], str]:
        """
        Redeem a single-use pairing token to establish an active session.
        """
        now = time.time()
        pt = self._pairing_tokens.get(token)

        if not pt:
            return False, None, "Invalid pairing token."
        if pt.used:
            return False, None, "Pairing token has already been redeemed."
        if now > pt.expires_at:
            del self._pairing_tokens[token]
            return False, None, "Pairing token has expired."

        # Check resource quotas
        current_cameras = sum(1 for s in self._active_sessions.values() if "camera" in s.granted_capabilities and s.is_active)
        current_mics = sum(1 for s in self._active_sessions.values() if "microphone" in s.granted_capabilities and s.is_active)

        if "camera" in pt.granted_capabilities and current_cameras >= self.max_cameras:
            return False, None, f"Max concurrent cameras ({self.max_cameras}) reached."
        if "microphone" in pt.granted_capabilities and current_mics >= self.max_microphones:
            return False, None, f"Max concurrent microphones ({self.max_microphones}) reached."

        # Mark single-use token as used
        pt.used = True

        session_id = f"volsess-{secrets.token_hex(6)}"
        source_id = f"vol-{client_ip.replace('.', '-')}-{secrets.token_hex(3)}"
        effective_device_info = device_name or device_info

        session = VolunteerSession(
            session_id=session_id,
            source_id=source_id,
            client_ip=client_ip,
            granted_capabilities=pt.granted_capabilities,
            created_at=now,
            last_seen_at=now,
            expires_at=now + self.session_timeout,
            device_info=effective_device_info,
            is_active=True,
        )

        self._active_sessions[session_id] = session
        log.info("Redeemed pairing token; established session %s for source %s", session_id, source_id)
        return True, session, "Session established"

    def create_direct_session(
        self,
        client_ip: str,
        capabilities: Union[Set[str], List[str], str],
        device_info: str = "",
    ) -> Tuple[bool, Optional[VolunteerSession], str]:
        """Directly create an active session after operator TOTP verification."""
        if isinstance(capabilities, str):
            if capabilities == "both":
                caps = {"camera", "microphone"}
            else:
                caps = {capabilities}
        else:
            caps = set(capabilities)

        if len(self._active_sessions) >= self.max_sessions:
            return False, None, f"Maximum concurrent sessions ({self.max_sessions}) reached."

        current_cameras = sum(1 for s in self._active_sessions.values() if "camera" in s.granted_capabilities and s.is_active)
        current_mics = sum(1 for s in self._active_sessions.values() if "microphone" in s.granted_capabilities and s.is_active)

        if "camera" in caps and current_cameras >= self.max_cameras:
            return False, None, f"Max concurrent cameras ({self.max_cameras}) reached."
        if "microphone" in caps and current_mics >= self.max_microphones:
            return False, None, f"Max concurrent microphones ({self.max_microphones}) reached."

        now = time.time()
        session_id = f"volsess-{secrets.token_hex(6)}"
        source_id = f"vol-{client_ip.replace('.', '-')}-{secrets.token_hex(3)}"

        session = VolunteerSession(
            session_id=session_id,
            source_id=source_id,
            client_ip=client_ip,
            granted_capabilities=caps,
            created_at=now,
            last_seen_at=now,
            expires_at=now + self.session_timeout,
            device_info=device_info,
            is_active=True,
        )

        self._active_sessions[session_id] = session
        log.info("Directly established volunteer session %s for source %s", session_id, source_id)
        return True, session, "Session established"

    def record_activity(self, session_id: str) -> None:
        """Update last seen timestamp for active session."""
        sess = self._active_sessions.get(session_id)
        if sess:
            sess.last_seen_at = time.time()

    def revoke_session(self, session_id: str, reason: str = "") -> bool:
        """Alias for terminate_session."""
        return self.terminate_session(session_id)

    def get_session(self, session_id: str) -> Optional[VolunteerSession]:
        return self._active_sessions.get(session_id)

    def terminate_session(self, session_id: str) -> bool:
        sess = self._active_sessions.pop(session_id, None)
        if sess:
            sess.is_active = False
            log.info("Terminated session %s", session_id)
            return True
        return False

    def list_active_sessions(self) -> List[VolunteerSession]:
        now = time.time()
        # Clean expired
        expired = [sid for sid, s in self._active_sessions.items() if now > s.expires_at]
        for sid in expired:
            self.terminate_session(sid)
        return list(self._active_sessions.values())
