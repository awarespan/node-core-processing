"""Isolated smoke tests for setup option combinations (no host packages/services)."""
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run_setup(tmp_path, *options, api_key=None):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)
    log = tmp_path / "install.log"
    real_python = sys.executable
    (fake_bin / "python3").write_text(
        "#!/usr/bin/env bash\n"
        f"REAL_PYTHON={real_python!r}\n"
        "if [[ \"${1:-}\" == -m && \"${2:-}\" == venv ]]; then\n"
        "  mkdir -p \"$3/bin\"\n"
        "  cat >\"$3/bin/python\" <<'STUB'\n"
        "#!/usr/bin/env bash\n"
        f"REAL_PYTHON={sys.executable!r}\n"
        "if [[ \"${1:-}\" == -m && \"${2:-}\" == pip ]]; then printf '%s\\n' \"$*\" >>\"$AWARESPAN_TEST_INSTALL_LOG\"; exit 0; fi\n"
        "exec \"$REAL_PYTHON\" \"$@\"\n"
        "STUB\n"
        "  chmod +x \"$3/bin/python\"\n"
        "else exec \"$REAL_PYTHON\" \"$@\"; fi\n"
    )
    (fake_bin / "dnf").write_text("#!/usr/bin/env bash\nexit 0\n")
    (fake_bin / "sudo").write_text("#!/usr/bin/env bash\nexit 0\n")
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
    })
    env.pop("BACKEND_API_KEY", None)
    if api_key:
        env["BACKEND_API_KEY"] = api_key
    result = subprocess.run(
        [str(ROOT / "scripts/setup.sh"), "--profile", "linux", "--non-interactive", *options],
        cwd=ROOT, env=env, text=True, capture_output=True, check=False,
    )
    return result, home, log


def test_linux_setup_option_matrix(tmp_path):
    """Train and production are independent toggles; exercise all four combinations."""
    cases = [
        (False, False), (False, True), (True, False), (True, True),
    ]
    for index, (train, production) in enumerate(cases):
        case_dir = tmp_path / str(index)
        case_dir.mkdir()
        options = ["--train" if train else "--no-train",
                   "--production" if production else "--no-production"]
        result, home, log = _run_setup(case_dir, *options,
                                       api_key="smoke-test-key" if production else None)
        assert result.returncode == 0, result.stdout + result.stderr
        installed = log.read_text()
        assert "-m pip install --upgrade pip" in installed
        assert "requirements/dev.txt" in installed
        assert ("requirements/training.txt" in installed) is train
        config = home / ".config/awarespan/node.env"
        values = dict(line.split("=", 1) for line in config.read_text().splitlines()
                      if "=" in line and not line.startswith("#"))
        assert values["ML_TRAINING_ENABLED"] == ("true" if train else "false")
        assert values["BACKEND_API_URL"] == (
            "https://api.awarespan.bchbenjamin.in" if production else "")
        assert values["ML_DATASET_DIR"] == str(ROOT / "datasets")
        assert values["ML_CHECKPOINT_DIR"] == str(ROOT / "models/working/training_runs")
        assert values["ML_DEPLOYMENT_MANIFEST"] == "models/deployed/manifest.json"
        assert stat.S_IMODE(config.stat().st_mode) == 0o600
        assert stat.S_IMODE(config.parent.stat().st_mode) == 0o700
        if production:
            assert values["BACKEND_API_KEY"] == "smoke-test-key"
        else:
            assert values["BACKEND_API_KEY"] == ""


def test_pi_profile_installs_runtime_only(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    real_python = sys.executable
    (fake_bin / "python3").write_text(
        "#!/usr/bin/env bash\n"
        f"REAL_PYTHON={real_python!r}\n"
        "if [[ \"${1:-}\" == -m && \"${2:-}\" == venv ]]; then mkdir -p \"$3/bin\"; "
        "cat >\"$3/bin/python\" <<'STUB'\n#!/usr/bin/env bash\n"
        f"REAL_PYTHON={sys.executable!r}\n"
        "if [[ \"${1:-}\" == -m && \"${2:-}\" == pip ]]; then printf '%s\\n' \"$*\" >>\"$AWARESPAN_TEST_INSTALL_LOG\"; exit 0; fi\n"
        "exec \"$REAL_PYTHON\" \"$@\"\nSTUB\n"
        "chmod +x \"$3/bin/python\"; else exec \"$REAL_PYTHON\" \"$@\"; fi\n"
    )
    (fake_bin / "dnf").write_text("#!/usr/bin/env bash\nexit 0\n")
    (fake_bin / "sudo").write_text("#!/usr/bin/env bash\nexit 0\n")
    for item in fake_bin.iterdir(): item.chmod(0o755)
    home = tmp_path / "home"; home.mkdir()
    log = tmp_path / "install.log"
    env = os.environ.copy(); env.update({"HOME": str(home), "PATH": f"{fake_bin}:{os.environ['PATH']}",
                                          "AWARESPAN_VENV": str(tmp_path / "venv"),
                                          "AWARESPAN_TEST_INSTALL_LOG": str(log)})
    result = subprocess.run([str(ROOT / "scripts/setup.sh"), "--profile", "pi", "--no-service",
                             "--no-production", "--non-interactive"], cwd=ROOT, env=env,
                            text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    installed = log.read_text()
    assert "requirements/runtime.txt" in installed
    assert "requirements/training.txt" not in installed
    assert "requirements/dev.txt" not in installed


def test_invalid_option_combinations_fail_before_install(tmp_path):
    result, _, log = _run_setup(tmp_path, "--service", "--no-production", "--no-train")
    assert result.returncode == 2
    assert "reserved for the Raspberry Pi profile" in result.stderr
    assert not log.exists()


def test_pi_profile_rejects_training_before_install(tmp_path):
    result, _, log = _run_setup(tmp_path, "--profile", "pi", "--train",
                                "--no-production", "--no-service")
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
    assert "requirements/training.txt" in log.read_text()
    values = dict(line.split("=", 1) for line in custom_env.read_text().splitlines()
                  if "=" in line and not line.startswith("#"))
    assert values["PI_NODE_ID"] == "workstation-smoke"
    assert values["BACKEND_API_URL"] == "https://backend.example.test"
    assert values["BACKEND_API_KEY"] == "smoke-test-key"
    assert values["MQTT_CLIENT_ID"] == "workstation-smoke"
