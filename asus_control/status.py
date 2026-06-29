"""Shared status model for CLI, D-Bus and future GUI frontends."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .battery import get_battery_status
from .monitor import get_hardware_status
from .power import get_power_status
from .profiles import PlatformProfileController


@dataclass(frozen=True)
class ControlStatus:
    """Complete status snapshot exposed to frontends."""

    profile: str
    cpu_temp_c: float | None
    gpu_temp_c: float | None
    cpu_fan_rpm: int | None
    gpu_fan_rpm: int | None
    power: str
    battery_percent: int | None
    battery_status: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable status mapping."""
        return asdict(self)


def collect_status(controller: PlatformProfileController | None = None) -> ControlStatus:
    """Collect the current laptop status."""
    profile_controller = controller or PlatformProfileController()
    hardware = get_hardware_status()
    power = get_power_status()
    battery = get_battery_status()
    profile = profile_controller.get_profile()

    return ControlStatus(
        profile=profile.value,
        cpu_temp_c=hardware.cpu_temp.celsius if hardware.cpu_temp else None,
        gpu_temp_c=hardware.gpu_temp.celsius if hardware.gpu_temp else None,
        cpu_fan_rpm=hardware.cpu_fan.rpm if hardware.cpu_fan else None,
        gpu_fan_rpm=hardware.gpu_fan.rpm if hardware.gpu_fan else None,
        power=power.state.value,
        battery_percent=battery.capacity_percent,
        battery_status=battery.status,
    )
