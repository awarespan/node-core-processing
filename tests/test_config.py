"""
Unit tests for AWARESPAN configuration and logging.
"""

import logging
from shared.config.settings import get_settings
from shared.logging.logger import sanitize_text, CredentialFilter


def test_settings_defaults():
    settings = get_settings()
    assert settings.node_id is not None
    assert settings.update_branch == "main"
    assert settings.update_check_interval > 0
    assert settings.ml_training_enabled is False


def test_credential_sanitizer():
    raw_token = "9876543210:AAH40-DummyTestTokenStringForSanitizerCheck123"
    text = f"Connecting to Telegram with token {raw_token} now."
    sanitized = sanitize_text(text)
    assert raw_token not in sanitized
    assert "[REDACTED_BOT_TOKEN]" in sanitized


def test_logger_filter():
    logger = logging.getLogger("test_logger")
    cred_filter = CredentialFilter()
    record = logging.LogRecord("test", logging.INFO, "test.py", 1, "Token 9876543210:AAH40-DummyTestTokenStringForSanitizerCheck123 failed", (), None)
    cred_filter.filter(record)
    assert "9876543210:" not in record.msg
    assert "[REDACTED_BOT_TOKEN]" in record.msg
