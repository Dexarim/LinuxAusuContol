"""YAML configuration loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from profiles import Profile


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")


@dataclass(frozen=True)
class BatteryConfig:
    """Profile policy for AC and battery states."""

    on_ac: Profile = Profile.PERFORMANCE
    on_battery: Profile = Profile.BALANCED
    low_battery: Profile = Profile.QUIET
    low_battery_percent: int = 25


@dataclass(frozen=True)
class TemperatureConfig:
    """Temperature thresholds in Celsius."""

    quiet_max: int = 55
    balanced_max: int = 75
    performance_above: int = 75


@dataclass(frozen=True)
class DaemonConfig:
    """Daemon runtime settings."""

    interval_seconds: float = 5.0
    notify: bool = True
    profile_switch_journal: bool = True
    performance_apps: tuple[str, ...] = (
        "steam",
        "steamwebhelper",
        "prismlauncher",
        "blender",
        "lutris",
        "heroic",
        "heroicgameslauncher",
        "gamescope",
        "mangohud",
        "wine",
        "proton",
        "umu",
        "gamemoderun",
    )


@dataclass(frozen=True)
class AppConfig:
    """Application configuration."""

    battery: BatteryConfig = BatteryConfig()
    temperature: TemperatureConfig = TemperatureConfig()
    daemon: DaemonConfig = DaemonConfig()


def _as_mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _profile(value: Any, fallback: Profile) -> Profile:
    if value is None:
        return fallback
    return Profile.from_string(str(value))


def _int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _bool(value: Any, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Load configuration from YAML, falling back to safe defaults."""
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to read config.yaml. Install requirements.txt first."
        ) from exc

    if not path.exists():
        return AppConfig()

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    root = _as_mapping(raw)
    battery_raw = _as_mapping(root.get("battery"))
    temp_raw = _as_mapping(root.get("temperature"))
    daemon_raw = _as_mapping(root.get("daemon"))

    default_battery = BatteryConfig()
    battery_config = BatteryConfig(
        on_ac=_profile(battery_raw.get("on_ac"), default_battery.on_ac),
        on_battery=_profile(battery_raw.get("on_battery"), default_battery.on_battery),
        low_battery=_profile(battery_raw.get("low_battery"), default_battery.low_battery),
        low_battery_percent=_int(
            battery_raw.get("low_battery_percent"),
            default_battery.low_battery_percent,
        ),
    )

    default_temp = TemperatureConfig()
    temp_config = TemperatureConfig(
        quiet_max=_int(temp_raw.get("quiet_max"), default_temp.quiet_max),
        balanced_max=_int(temp_raw.get("balanced_max"), default_temp.balanced_max),
        performance_above=_int(
            temp_raw.get("performance_above"),
            default_temp.performance_above,
        ),
    )

    default_daemon = DaemonConfig()
    apps_raw = daemon_raw.get("performance_apps", default_daemon.performance_apps)
    apps = tuple(str(item).lower() for item in apps_raw) if isinstance(apps_raw, list) else default_daemon.performance_apps
    daemon_config = DaemonConfig(
        interval_seconds=_float(
            daemon_raw.get("interval_seconds"),
            default_daemon.interval_seconds,
        ),
        notify=_bool(daemon_raw.get("notify"), default_daemon.notify),
        profile_switch_journal=_bool(
            daemon_raw.get("profile_switch_journal"),
            default_daemon.profile_switch_journal,
        ),
        performance_apps=apps,
    )

    return AppConfig(
        battery=battery_config,
        temperature=temp_config,
        daemon=daemon_config,
    )
