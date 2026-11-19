# Test suites

Use the canonical runner from the repository root:

```bash
./scripts/test.sh setup  # setup wizard option matrix and install-plan checks
./scripts/test.sh unit   # application/unit tests, excluding setup smoke tests
./scripts/test.sh all    # everything (default)
./scripts/test.sh list   # collect/list tests without running them
```

The `setup` suite lives in `tests/setup/` and is marked `pytest.mark.setup`.
It uses isolated temporary directories and mocked host package-manager / pip
commands; it does not install packages, change system services or touch the
operator's real `.venv`. It verifies the four Linux combinations of ML training
and production connectivity, Pi runtime-only selection, invalid option guards,
secret preflight, custom config paths, Python-version rejection/replacement,
and exact dependency pins.

The application tests remain directly under `tests/`. All tests can also be
run with `.venv/bin/python -m pytest -q`, but the wrapper is preferred because
it verifies that the selected interpreter is CPython 3.11.
