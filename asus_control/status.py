"""Shared status model for CLI, D-Bus and future GUI frontends."""

from __future__ import annotations

import time
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
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
    
    # New metrics for release v0.2.0 GUI
    cpu_usage_percent: float | None
    ram_usage_percent: float | None
    ssd_temp_c: float | None
    amd_gpu_usage_percent: int | None
    nvidia_gpu_usage_percent: int | None
    nvidia_status: str | None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable status mapping."""
        return asdict(self)


# Keep track of previous CPU ticks to compute CPU utilization delta
_last_cpu_ticks: tuple[float, float] | None = None  # (idle_ticks, total_ticks)


def _get_cpu_usage() -> float | None:
    global _last_cpu_ticks
    try:
        stat_path = Path("/proc/stat")
        if not stat_path.exists():
            return None
        
        # Read the first line of /proc/stat
        with stat_path.open("r", encoding="utf-8") as f:
            cpu_line = f.readline()
        
        parts = cpu_line.split()
        if len(parts) >= 5 and parts[0] == "cpu":
            # Fields: user, nice, system, idle, iowait, irq, softirq, steal
            ticks = [float(x) for x in parts[1:9]]
            idle = ticks[3] + ticks[4]  # idle + iowait
            total = sum(ticks)
            
            if _last_cpu_ticks is None:
                _last_cpu_ticks = (idle, total)
                return 0.0
            
            prev_idle, prev_total = _last_cpu_ticks
            _last_cpu_ticks = (idle, total)
            
            idle_delta = idle - prev_idle
            total_delta = total - prev_total
            
            if total_delta > 0:
                percent = (1.0 - (idle_delta / total_delta)) * 100.0
                return max(0.0, min(100.0, percent))
    except Exception:
        pass
    return None


def _get_ram_usage() -> float | None:
    try:
        meminfo_path = Path("/proc/meminfo")
        if not meminfo_path.exists():
            return None
        
        meminfo: dict[str, float] = {}
        with meminfo_path.open("r", encoding="utf-8") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].strip(":")
                    meminfo[key] = float(parts[1])
        
        total = meminfo.get("MemTotal", 0.0)
        available = meminfo.get("MemAvailable", 0.0)
        if total > 0:
            return ((total - available) / total) * 100.0
    except Exception:
        pass
    return None


def _get_ssd_temp() -> float | None:
    try:
        for hwmon in Path("/sys/class/hwmon").glob("hwmon*"):
            name_path = hwmon / "name"
            if name_path.exists() and name_path.read_text(encoding="utf-8").strip() == "nvme":
                # Check for temp1_input (Composite temp is usually temp1)
                temp_path = hwmon / "temp1_input"
                if temp_path.exists():
                    val = float(temp_path.read_text(encoding="utf-8").strip())
                    return val / 1000.0
    except Exception:
        pass
    return None


def _get_amd_gpu_usage() -> int | None:
    try:
        for path in Path("/sys/class/drm").glob("card*/device/gpu_busy_percent"):
            if path.exists():
                return int(path.read_text(encoding="utf-8").strip())
    except Exception:
        pass
    return None


def _get_nvidia_status_and_usage() -> tuple[str | None, int | None]:
    try:
        devs = list(Path("/sys/bus/pci/devices").glob("*/vendor"))
        nvidia_dev = None
        for dev in devs:
            if dev.exists() and dev.read_text(encoding="utf-8").strip() == "0x10de":
                nvidia_dev = dev.parent
                break
        
        if nvidia_dev is None:
            return None, None
        
        status_path = nvidia_dev / "power" / "runtime_status"
        if not status_path.exists():
            return "Off", None
        
        status = status_path.read_text(encoding="utf-8").strip().capitalize()
        if status == "Suspended":
            return "Suspended", 0
        elif status == "Active":
            # Run nvidia-smi with timeout to avoid hanging
            try:
                res = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=0.8
                )
                if res.returncode == 0:
                    val = int(res.stdout.strip())
                    return "Active", val
            except Exception:
                pass
            return "Active", None
        return status, None
    except Exception:
        pass
    return None, None


def collect_status(controller: PlatformProfileController | None = None) -> ControlStatus:
    """Collect the current laptop status."""
    profile_controller = controller or PlatformProfileController()
    hardware = get_hardware_status()
    power = get_power_status()
    battery = get_battery_status()
    profile = profile_controller.get_profile()
    
    cpu_usage = _get_cpu_usage()
    ram_usage = _get_ram_usage()
    ssd_temp = _get_ssd_temp()
    amd_gpu = _get_amd_gpu_usage()
    nv_status, nv_gpu = _get_nvidia_status_and_usage()

    return ControlStatus(
        profile=profile.value,
        cpu_temp_c=hardware.cpu_temp.celsius if hardware.cpu_temp else None,
        gpu_temp_c=hardware.gpu_temp.celsius if hardware.gpu_temp else None,
        cpu_fan_rpm=hardware.cpu_fan.rpm if hardware.cpu_fan else None,
        gpu_fan_rpm=hardware.gpu_fan.rpm if hardware.gpu_fan else None,
        power=power.state.value,
        battery_percent=battery.capacity_percent,
        battery_status=battery.status,
        
        # New metrics
        cpu_usage_percent=cpu_usage,
        ram_usage_percent=ram_usage,
        ssd_temp_c=ssd_temp,
        amd_gpu_usage_percent=amd_gpu,
        nvidia_gpu_usage_percent=nv_gpu,
        nvidia_status=nv_status,
    )
