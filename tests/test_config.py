"""
Unit tests for AWARESPAN configuration and logging.
"""

import logging
from shared.config.settings import get_settings
from shared.config import settings as settings_module
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


def test_repository_root_env_precedes_legacy_config_paths(tmp_path, monkeypatch):
    canonical = tmp_path / ".env"
    canonical.write_text("PI_NODE_ID=canonical\n")
    monkeypatch.setattr(settings_module, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("AWARESPAN_ENV_FILE", "")
    assert settings_module.find_canonical_env() == canonical.resolve()


def test_explicit_env_file_overrides_repository_root_env(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("PI_NODE_ID=canonical\n")
    explicit = tmp_path / "custom.env"
    explicit.write_text("PI_NODE_ID=explicit\n")
    monkeypatch.setattr(settings_module, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("AWARESPAN_ENV_FILE", str(explicit))
    assert settings_module.find_canonical_env() == explicit.resolve()
