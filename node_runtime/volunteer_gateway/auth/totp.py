"""
AWARESPAN — Volunteer Gateway TOTP Authentication
Pure-Python RFC 6238 compliant TOTP generator, verifier, and brute-force rate limiter.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from shared.logging.logger import get_logger

log = get_logger("volunteer_gateway.auth.totp")


def _generate_secret(length: int = 20) -> str:
    """Generate a random base32 TOTP secret."""
    raw = secrets.token_bytes(length)
    return base64.b32encode(raw).decode("utf-8").replace("=", "")


def _get_hotp(secret_base32: str, counter: int) -> str:
    """Compute HMAC-based One-Time Password for counter."""
    # Ensure proper base32 padding
    padding = (8 - len(secret_base32) % 8) % 8
    key = base64.b32decode(secret_base32.upper() + "=" * padding)
    msg = struct.pack(">Q", counter)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    code = (struct.unpack(">I", h[offset : offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"


def generate_totp_code(secret_base32: str, for_time: Optional[float] = None) -> str:
    """Generate 6-digit TOTP code for current or specified unix timestamp."""
    t = for_time if for_time is not None else time.time()
    counter = int(t // 30)
    return _get_hotp(secret_base32, counter)


def verify_totp_code(secret_base32: str, code: str, window: int = 1) -> bool:
    """
    Verify 6-digit TOTP code against secret.
    window=1 checks +/- 30 seconds clock drift (3 total time steps).
    """
    cleaned = code.strip().replace(" ", "")
    if len(cleaned) != 6 or not cleaned.isdigit():
        return False

    current_counter = int(time.time() // 30)
    for offset in range(-window, window + 1):
        if _get_hotp(secret_base32, current_counter + offset) == cleaned:
            return True
    return False


@dataclass
class RateLimitRecord:
    attempts: int
    locked_until: float
    last_attempt: float


class TOTPAuthManager:
    """Manages server-side TOTP secret provisioning, verification, and rate limiting."""

    def __init__(
        self,
        secret_file: Optional[Path] = None,
        max_attempts: int = 5,
        lockout_duration_sec: float = 300.0,
        window: int = 1,
        max_failed_attempts: Optional[int] = None,
        lockout_window_sec: Optional[float] = None,
    ):
        self.secret_file = secret_file or Path("state") / "totp_secret.json"
        self.max_attempts = max_failed_attempts if max_failed_attempts is not None else max_attempts
        self.lockout_duration = lockout_window_sec if lockout_window_sec is not None else lockout_duration_sec
        self.window = window
        self._secret: Optional[str] = None
        self._rate_limits: Dict[str, RateLimitRecord] = {}
        self._load_or_create_secret()

    def get_current_token(self) -> Tuple[str, float]:
        """Generate current 6-digit TOTP token and seconds remaining in time window."""
        code = generate_totp_code(self.secret)
        remaining = 30.0 - (time.time() % 30)
        return code, remaining

    def verify_token(self, code: str, client_ip: str = "127.0.0.1") -> bool:
        """Convenience method returning boolean verification result."""
        success, _ = self.verify_attempt(client_ip, code)
        return success

    def _load_or_create_secret(self) -> None:
        """Load persistent secret or initialize a fresh one."""
        self.secret_file.parent.mkdir(parents=True, exist_ok=True)
        if self.secret_file.exists():
            try:
                with open(self.secret_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._secret = data.get("totp_secret")
                log.info("Loaded operator TOTP secret from %s", self.secret_file)
                return
            except Exception as exc:
                log.warning("Could not read TOTP secret file: %s; generating new", exc)

        # Generate new secret
        self._secret = _generate_secret()
        try:
            with open(self.secret_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "totp_secret": self._secret,
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "issuer": "AWARESPAN",
                    },
                    f,
                    indent=2,
                )
            os.chmod(self.secret_file, 0o600)
            log.info("Provisioned new operator TOTP secret at %s", self.secret_file)
        except Exception as exc:
            log.error("Failed to persist TOTP secret: %s", exc)

    @property
    def secret(self) -> str:
        return self._secret or ""

    def get_provisioning_uri(self, account_name: str = "Operator", issuer: str = "AWARESPAN") -> str:
        """Format standard otpauth:// URI for QR code / authenticator import."""
        return f"otpauth://totp/{issuer}:{account_name}?secret={self.secret}&issuer={issuer}&algorithm=SHA1&digits=6&period=30"

    def is_rate_limited(self, client_ip: str) -> Tuple[bool, float]:
        """Check if client IP is currently locked out. Returns (is_locked, remaining_seconds)."""
        rec = self._rate_limits.get(client_ip)
        if not rec:
            return False, 0.0

        now = time.time()
        if now < rec.locked_until:
            return True, rec.locked_until - now

        # Lockout expired
        if rec.attempts >= self.max_attempts:
            rec.attempts = 0
            rec.locked_until = 0.0

        return False, 0.0

    def verify_attempt(self, client_ip: str, code: str) -> Tuple[bool, str]:
        """
        Verify TOTP code with rate limiting.
        Returns (success: bool, message: str).
        """
        is_locked, remaining = self.is_rate_limited(client_ip)
        if is_locked:
            return False, f"Too many failed attempts. Locked out for {int(remaining)}s."

        now = time.time()
        rec = self._rate_limits.setdefault(client_ip, RateLimitRecord(0, 0.0, now))
        rec.last_attempt = now

        success = verify_totp_code(self.secret, code, window=self.window)
        if success:
            rec.attempts = 0
            rec.locked_until = 0.0
            log.info("Successful TOTP operator verification from %s", client_ip)
            return True, "Authentication successful"
        else:
            rec.attempts += 1
            if rec.attempts >= self.max_attempts:
                rec.locked_until = now + self.lockout_duration
                log.warning("Client %s reached max failed TOTP attempts; locked for %ds", client_ip, int(self.lockout_duration))
                return False, f"Invalid code. Max attempts reached; locked out for {int(self.lockout_duration)}s."
            remaining_attempts = self.max_attempts - rec.attempts
            log.warning("Failed TOTP code from %s (%d attempts remaining)", client_ip, remaining_attempts)
            return False, f"Invalid code. {remaining_attempts} attempts remaining."
