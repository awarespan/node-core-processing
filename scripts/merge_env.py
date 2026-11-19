#!/usr/bin/env python3
"""Rebuild the private root .env in .env.example order while preserving values."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values


ASSIGNMENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")
SAFE_UNQUOTED = re.compile(r"^[A-Za-z0-9_./:@,+-]+$")


def format_value(value: Optional[str]) -> str:
    """Render a dotenv-compatible value without losing spaces or special chars."""
    if value is None or value == "":
        return ""
    value = str(value)
    if SAFE_UNQUOTED.fullmatch(value):
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def merge_env(env_path: Path, template_path: Path) -> None:
    """Use template comments/order but keep existing values and custom keys."""
    existing = dotenv_values(env_path, interpolate=False) if env_path.is_file() else {}
    template_values = dotenv_values(template_path, interpolate=False)
    output = []
    known = set()

    for line in template_path.read_text().splitlines():
        match = ASSIGNMENT.match(line)
        if not match:
            output.append(line)
            continue
        key = match.group(1)
        known.add(key)
        value = existing[key] if key in existing else template_values.get(key)
        output.append(f"{key}={format_value(value)}")

    extras = [(key, value) for key, value in existing.items()
              if key not in known and value is not None]
    if extras:
        output.extend([
            "",
            "# =============================================================================",
            "# CUSTOM / LEGACY SETTINGS — preserved during configuration migration",
            "# Review these values before removing them; active keys are grouped above.",
            "# =============================================================================",
        ])
        output.extend(f"{key}={format_value(value)}" for key, value in extras)

    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(output) + "\n")
    env_path.chmod(0o600)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else root / ".env"
    template_path = root / ".env.example"
    if not template_path.is_file():
        print(f"Configuration template not found: {template_path}", file=sys.stderr)
        return 2
    merge_env(env_path, template_path)
    print(f"Normalised shared AWARESPAN configuration: {env_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
