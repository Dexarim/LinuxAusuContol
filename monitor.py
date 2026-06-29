"""Hardware monitoring helpers for temperatures and fans."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


HWMON_ROOT = Path("/sys/class/hwmon")


@dataclass(frozen=True)
class FanReading:
    """Fan speed reading."""

    label: str
    rpm: int


@dataclass(frozen=True)
class TemperatureReading:
    """Temperature reading in Celsius."""

    label: str
    celsius: float


@dataclass(frozen=True)
class HardwareStatus:
    """Combined hardware monitoring status."""

    cpu_temp: TemperatureReading | None
    gpu_temp: TemperatureReading | None
    cpu_fan: FanReading | None
    gpu_fan: FanReading | None


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _read_int(path: Path) -> int | None:
    raw = _read_text(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _hwmon_name(hwmon: Path) -> str:
    return (_read_text(hwmon / "name") or hwmon.name).lower()


def _label_for(hwmon: Path, stem: str, fallback: str) -> str:
    return _read_text(hwmon / f"{stem}_label") or fallback


def _read_temperatures() -> list[tuple[str, str, float]]:
    readings: list[tuple[str, str, float]] = []
    for hwmon in sorted(HWMON_ROOT.glob("hwmon*")):
        device_name = _hwmon_name(hwmon)
        for input_path in sorted(hwmon.glob("temp*_input")):
            milli_c = _read_int(input_path)
            if milli_c is None:
                continue
            stem = input_path.stem.removesuffix("_input")
            label = _label_for(hwmon, stem, stem)
            readings.append((device_name, label, milli_c / 1000.0))
    return readings


def _read_fans() -> list[tuple[str, str, int]]:
    readings: list[tuple[str, str, int]] = []
    for hwmon in sorted(HWMON_ROOT.glob("hwmon*")):
        device_name = _hwmon_name(hwmon)
        for input_path in sorted(hwmon.glob("fan*_input")):
            rpm = _read_int(input_path)
            if rpm is None:
                continue
            stem = input_path.stem.removesuffix("_input")
            label = _label_for(hwmon, stem, stem)
            readings.append((device_name, label, rpm))
    return readings


def _pick_cpu_temp(readings: list[tuple[str, str, float]]) -> TemperatureReading | None:
    preferred_names = ("k10temp", "zenpower", "asus")
    preferred_labels = ("tctl", "tdie", "cpu", "package")
    for device_name, label, value in readings:
        if device_name in preferred_names and label.lower() in preferred_labels:
            return TemperatureReading(label=label, celsius=value)
    for device_name, label, value in readings:
        if device_name in preferred_names:
            return TemperatureReading(label=label, celsius=value)
    return TemperatureReading(label=readings[0][1], celsius=readings[0][2]) if readings else None


def _pick_gpu_temp(readings: list[tuple[str, str, float]]) -> TemperatureReading | None:
    for device_name, label, value in readings:
        if device_name in {"amdgpu", "nouveau", "nvidia"}:
            return TemperatureReading(label=label, celsius=value)
    for device_name, label, value in readings:
        if "gpu" in device_name or "gpu" in label.lower():
            return TemperatureReading(label=label, celsius=value)
    return None


def _pick_fans(readings: list[tuple[str, str, int]]) -> tuple[FanReading | None, FanReading | None]:
    cpu_fan: FanReading | None = None
    gpu_fan: FanReading | None = None

    for _device_name, label, rpm in readings:
        lowered = label.lower()
        fan = FanReading(label=label, rpm=rpm)
        if cpu_fan is None and "cpu" in lowered:
            cpu_fan = fan
        elif gpu_fan is None and "gpu" in lowered:
            gpu_fan = fan

    if cpu_fan is None and readings:
        cpu_fan = FanReading(label=readings[0][1], rpm=readings[0][2])
    if gpu_fan is None and len(readings) > 1:
        gpu_fan = FanReading(label=readings[1][1], rpm=readings[1][2])

    return cpu_fan, gpu_fan


def get_hardware_status() -> HardwareStatus:
    """Read CPU/GPU temperatures and fan RPMs from hwmon."""
    temperatures = _read_temperatures()
    fans = _read_fans()
    cpu_fan, gpu_fan = _pick_fans(fans)
    return HardwareStatus(
        cpu_temp=_pick_cpu_temp(temperatures),
        gpu_temp=_pick_gpu_temp(temperatures),
        cpu_fan=cpu_fan,
        gpu_fan=gpu_fan,
    )
