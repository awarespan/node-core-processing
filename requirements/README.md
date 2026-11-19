# Python dependency management

AWARESPAN's supported interpreter baseline is **CPython 3.11 or 3.12 or 3.12** (`.python-version`).
The dependency manifests are intentionally exact-pinned: package upgrades are
reviewed changes, not something pip should choose during setup.

## Manifest layout

| File | Purpose |
|---|---|
| `bootstrap.txt` | Exact pip, setuptools and wheel versions used by the installer |
| `torch-cpu.txt` | Exact CPU-only PyTorch and torchvision pair; install from the official PyTorch CPU wheel index |
| `runtime.txt` | Exact runtime, inference, communications and configuration packages |
| `dev.txt` | Runtime plus exact test and lint dependencies |
| `training.txt` | Runtime plus exact dataset/training integrations |
| `ultralytics.txt` | Exact Ultralytics version, installed separately with `--no-deps` to avoid its GUI OpenCV dependency |
| `constraints-py311.txt` | Exact constraints for shared transitive dependencies, including platform markers where needed |

All active dependency files use `==` pins. Across the runtime, development,
training, inference and shared transitive manifests, the current baseline pins
58 exact package-version pins: 55 application/runtime packages plus the three installer tools (`pip`, `setuptools` and `wheel`). The dependency metadata for the selected package
versions was audited for CPython 3.11 or 3.12 or 3.12 on Linux x86-64 and ARM64; every declared dependency
is pinned or has an explicit platform-specific reason for exclusion. The
constraints file ensures that transitive dependencies resolved by pip do not
drift independently of the reviewed baseline. The PyTorch pair is installed first from
`https://download.pytorch.org/whl/cpu`; the remaining dependencies are resolved
from PyPI with `--only-binary=:all:`. This deliberately fails when a compatible
wheel is unavailable rather than silently invoking a source build.

Two upstream metadata differences are intentional: the PyTorch CPU index serves
the CPU build (not the CUDA-enabled PyPI wheel and its NVIDIA packages), and
Ultralytics declares `opencv-python` while this project intentionally supplies
`opencv-python-headless==4.10.0.84`. Ultralytics is therefore installed with
`--no-deps` after its other required dependencies have been explicitly pinned.
Do not install both OpenCV distributions in the same environment.

## Installation order

The canonical installer is `./scripts/setup.sh`. For a manual workstation
training install, use this exact sequence from the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade --only-binary=:all: -c requirements/constraints-py311.txt -r requirements/bootstrap.txt
python -m pip install --only-binary=:all: --index-url https://download.pytorch.org/whl/cpu -c requirements/constraints-py311.txt -r requirements/torch-cpu.txt
python -m pip install --only-binary=:all: -r requirements/training.txt
python -m pip install --only-binary=:all: --no-deps -r requirements/ultralytics.txt
```

For a production Pi, the setup wizard selects runtime-only requirements and
does not install developer or training packages.

## Updating a dependency

1. Change the exact version in the appropriate manifest.
2. Update any affected transitive pin in `constraints-py311.txt`.
3. Run the setup smoke suite and full suite: `./scripts/test.sh setup` and
   `./scripts/test.sh all`.
4. Run pip's wheel-only resolver against the runtime, development and training
   manifests on CPython 3.11 or 3.12 or 3.12. Do not merge if it needs a source build or reports
   a resolution conflict.
5. Record the package upgrade in the commit message and this manifest if the
   supported interpreter/platform assumptions changed.

Do not use open-ended ranges (`>=`, `~=`, etc.) in the active dependency files. Host RPM/DEB packages remain managed by the selected Linux distribution; the exact pins here cover the Python environment.
