"""
AWARESPAN — Centralized Logging and Credential Sanitization
Ensures sensitive tokens, passwords, and device secrets are never emitted in plaintext.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import logging
import os
import re
from pathlib import Path
from typing import Optional, Set

from shared.config.settings import get_settings


# Regular expression to catch Telegram bot tokens: e.g. 1234567890:AAH40-Xw4...
TELEGRAM_TOKEN_REGEX = re.compile(r"\b\d{8,11}:[A-Za-z0-9_-]{35,}\b")


def get_known_secrets() -> Set[str]:
    """Gather all configured secret strings that must be redacted."""
    secrets = set()
    try:
        settings = get_settings()
        if settings.bot_token and len(settings.bot_token) > 5:
            secrets.add(settings.bot_token)
        if settings.device_secret and len(settings.device_secret) > 3 and settings.device_secret != "changeme":
            secrets.add(settings.device_secret)
        if settings.backend_api_key and len(settings.backend_api_key) > 5:
            secrets.add(settings.backend_api_key)
        if settings.mqtt_password and len(settings.mqtt_password) > 3:
            secrets.add(settings.mqtt_password)
        if getattr(settings, "totp_secret", "") and len(settings.totp_secret) > 3:
            secrets.add(settings.totp_secret)
        if getattr(settings, "turn_password", "") and len(settings.turn_password) > 3:
            secrets.add(settings.turn_password)
    except Exception:
        pass

    # Also check common environment variables
    for env_var in ("BOT_TOKEN", "PI_DEVICE_SECRET", "BACKEND_API_KEY", "MQTT_PASSWORD", "SSH_PASSWORD", "TOTP_SECRET", "TURN_PASSWORD"):
        val = os.getenv(env_var)
        if val and len(val.strip()) > 3 and val.strip() != "changeme":
            secrets.add(val.strip())

    return secrets


def sanitize_text(text: str) -> str:
    """Sanitize a string, masking any known secrets or token patterns."""
    if not isinstance(text, str):
        text = str(text)

    # Redact regex-matched bot tokens
    sanitized = TELEGRAM_TOKEN_REGEX.sub("[REDACTED_BOT_TOKEN]", text)

    # Redact known secrets
    for secret in get_known_secrets():
        if secret in sanitized:
            sanitized = sanitized.replace(secret, "[REDACTED_SECRET]")

    return sanitized


class CredentialFilter(logging.Filter):
    """Logging filter that scrubs sensitive credentials from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: sanitize_text(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(sanitize_text(v) if isinstance(v, str) else v for v in record.args)
        return True


def get_logger(name: str, log_to_file: bool = False, file_name: Optional[str] = None) -> logging.Logger:
    """
    Get a pre-configured logger with credential filtering and standard formatting.
    """
    logger = logging.getLogger(name)

    # Avoid adding multiple duplicate handlers
    if logger.handlers:
        return logger

    settings = get_settings()
    level_name = getattr(logging, settings.log_level, logging.INFO)
    logger.setLevel(level_name)

    # Formatter: [2026-11-12 12:00:00] [INFO] [node_runtime] message
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    credential_filter = CredentialFilter()

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level_name)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(credential_filter)
    logger.addHandler(console_handler)

    # Optional File Handler
    if log_to_file:
        try:
            log_dir = Path(settings.log_dir)
            if not log_dir.exists():
                try:
                    log_dir.mkdir(parents=True, exist_ok=True)
                except OSError:
                    log_dir = settings.repo_root / "logs"
                    log_dir.mkdir(parents=True, exist_ok=True)

            log_file = log_dir / (file_name or f"{name}.log")
            file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
            file_handler.setLevel(level_name)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(credential_filter)
            logger.addHandler(file_handler)
        except Exception:
            pass

    return logger
