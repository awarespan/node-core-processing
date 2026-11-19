"""Isolated smoke tests for setup option combinations (no host packages/services)."""
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.setup

ROOT = Path(__file__).resolve().parents[2]


def _run_setup(tmp_path, *options, api_key=None, profile="linux", python_minor="3.11", old_venv_minor=None):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    log = tmp_path / "install.log"
    bootstrap = fake_bin / "python3.11"
    old_python = tmp_path / "venv" / "bin" / "python"
    if old_venv_minor:
        old_python.parent.mkdir(parents=True)
        old_python.write_text(
            "#!/usr/bin/env bash\n"
            f"printf '%s\\n' '{old_venv_minor}'\n"
        )
        old_python.chmod(0o755)
    bootstrap.write_text(
        "#!/usr/bin/env bash\n"
        "if [[ \"${1:-}\" == -c ]]; then printf '%s\\n' \"${AWARESPAN_TEST_PY_MINOR:-3.11}\"; exit 0; fi\n"
        "if [[ \"${1:-}\" == -m && \"${2:-}\" == venv ]]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  cat >\"$3/bin/python\" <<'STUB'\n"
        "#!/usr/bin/env bash\n"
        f"REAL_PYTHON={sys.executable!r}\n"
        "if [[ \"${1:-}\" == -c ]]; then printf '%s\\n' \"${AWARESPAN_TEST_PY_MINOR:-3.11}\"; exit 0; fi\n"
        "if [[ \"${1:-}\" == -m && \"${2:-}\" == pip ]]; then printf '%s\\n' \"$*\" >>\"$AWARESPAN_TEST_INSTALL_LOG\"; exit 0; fi\n"
        "exec \"$REAL_PYTHON\" \"$@\"\n"
        "STUB\n"
        "  chmod +x \"$3/bin/python\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n"
    )
    (fake_bin / "dnf").write_text("#!/usr/bin/env bash\nprintf '%s\\n' \"$*\" >>\"$AWARESPAN_TEST_INSTALL_LOG.dnf\"\n")
    (fake_bin / "sudo").write_text("#!/usr/bin/env bash\nexec \"$@\"\n")
    for executable in fake_bin.iterdir():
        executable.chmod(0o755)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "PATH": f"{fake_bin}:{env['PATH']}",
        "AWARESPAN_VENV": str(tmp_path / "venv"),
        "AWARESPAN_TEST_INSTALL_LOG": str(log),
        "AWARESPAN_TEST_PY_MINOR": python_minor,
    })
    env.pop("BACKEND_API_KEY", None)
    if api_key:
        env["BACKEND_API_KEY"] = api_key
    result = subprocess.run(
        [str(ROOT / "scripts/setup.sh"), "--profile", profile, "--non-interactive", *options],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    return result, home, log


def _config_values(path):
    return dict(line.split("=", 1) for line in path.read_text().splitlines()
                if "=" in line and not line.startswith("#"))


def test_linux_setup_option_matrix(tmp_path):
    """Train and production are independent toggles; exercise all four combinations."""
    cases = [(False, False), (False, True), (True, False), (True, True)]
    for index, (train, production) in enumerate(cases):
        case_dir = tmp_path / str(index)
        case_dir.mkdir()
        options = ["--train" if train else "--no-train",
                   "--production" if production else "--no-production"]
        result, home, log = _run_setup(case_dir, *options,
                                       api_key="smoke-test-key" if production else None)
        assert result.returncode == 0, result.stdout + result.stderr
        install_lines = log.read_text().splitlines()
        bootstrap_install = next(i for i, line in enumerate(install_lines)
                                 if "requirements/bootstrap.txt" in line)
        torch_install = next(i for i, line in enumerate(install_lines)
                             if "--index-url https://download.pytorch.org/whl/cpu" in line)
        runtime_install = next(i for i, line in enumerate(install_lines)
                               if "requirements/dev.txt" in line)
        ultralytics_install = next(i for i, line in enumerate(install_lines)
                                   if "requirements/ultralytics.txt" in line)
        assert bootstrap_install < torch_install < runtime_install < ultralytics_install
        assert "--only-binary=:all:" in install_lines[bootstrap_install]
        assert "requirements/constraints-py311.txt" in install_lines[bootstrap_install]
        assert "requirements/torch-cpu.txt" in install_lines[torch_install]
        assert "requirements/constraints-py311.txt" in install_lines[torch_install]
        assert "--only-binary=:all:" in install_lines[torch_install]
        assert (any("requirements/training.txt" in line for line in install_lines)) is train
        assert any("--no-deps" in line and "requirements/ultralytics.txt" in line
                   for line in install_lines)
        values = _config_values(home / ".config/awarespan/node.env")
        assert values["ML_TRAINING_ENABLED"] == ("true" if train else "false")
        assert values["BACKEND_API_URL"] == (
            "https://api.awarespan.bchbenjamin.in" if production else "")
        assert values["ML_DATASET_DIR"] == str(ROOT / "datasets")
        assert values["ML_CHECKPOINT_DIR"] == str(ROOT / "models/working/training_runs")
        assert values["ML_DEPLOYMENT_MANIFEST"] == "models/deployed/manifest.json"
        config = home / ".config/awarespan/node.env"
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
        assert stat.S_IMODE(config.parent.stat().st_mode) == 0o700
        assert values["BACKEND_API_KEY"] == ("smoke-test-key" if production else "")


def test_pi_profile_installs_runtime_without_training_or_dev(tmp_path):
    result, _, log = _run_setup(tmp_path, "--no-service", "--no-production", "--no-train",
                                profile="pi")
    assert result.returncode == 0, result.stdout + result.stderr
    install_lines = log.read_text().splitlines()
    assert any("requirements/bootstrap.txt" in line for line in install_lines)
    assert any("requirements/torch-cpu.txt" in line for line in install_lines)
    assert any("requirements/runtime.txt" in line for line in install_lines)
    assert not any("requirements/training.txt" in line for line in install_lines)
    assert not any("requirements/dev.txt" in line for line in install_lines)
    assert any("requirements/ultralytics.txt" in line for line in install_lines)


def test_invalid_option_combinations_fail_before_install(tmp_path):
    result, _, log = _run_setup(tmp_path, "--service", "--no-production", "--no-train")
    assert result.returncode == 2
    assert "reserved for the Raspberry Pi profile" in result.stderr
    assert not log.exists()


def test_pi_profile_rejects_training_before_install(tmp_path):
    result, _, log = _run_setup(tmp_path, "--train", "--no-production", "--no-service",
                                profile="pi")
    assert result.returncode == 2
    assert "training is restricted to x86-64 workstations" in result.stderr
    assert not log.exists()


def test_noninteractive_production_requires_api_key_before_install(tmp_path):
    result, _, log = _run_setup(tmp_path, "--production", "--no-train")
    assert result.returncode == 2
    assert "requires BACKEND_API_KEY" in result.stderr
    assert not log.exists()


def test_custom_node_backend_and_env_file_options(tmp_path):
    custom_env = tmp_path / "operator-config" / "node.env"
    result, _, log = _run_setup(
        tmp_path, "--train", "--production", "--node-id", "workstation-smoke",
        "--backend-url", "https://backend.example.test", "--env-file", str(custom_env),
        api_key="smoke-test-key",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert any("requirements/training.txt" in line for line in log.read_text().splitlines())
    values = _config_values(custom_env)
    assert values["PI_NODE_ID"] == "workstation-smoke"
    assert values["BACKEND_API_URL"] == "https://backend.example.test"
    assert values["BACKEND_API_KEY"] == "smoke-test-key"
    assert values["MQTT_CLIENT_ID"] == "workstation-smoke"


def test_unsupported_python_fails_before_creating_environment(tmp_path):
    result, _, log = _run_setup(tmp_path, "--no-production", "--no-train", python_minor="3.15")
    assert result.returncode == 2
    assert "requires CPython 3.11" in result.stderr
    assert not log.exists()
    assert not (tmp_path / "venv").exists()


def test_dependency_files_are_exactly_pinned():
    assert (ROOT / ".python-version").read_text().strip() == "3.11"
    requirement_files = [
        ROOT / "requirements/bootstrap.txt", ROOT / "requirements/runtime.txt", ROOT / "requirements/dev.txt",
        ROOT / "requirements/training.txt", ROOT / "requirements/constraints-py311.txt",
        ROOT / "requirements/ultralytics.txt", ROOT / "requirements/torch-cpu.txt",
    ]
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name

    pinned_packages = set()
    pinned_versions = {}
    for path in requirement_files:
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(("-r ", "-c ")):
                included = ROOT / "requirements" / line.split(maxsplit=1)[1]
                assert included.is_file(), f"Missing included manifest: {included}"
                continue
            requirement = Requirement(line)
            package_name = canonicalize_name(requirement.name)
            pinned_packages.add(package_name)
            specifiers = list(requirement.specifier)
            assert len(specifiers) == 1 and specifiers[0].operator == "==", (
                f"Version is not an exact pin in {path.name}: {line}"
            )
            version = specifiers[0].version
            if package_name in pinned_versions:
                assert pinned_versions[package_name] == version, (
                    f"Conflicting versions for {package_name}: "
                    f"{pinned_versions[package_name]} vs {version}"
                )
            pinned_versions[package_name] = version
    expected_packages = {
        "certifi", "charset-normalizer", "contourpy", "cycler", "filelock",
        "filetype", "flake8", "fonttools", "fsspec", "idna", "iniconfig",
        "jinja2", "kagglehub", "kiwisolver", "markupsafe", "matplotlib",
        "mccabe", "mpmath", "networkx", "numpy", "opencv-python-headless",
        "packaging", "paho-mqtt", "pandas", "pillow", "pip", "pluggy", "psutil",
        "py-cpuinfo", "pycodestyle", "pyflakes", "pygments", "pyparsing",
        "pytest", "pytest-mock", "python-dateutil", "python-dotenv", "pytz",
        "pyyaml", "requests", "requests-toolbelt", "roboflow", "scipy", "setuptools",
        "seaborn", "six", "sympy", "torch", "torchvision", "tqdm", "triton",
        "typing-extensions", "tzdata", "ultralytics", "ultralytics-thop",
        "urllib3", "websockets", "wheel",
    }
    assert pinned_packages == expected_packages, (
        f"Dependency inventory changed; missing={expected_packages - pinned_packages}, "
        f"added={pinned_packages - expected_packages}. Review and update the lock inventory."
    )
    assert "ultralytics==8.2.70" in (ROOT / "requirements/ultralytics.txt").read_text()
    runtime_pins = (ROOT / "requirements/runtime.txt").read_text()
    shared_constraints = (ROOT / "requirements/constraints-py311.txt").read_text()
    assert "numpy==1.26.4" in shared_constraints
    assert "pillow==10.4.0" in shared_constraints
    assert "opencv-python-headless==4.10.0.84" in runtime_pins
    assert "opencv-python==" not in runtime_pins
    assert "--no-deps" in (ROOT / "scripts/setup.sh").read_text()
    torch_pins = (ROOT / "requirements/torch-cpu.txt").read_text()
    assert "torch==2.5.1" in torch_pins
    assert "torchvision==0.20.1" in torch_pins


def test_python_315_venv_is_replaced_by_python_311(tmp_path):
    result, _, _ = _run_setup(tmp_path, "--no-production", "--no-train",
                              old_venv_minor="3.15")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Replacing existing Python 3.15 environment with CPython 3.11" in result.stdout
    assert "Python        : CPython 3.11" in result.stdout
