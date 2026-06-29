"""Battery information from Linux power_supply sysfs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


POWER_SUPPLY_ROOT = Path("/sys/class/power_supply")


@dataclass(frozen=True)
class BatteryStatus:
    """Battery capacity and charging state."""

    capacity_percent: int | None
    status: str | None
    path: Path | None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _find_battery() -> Path | None:
    for candidate in sorted(POWER_SUPPLY_ROOT.glob("*")):
        if (_read_text(candidate / "type") or "").lower() == "battery":
            return candidate
    return None


def get_battery_status() -> BatteryStatus:
    """Read battery capacity from sysfs."""
    battery = _find_battery()
    if battery is None:
        return BatteryStatus(capacity_percent=None, status=None, path=None)

    capacity_raw = _read_text(battery / "capacity")
    capacity: int | None
    try:
        capacity = int(capacity_raw) if capacity_raw is not None else None
    except ValueError:
        capacity = None

    return BatteryStatus(
        capacity_percent=capacity,
        status=_read_text(battery / "status"),
        path=battery,
    )
