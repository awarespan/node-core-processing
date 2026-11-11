"""
AWARESPAN — Centralized Configuration Management
Canonical environment loading with strong typing and explicit repo-root resolution.

Project: AWARESPAN
Tagline: Awareness Without Boundaries.
Official problem statement: An AI-Powered Safety Device.
Contact: awarespan@bchbenjamin.in
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set
import uuid

import dotenv


def find_repo_root() -> Path:
    """Find git repository root directory by walking up from this file."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".git").is_dir() or (parent / ".env.example").is_file():
            return parent
    return Path.cwd()


REPO_ROOT = find_repo_root()


def find_canonical_env() -> Optional[Path]:
    """
    Locate the canonical root .env file.
    Resolution priority:
    1. REPO_ROOT / .env
    2. os.environ['AWARESPAN_ENV_FILE']
    3. CWD / .env
    4. ~/edge-ai/.env
    5. ~/SIP/node-backend/.env
    """
    explicit = os.environ.get("AWARESPAN_ENV_FILE")
    if explicit and Path(explicit).is_file():
        return Path(explicit).resolve()

    candidates = [
        Path("/etc/awarespan/node.env"),
        Path.home() / ".awarespan" / "node.env",
        Path("/var/lib/awarespan/node.env"),
        Path.home() / "edge-ai" / ".env",
        REPO_ROOT / ".env",
        Path.cwd() / ".env",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


# Load canonical .env into environment once at module import
CANONICAL_ENV_PATH = find_canonical_env()
if CANONICAL_ENV_PATH:
    dotenv.load_dotenv(CANONICAL_ENV_PATH, override=False)


def _get_str(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val.strip() if val is not None else default


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _get_int(key: str, default: int = 0) -> int:
    val = os.getenv(key)
    if val is None or not val.strip():
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def _get_float(key: str, default: float = 0.0) -> float:
    val = os.getenv(key)
    if val is None or not val.strip():
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


def _get_list(key: str, default: Optional[List[str]] = None) -> List[str]:
    val = os.getenv(key)
    if val is None or not val.strip():
        return list(default or [])
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass
class Settings:
    """Strongly-typed runtime configuration for AWARESPAN edge nodes."""

    # Repository paths
    repo_root: Path = REPO_ROOT
    env_file_path: Optional[Path] = CANONICAL_ENV_PATH

    # Node Identity
    node_id: str = field(default_factory=lambda: _get_str("PI_NODE_ID", ""))
    device_secret: str = field(default_factory=lambda: _get_str("PI_DEVICE_SECRET", ""))

    # Backend REST API
    backend_api_url: str = field(
        default_factory=lambda: _get_str("BACKEND_API_URL", "").rstrip("/")
    )
    backend_api_key: str = field(default_factory=lambda: _get_str("BACKEND_API_KEY", ""))

    # MQTT Broker
    mqtt_broker_url: str = field(
        default_factory=lambda: _get_str("MQTT_BROKER_URL", "")
    )
    mqtt_client_id: str = field(
        default_factory=lambda: _get_str("MQTT_CLIENT_ID", f"node-{uuid.getnode():012x}")
    )
    mqtt_username: str = field(default_factory=lambda: _get_str("MQTT_USERNAME", ""))
    mqtt_password: str = field(default_factory=lambda: _get_str("MQTT_PASSWORD", ""))
    mqtt_use_tls: bool = field(default_factory=lambda: _get_bool("MQTT_USE_TLS", False))
    mqtt_tls_ca_cert: str = field(default_factory=lambda: _get_str("MQTT_TLS_CA_CERT", ""))
    mqtt_tls_insecure: bool = field(default_factory=lambda: _get_bool("MQTT_TLS_INSECURE", False))

    # Telegram Bot & Notifications
    bot_token: str = field(default_factory=lambda: _get_str("BOT_TOKEN", ""))
    primary_chat_id: str = field(default_factory=lambda: _get_str("PRIMARY_CHAT_ID", ""))
    allowed_chat_ids: List[str] = field(default_factory=lambda: _get_list("ALLOWED_CHAT_IDS", []))

    # Alert Webhook Fallback
    alert_webhook_url: str = field(default_factory=lambda: _get_str("ALERT_WEBHOOK_URL", ""))

    # Automatic Updater & Node Manager
    update_branch: str = field(default_factory=lambda: _get_str("AWARESPAN_UPDATE_BRANCH", "main"))
    update_check_interval: int = field(
        default_factory=lambda: _get_int("AWARESPAN_UPDATE_CHECK_INTERVAL", 120)
    )
    repo_url: str = field(
        default_factory=lambda: _get_str(
            "AWARESPAN_REPO_URL", "https://github.com/awarespan/node-core-processing.git"
        )
    )
    auto_update_enabled: bool = field(
        default_factory=lambda: _get_bool("AWARESPAN_AUTO_UPDATE_ENABLED", True)
    )
    state_dir: str = field(
        default_factory=lambda: _get_str("AWARESPAN_STATE_DIR", "/var/lib/awarespan")
    )
    lock_file: str = field(
        default_factory=lambda: _get_str("AWARESPAN_LOCK_FILE", "/tmp/awarespan-update.lock")
    )

    # ML Pipeline (explicitly disabled on production nodes by default)
    ml_training_enabled: bool = field(
        default_factory=lambda: _get_bool("ML_TRAINING_ENABLED", False)
    )
    dataset_dir: str = field(
        default_factory=lambda: _get_str("ML_DATASET_DIR", str(REPO_ROOT / "datasets"))
    )
    checkpoint_dir: str = field(
        default_factory=lambda: _get_str("ML_CHECKPOINT_DIR", str(REPO_ROOT / "runs"))
    )
    default_model: str = field(
        default_factory=lambda: _get_str("ML_DEFAULT_MODEL", "yolov8n_best_weapon.pt")
    )

    # Node Runtime
    runtime_host: str = field(default_factory=lambda: _get_str("RUNTIME_HOST", "0.0.0.0"))
    runtime_port: int = field(default_factory=lambda: _get_int("RUNTIME_PORT", 8766))
    confidence_threshold: float = field(
        default_factory=lambda: _get_float("CONFIDENCE_THRESHOLD", 0.45)
    )
    tier1_labels: Set[str] = field(
        default_factory=lambda: {
            "person", "dog", "cat", "horse", "cow", "sheep", "elephant", "bear", "zebra", "giraffe"
        }
    )
    tier2_labels: Set[str] = field(
        default_factory=lambda: {
            "car", "motorcycle", "bus", "truck", "train", "knife", "gun", "weapon", "pistol", "rifle"
        }
    )
    cooldown_seconds: float = field(
        default_factory=lambda: _get_float("COOLDOWN_SECONDS", 8.0)
    )
    offline_queue_path: str = field(
        default_factory=lambda: _get_str("OFFLINE_QUEUE_PATH", "/tmp/awarespan_event_queue.db")
    )
    siren_enabled: bool = field(default_factory=lambda: _get_bool("SIREN_ENABLED", True))
    siren_file: str = field(
        default_factory=lambda: _get_str("SIREN_FILE", str(REPO_ROOT / "Samples" / "siren.wav"))
    )

    # Volunteer Media Gateway
    volunteer_gateway_enabled: bool = field(
        default_factory=lambda: _get_bool("VOLUNTEER_GATEWAY_ENABLED", True)
    )
    volunteer_gateway_host: str = field(
        default_factory=lambda: _get_str("VOLUNTEER_GATEWAY_HOST", "0.0.0.0")
    )
    volunteer_gateway_port: int = field(
        default_factory=lambda: _get_int("VOLUNTEER_GATEWAY_PORT", 8443)
    )
    volunteer_gateway_tls: bool = field(
        default_factory=lambda: _get_bool("VOLUNTEER_GATEWAY_TLS", False)
    )
    volunteer_max_sessions: int = field(
        default_factory=lambda: _get_int("VOLUNTEER_MAX_SESSIONS", 5)
    )
    volunteer_max_cameras: int = field(
        default_factory=lambda: _get_int("VOLUNTEER_MAX_CAMERAS", 2)
    )
    volunteer_max_microphones: int = field(
        default_factory=lambda: _get_int("VOLUNTEER_MAX_MICROPHONES", 2)
    )
    volunteer_pairing_timeout_sec: int = field(
        default_factory=lambda: _get_int("VOLUNTEER_PAIRING_TIMEOUT_SEC", 300)
    )
    volunteer_heartbeat_timeout_sec: int = field(
        default_factory=lambda: _get_int("VOLUNTEER_HEARTBEAT_TIMEOUT_SEC", 30)
    )
    volunteer_portal_static_dir: str = field(
        default_factory=lambda: _get_str("VOLUNTEER_PORTAL_STATIC_DIR", str(REPO_ROOT / "static" / "volunteer"))
    )
    totp_secret_file: str = field(
        default_factory=lambda: _get_str("TOTP_SECRET_FILE", "/var/lib/awarespan/totp_secret.json")
    )
    totp_window: int = field(
        default_factory=lambda: _get_int("TOTP_WINDOW", 1)
    )
    telegram_queue_path: str = field(
        default_factory=lambda: _get_str("TELEGRAM_QUEUE_PATH", "/tmp/awarespan_telegram_queue.db")
    )
    ap_ssid: str = field(
        default_factory=lambda: _get_str("AP_SSID", "AWARESPAN-AP")
    )
    ap_gateway_ip: str = field(
        default_factory=lambda: _get_str("AP_GATEWAY_IP", "192.168.4.1")
    )

    # Logging
    log_level: str = field(default_factory=lambda: _get_str("LOG_LEVEL", "INFO").upper())
    log_dir: str = field(default_factory=lambda: _get_str("LOG_DIR", "/var/log/awarespan"))


# Global singleton settings instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Retrieve the global Settings instance."""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


def reload_settings() -> Settings:
    """Reload settings from disk."""
    global _settings_instance, CANONICAL_ENV_PATH
    CANONICAL_ENV_PATH = find_canonical_env()
    if CANONICAL_ENV_PATH:
        dotenv.load_dotenv(CANONICAL_ENV_PATH, override=True)
    _settings_instance = Settings()
    return _settings_instance
