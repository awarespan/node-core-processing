"""
AWARESPAN — System Utilities
Cross-platform system utilities, lock management, Pi hardware inspection, and safe subprocesses.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
import platform
import socket
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from shared.logging.logger import get_logger, sanitize_text
from shared.models.events import PowerStatus

log = get_logger("shared.system")

try:
    import fcntl
except ImportError:
    fcntl = None  # Non-Unix fallback (e.g. Windows dev)


class FileLock:
    """
    Inter-process file lock using flock on Unix systems.
    Prevents concurrent updater runs or overlapping heavy operations.
    """

    def __init__(self, lock_path: str = "/tmp/awarespan-update.lock", timeout_sec: float = 10.0):
        self.lock_path = Path(lock_path)
        self.timeout_sec = timeout_sec
        self._fd = None
        self.locked = False

    def acquire(self) -> bool:
        """Attempt to acquire the file lock within the timeout window."""
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            self._fd = open(self.lock_path, "a+")
        except OSError as exc:
            log.warning("Failed to open lock file %s: %s", self.lock_path, exc)
            return False

        if fcntl is None:
            # Fallback for Windows development environment
            self.locked = True
            return True

        start_time = time.time()
        while time.time() - start_time < self.timeout_sec:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.locked = True
                self._fd.seek(0)
                self._fd.truncate()
                self._fd.write(f"pid={os.getpid()}\ntime={time.time()}\n")
                self._fd.flush()
                return True
            except (BlockingIOError, OSError):
                time.sleep(0.5)

        log.warning("Lock acquisition timed out for %s (held by another process)", self.lock_path)
        return False

    def release(self) -> None:
        """Release the file lock."""
        if not self.locked:
            return
        try:
            if fcntl is not None and self._fd:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
        except OSError as exc:
            log.warning("Error unlocking %s: %s", self.lock_path, exc)
        finally:
            self.locked = False
            if self._fd:
                try:
                    self._fd.close()
                except OSError:
                    pass
                self._fd = None

    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"Could not acquire lock: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def check_internet(timeout: float = 3.0, host: str = "1.1.1.1", port: int = 53) -> bool:
    """
    Quick non-blocking check to verify internet reachability via DNS port.
    Falls back to HTTP if DNS socket check fails.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.close()
        return True
    except OSError:
        pass

    # Secondary check against GitHub
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("140.82.121.4", 443))  # github.com IP fallback
        sock.close()
        return True
    except OSError:
        return False


def get_raspberry_pi_model() -> str:
    """Read the Raspberry Pi hardware model from device tree, or fallback to platform info."""
    model_path = Path("/proc/device-tree/model")
    if model_path.exists():
        try:
            with open(model_path, "r", encoding="utf-8") as f:
                return f.read().strip("\x00 \n\r")
        except OSError:
            pass

    # Check /proc/cpuinfo
    cpuinfo_path = Path("/proc/cpuinfo")
    if cpuinfo_path.exists():
        try:
            with open(cpuinfo_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("Model"):
                        return line.split(":", 1)[1].strip()
        except OSError:
            pass

    return f"{platform.system()} {platform.machine()} ({platform.processor()})"


def get_cpu_temperature() -> Optional[float]:
    """Read CPU temperature in Celsius."""
    # Thermal zone (standard Linux / sysfs)
    thermal_path = Path("/sys/class/thermal/thermal_zone0/temp")
    if thermal_path.exists():
        try:
            with open(thermal_path, "r", encoding="utf-8") as f:
                raw = f.read().strip()
                return float(raw) / 1000.0
        except (ValueError, OSError):
            pass

    # vcgencmd measure_temp fallback (Raspberry Pi OS)
    try:
        res = subprocess.run(["vcgencmd", "measure_temp"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and "temp=" in res.stdout:
            # Output: temp=48.2'C
            val_str = res.stdout.strip().replace("temp=", "").replace("'C", "")
            return float(val_str)
    except Exception:
        pass

    return None


def get_throttled_state() -> PowerStatus:
    """
    Read throttled bitmask from vcgencmd get_throttled.
    Bits on Raspberry Pi:
      0: Under-voltage detected
      1: Arm frequency capped
      2: Currently throttled
      3: Soft temperature limit active
      16: Under-voltage has occurred
      17: Arm frequency capping has occurred
      18: Throttling has occurred
      19: Soft temperature limit has occurred
    """
    raw_output = "0x0"
    try:
        res = subprocess.run(["vcgencmd", "get_throttled"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0 and "=" in res.stdout:
            raw_output = res.stdout.strip().split("=")[1]
    except Exception:
        pass

    try:
        val = int(raw_output, 16)
    except ValueError:
        val = 0

    undervoltage_now = bool(val & 0x1)
    freq_capped_now = bool(val & 0x2)
    undervoltage_occurred = bool(val & 0x10000)
    freq_capped_occurred = bool(val & 0x20000)

    temp_c = get_cpu_temperature()

    return PowerStatus(
        throttled_raw=raw_output,
        undervoltage_now=undervoltage_now,
        undervoltage_occurred=undervoltage_occurred,
        freq_capped_now=freq_capped_now,
        freq_capped_occurred=freq_capped_occurred,
        temp_c=temp_c,
    )


def safe_subprocess_run(
    cmd: List[str],
    timeout: float = 60.0,
    cwd: Optional[str] = None,
    check: bool = False,
) -> Tuple[int, str, str]:
    """
    Run subprocess with sanitized command logging and safe credential protection.
    Returns (returncode, stdout, stderr).
    """
    cmd_str = sanitize_text(" ".join(cmd))
    log.debug("Executing command: %s (cwd=%s)", cmd_str, cwd)

    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            cwd=cwd,
            check=check,
        )
        return res.returncode, res.stdout, res.stderr
    except subprocess.TimeoutExpired:
        log.warning("Command timed out after %ds: %s", timeout, cmd_str)
        return -1, "", f"TimeoutExpired after {timeout}s"
    except Exception as exc:
        log.warning("Command failed to execute: %s - %s", cmd_str, exc)
        return -1, "", str(exc)


def get_git_commit(cwd: Optional[str] = None) -> str:
    """Get the current HEAD commit hash."""
    code, stdout, _ = safe_subprocess_run(["git", "rev-parse", "HEAD"], timeout=5, cwd=cwd)
    if code == 0:
        return stdout.strip()
    return "unknown"
