"""
AWARESPAN — Tests for TOTP Secret Provisioning & Authenticator Onboarding
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from shared.config.settings import get_settings
from shared.logging.logger import get_known_secrets, sanitize_text
from node_runtime.volunteer_gateway.auth.totp import (
    TOTPAuthManager,
    generate_totp_code,
    verify_totp_code,
)


def test_totp_generation_and_verification():
    secret = "JBSWY3DPEHPK3PXP"  # standard RFC test secret
    code = generate_totp_code(secret)
    assert len(code) == 6
    assert code.isdigit()
    assert verify_totp_code(secret, code, window=1) is True
    assert verify_totp_code(secret, "000000" if code != "000000" else "111111", window=1) is False


def test_totp_auth_manager_precedence_and_file_fallback(tmp_path):
    secret_file = tmp_path / "totp_secret.json"
    mgr = TOTPAuthManager(secret_file=secret_file)
    assert mgr.is_enrolled() is True
    assert len(mgr.secret) >= 16

    # Verify secret is saved to file with secure permissions
    assert secret_file.exists()
    mode = oct(os.stat(secret_file).st_mode & 0o777)
    assert mode == "0o600"

    # Reload from file
    mgr2 = TOTPAuthManager(secret_file=secret_file)
    assert mgr2.secret == mgr.secret


def test_totp_rate_limiting(tmp_path):
    secret_file = tmp_path / "totp_secret.json"
    mgr = TOTPAuthManager(secret_file=secret_file, max_attempts=3, lockout_duration_sec=60.0)

    # 3 failed attempts
    for _ in range(3):
        success, msg = mgr.verify_attempt("10.0.0.99", "000000")
        assert success is False

    # 4th attempt should be blocked by rate limiter
    is_locked, remaining = mgr.is_rate_limited("10.0.0.99")
    assert is_locked is True
    assert remaining > 0

    success, msg = mgr.verify_attempt("10.0.0.99", "000000")
    assert success is False
    assert "Too many failed attempts" in msg or "Locked out" in msg


def test_totp_secret_rotation(tmp_path):
    secret_file = tmp_path / "totp_secret.json"
    mgr = TOTPAuthManager(secret_file=secret_file)
    initial_secret = mgr.secret

    new_secret = mgr.rotate_secret()
    assert new_secret != initial_secret
    assert mgr.secret == new_secret


def test_totp_secret_sanitization():
    settings = get_settings()
    original_secret = getattr(settings, "totp_secret", "")
    try:
        test_sec = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"
        settings.totp_secret = test_sec
        known = get_known_secrets()
        assert test_sec in known

        logged_line = f"Operator secret is {test_sec} in environment."
        sanitized = sanitize_text(logged_line)
        assert test_sec not in sanitized
        assert "[REDACTED_SECRET]" in sanitized
    finally:
        settings.totp_secret = original_secret


def test_provision_cli_tool(tmp_path):
    env_file = tmp_path / "test.env"
    env_file.write_text("BACKEND_API_URL=https://api.example.com\n", encoding="utf-8")

    # 1. Test --sync-env
    cmd = [sys.executable, "scripts/provision_totp.py", "--sync-env", str(env_file)]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert "Successfully synced TOTP_SECRET" in res.stdout
    assert env_file.exists()

    env_content = env_file.read_text(encoding="utf-8")
    assert "TOTP_SECRET=" in env_content
    mode = oct(os.stat(env_file).st_mode & 0o777)
    assert mode == "0o600"

    # 2. Test --code
    cmd_code = [sys.executable, "scripts/provision_totp.py", "--code"]
    res_code = subprocess.run(cmd_code, capture_output=True, text=True, check=True)
    code = res_code.stdout.strip()
    assert len(code) == 6
    assert code.isdigit()

    # 3. Test --verify with the code
    cmd_verify = [sys.executable, "scripts/provision_totp.py", "--verify", code]
    res_verify = subprocess.run(cmd_verify, capture_output=True, text=True, check=True)
    assert "SUCCESS" in res_verify.stdout
