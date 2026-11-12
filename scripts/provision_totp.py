#!/usr/bin/env python3
"""
AWARESPAN — Operator TOTP Provisioning & Authenticator Onboarding Utility
Safely provisions, verifies, syncs, and displays RFC 6238 TOTP onboarding credentials.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared.config.settings import CANONICAL_ENV_PATH, find_canonical_env, get_settings
from shared.logging.logger import get_logger
from node_runtime.volunteer_gateway.auth.totp import TOTPAuthManager, verify_totp_code

log = get_logger("provision_totp")


def render_ascii_qr(uri: str) -> None:
    """Render terminal-friendly ASCII QR code."""
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=2,
        )
        qr.add_data(uri)
        qr.make(fit=True)
        print("\nScan this QR code with Google Authenticator, Microsoft Authenticator, or 1Password:\n")
        qr.print_ascii(invert=True)
    except ImportError:
        print("\n[Note: 'qrcode' package not installed. Install with 'pip install qrcode' for terminal QR rendering.]")
        print("You can manually import the provisioning URI below:")


def get_auth_manager() -> TOTPAuthManager:
    settings = get_settings()
    secret_file = Path(getattr(settings, "totp_secret_file", "/var/lib/awarespan/totp_secret.json"))
    return TOTPAuthManager(secret_file=secret_file)


def show_status(auth_mgr: TOTPAuthManager):
    settings = get_settings()
    enrolled = auth_mgr.is_enrolled()
    code, remaining = auth_mgr.get_current_token() if enrolled else ("", 0.0)

    # Determine secret source
    env_secret = getattr(settings, "totp_secret", "").strip()
    source_label = "Environment variable (TOTP_SECRET)" if env_secret else f"File ({auth_mgr.secret_file})"

    print("\n=======================================================")
    print("  AWARESPAN — OPERATOR TOTP AUTHENTICATION STATUS")
    print("=======================================================")
    print(f"Status:             {'[ENROLLED & ACTIVE]' if enrolled else '[UNENROLLED]'}")
    print(f"Secret Source:      {source_label}")
    print(f"Issuer:             {getattr(settings, 'totp_issuer', 'AWARESPAN')}")
    print(f"Account:            {getattr(settings, 'totp_account_name', 'operator')} ({settings.node_id})")
    print(f"Clock Window:       +/- {getattr(settings, 'totp_window', 1) * 30}s tolerance")
    if enrolled:
        print(f"Current Code:       \033[1;32m{code}\033[0m (valid for {remaining:.0f}s)")
        print(f"Secret Storage:     Securely stored with 0600 permissions (Value Redacted)")
    else:
        print("Run 'python3 scripts/provision_totp.py --qr' to initiate onboarding.")
    print("=======================================================\n")


def show_uri(auth_mgr: TOTPAuthManager):
    settings = get_settings()
    uri = auth_mgr.get_provisioning_uri(
        account_name=f"{getattr(settings, 'totp_account_name', 'operator')}@{settings.node_id}",
        issuer=getattr(settings, "totp_issuer", "AWARESPAN"),
    )
    print("\n=======================================================")
    print("  AWARESPAN — TOTP PROVISIONING URI")
    print("=======================================================")
    print(f"URI: {uri}")
    print("\nCopy and paste this URI into your authenticator app.")
    print("=======================================================\n")


def show_qr(auth_mgr: TOTPAuthManager):
    settings = get_settings()
    uri = auth_mgr.get_provisioning_uri(
        account_name=f"{getattr(settings, 'totp_account_name', 'operator')}@{settings.node_id}",
        issuer=getattr(settings, "totp_issuer", "AWARESPAN"),
    )
    print("\n=======================================================")
    print("  AWARESPAN — OPERATOR AUTHENTICATOR ONBOARDING")
    print("=======================================================")
    render_ascii_qr(uri)
    print(f"Provisioning URI: {uri}")
    print("\nAfter scanning, verify your enrollment with:")
    print("  python3 scripts/provision_totp.py --verify <6-digit-code>")
    print("=======================================================\n")


def verify_code(auth_mgr: TOTPAuthManager, code: str):
    # Strip any ANSI escape sequences or non-digit characters
    code_clean = re.sub(r"[^\d]", "", code.strip())
    success, msg = auth_mgr.verify_attempt("127.0.0.1", code_clean)
    print("\n=======================================================")
    print("  AWARESPAN — TOTP CODE VERIFICATION TEST")
    print("=======================================================")
    if success:
        print(f"\033[1;32m[✓] SUCCESS: Code '{code_clean}' verified successfully!\033[0m")
        print("Your authenticator is correctly registered and synchronized.")
    else:
        print(f"\033[1;31m[✗] FAILED: {msg}\033[0m")
        print("Ensure device time is synchronized (NTP) and code is current.")
    print("=======================================================\n")
    return success


def sync_to_env(auth_mgr: TOTPAuthManager, target_env: Optional[str] = None):
    """
    Populates TOTP_SECRET into the canonical .env or specified file safely.
    Ensures 0600 file permissions and never leaks secret in logs.
    """
    secret = auth_mgr.secret
    if not secret:
        print("[!] Error: No active TOTP secret found to sync.")
        sys.exit(1)

    env_path = Path(target_env) if target_env else (find_canonical_env() or Path(".env"))
    env_path = env_path.resolve()

    print(f"[*] Syncing TOTP_SECRET to: {env_path}")
    existing_lines = []
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            existing_lines = f.readlines()

    updated = False
    new_lines = []
    for line in existing_lines:
        if re.match(r"^\s*TOTP_SECRET\s*=", line):
            new_lines.append(f"TOTP_SECRET={secret}\n")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append("\n# Operator Volunteer TOTP Secret (RFC 6238)\n")
        new_lines.append(f"TOTP_SECRET={secret}\n")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    os.chmod(env_path, 0o600)

    print(f"\033[1;32m[✓] Successfully synced TOTP_SECRET into {env_path} (mode 0600).\033[0m")


def rotate_secret(auth_mgr: TOTPAuthManager):
    print("\n=======================================================")
    print("  AWARESPAN — OPERATOR TOTP SECRET ROTATION")
    print("=======================================================")
    print("[WARNING] Rotating the secret invalidates all currently enrolled")
    print("authenticators and active volunteer sessions.")
    confirm = input("Type 'ROTATE' to confirm secret rotation: ").strip()
    if confirm != "ROTATE":
        print("Rotation canceled.")
        return

    new_sec = auth_mgr.rotate_secret()
    print("\033[1;32m[✓] Generated and persisted new cryptographic TOTP secret.\033[0m")
    sync_to_env(auth_mgr)
    show_qr(auth_mgr)


def main():
    parser = argparse.ArgumentParser(description="AWARESPAN TOTP Provisioning & Onboarding Tool")
    parser.add_argument("--status", action="store_true", help="Display enrollment and active code status")
    parser.add_argument("--code", action="store_true", help="Print current 6-digit TOTP code only (clean digits)")
    parser.add_argument("--show-uri", action="store_true", help="Display otpauth:// provisioning URI")
    parser.add_argument("--qr", action="store_true", help="Render terminal ASCII QR code for authenticator scan")
    parser.add_argument("--verify", metavar="CODE", help="Verify a 6-digit TOTP code")
    parser.add_argument("--sync-env", nargs="?", const="", metavar="ENV_FILE", help="Sync secret into .env file")
    parser.add_argument("--rotate", action="store_true", help="Rotate operator secret")
    args = parser.parse_args()

    if args.code:
        import logging
        logging.getLogger().setLevel(logging.ERROR)
        log.setLevel(logging.ERROR)
        logging.getLogger("volunteer_gateway.auth.totp").setLevel(logging.ERROR)
        auth_mgr = get_auth_manager()
        code, _ = auth_mgr.get_current_token()
        print(code)
        return

    auth_mgr = get_auth_manager()

    if args.verify:
        success = verify_code(auth_mgr, args.verify)
        sys.exit(0 if success else 1)
    elif args.show_uri:
        show_uri(auth_mgr)
    elif args.qr:
        show_qr(auth_mgr)
    elif args.sync_env is not None:
        target = args.sync_env if args.sync_env != "" else None
        sync_to_env(auth_mgr, target)
    elif args.rotate:
        rotate_secret(auth_mgr)
    else:
        show_status(auth_mgr)


if __name__ == "__main__":
    main()
