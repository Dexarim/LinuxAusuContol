"""AC/DC power detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


POWER_SUPPLY_ROOT = Path("/sys/class/power_supply")


class PowerState(str, Enum):
    """External power state."""

    AC = "AC"
    BATTERY = "Battery"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class PowerStatus:
    """Current power status."""

    state: PowerState
    source: Path | None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def get_power_status() -> PowerStatus:
    """Return whether the laptop is connected to external power."""
    saw_mains = False
    for candidate in sorted(POWER_SUPPLY_ROOT.glob("*")):
        supply_type = (_read_text(candidate / "type") or "").lower()
        if supply_type not in {"mains", "usb", "usb_c", "usb_pd"}:
            continue
        saw_mains = True
        online = _read_text(candidate / "online")
        if online == "1":
            return PowerStatus(state=PowerState.AC, source=candidate)

    if saw_mains:
        return PowerStatus(state=PowerState.BATTERY, source=None)
    return PowerStatus(state=PowerState.UNKNOWN, source=None)
