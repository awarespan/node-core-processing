#!/usr/bin/env bash
# Repeatable test-suite entrypoint for AWARESPAN.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${AWARESPAN_TEST_PYTHON:-$ROOT/.venv/bin/python}"
SUITE="${1:-all}"

if [[ ! -x "$PYTHON" ]]; then
  echo "Python environment not found: $PYTHON" >&2
  echo "Run ./scripts/setup.sh first, then ./scripts/test.sh setup" >&2
  exit 2
fi

PYTHON_MINOR="$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if [[ "$PYTHON_MINOR" != "3.11" ]]; then
  echo "AWARESPAN tests require CPython 3.11; found $PYTHON_MINOR at $PYTHON" >&2
  exit 2
fi

case "$SUITE" in
  setup)
    exec "$PYTHON" -m pytest -q -m setup "$ROOT/tests/setup"
    ;;
  unit)
    exec "$PYTHON" -m pytest -q -m 'not setup' "$ROOT/tests"
    ;;
  all)
    exec "$PYTHON" -m pytest -q "$ROOT/tests"
    ;;
  list)
    exec "$PYTHON" -m pytest --collect-only -q "$ROOT/tests"
    ;;
  -h|--help|help)
    cat <<'USAGE'
AWARESPAN test runner

Usage: ./scripts/test.sh [suite]

Suites:
  setup   Setup wizard and dependency-selection smoke tests only
  unit    All tests except the setup smoke suite
  all     Entire test suite (default)
  list    List collected tests without executing them

The runner uses .venv/bin/python by default and requires CPython 3.11.
Override the interpreter with AWARESPAN_TEST_PYTHON=/path/to/python.
USAGE
    ;;
  *)
    echo "Unknown test suite: $SUITE" >&2
    echo "Use: ./scripts/test.sh {setup|unit|all|list}" >&2
    exit 2
    ;;
esac
