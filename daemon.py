"""Background automation daemon for ASUS platform profiles."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from battery import BatteryStatus, get_battery_status
from config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from logger import setup_logging
from monitor import HardwareStatus, get_hardware_status
from notifications import notify_send
from power import PowerState, PowerStatus, get_power_status
from profile_journal import ProfileSwitchRecord, append_profile_switch, now_timestamp
from profiles import PlatformProfileController, PlatformProfileError, Profile, max_profile


PROC_ROOT = Path("/proc")


@dataclass(frozen=True)
class SystemSnapshot:
    """Current state used by automation policy."""

    hardware: HardwareStatus
    power: PowerStatus
    battery: BatteryStatus
    profile: Profile
    performance_app_running: bool


@dataclass(frozen=True)
class ProfileDecision:
    """Desired profile and the reason behind it."""

    profile: Profile
    reason: str


def is_process_running(process_names: tuple[str, ...]) -> bool:
    """Check /proc for configured performance application names."""
    names = {name.lower() for name in process_names}
    for process_dir in PROC_ROOT.glob("[0-9]*"):
        comm_path = process_dir / "comm"
        cmdline_path = process_dir / "cmdline"
        try:
            comm = comm_path.read_text(encoding="utf-8").strip().lower()
        except OSError:
            comm = ""
        try:
            cmdline = (
                cmdline_path.read_text(encoding="utf-8")
                .replace("\x00", " ")
                .strip()
                .lower()
            )
        except OSError:
            cmdline = ""
        haystacks = (comm, cmdline)
        if any(name == value or name in value for name in names for value in haystacks):
            return True
    return False


def desired_profile(snapshot: SystemSnapshot, config: AppConfig) -> ProfileDecision:
    """Choose the desired profile from power, battery and temperature policy."""
    if snapshot.power.state is PowerState.AC:
        desired = config.battery.on_ac
        reason = "ac_power"
    elif (
        snapshot.battery.capacity_percent is not None
        and snapshot.battery.capacity_percent < config.battery.low_battery_percent
    ):
        desired = config.battery.low_battery
        reason = "low_battery"
    else:
        desired = config.battery.on_battery
        reason = "battery_power"

    if snapshot.performance_app_running:
        next_profile = max_profile(desired, Profile.PERFORMANCE)
        if next_profile != desired:
            reason = "performance_app"
        desired = next_profile

    hottest = max(
        [
            temp.celsius
            for temp in (snapshot.hardware.cpu_temp, snapshot.hardware.gpu_temp)
            if temp is not None
        ],
        default=None,
    )
    if hottest is not None:
        if hottest >= config.temperature.performance_above:
            next_profile = max_profile(desired, Profile.PERFORMANCE)
            if next_profile != desired:
                reason = "temperature_performance"
            desired = next_profile
        elif hottest > config.temperature.quiet_max:
            next_profile = max_profile(desired, Profile.BALANCED)
            if next_profile != desired:
                reason = "temperature_balanced"
            desired = next_profile

    return ProfileDecision(profile=desired, reason=reason)


class AsusControlDaemon:
    """Main daemon loop."""

    def __init__(
        self,
        config: AppConfig,
        controller: PlatformProfileController,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.controller = controller
        self.logger = logger

    def snapshot(self) -> SystemSnapshot:
        """Read all inputs required by the automation policy."""
        return SystemSnapshot(
            hardware=get_hardware_status(),
            power=get_power_status(),
            battery=get_battery_status(),
            profile=self.controller.get_profile(),
            performance_app_running=is_process_running(
                self.config.daemon.performance_apps
            ),
        )

    def tick(self) -> None:
        """Perform one policy evaluation and apply profile changes."""
        snapshot = self.snapshot()
        decision = desired_profile(snapshot, self.config)
        if decision.profile == snapshot.profile:
            return

        self.controller.set_profile(decision.profile)
        message = (
            f"Profile changed: {snapshot.profile.value} -> "
            f"{decision.profile.value} ({decision.reason})"
        )
        if self.config.daemon.profile_switch_journal:
            self.logger.info(message)
            append_profile_switch(
                ProfileSwitchRecord(
                    timestamp=now_timestamp(),
                    previous_profile=snapshot.profile.value,
                    new_profile=decision.profile.value,
                    reason=decision.reason,
                    cpu_temp_c=(
                        snapshot.hardware.cpu_temp.celsius
                        if snapshot.hardware.cpu_temp
                        else None
                    ),
                    gpu_temp_c=(
                        snapshot.hardware.gpu_temp.celsius
                        if snapshot.hardware.gpu_temp
                        else None
                    ),
                    power=snapshot.power.state.value,
                    battery_percent=snapshot.battery.capacity_percent,
                    performance_app_running=snapshot.performance_app_running,
                )
            )
        notify_send("ASUS Control", message, self.config.daemon.notify)

    def run_forever(self) -> None:
        """Run daemon loop until interrupted by systemd or user."""
        self.logger.info("asus-control daemon started")
        while True:
            try:
                self.tick()
            except PlatformProfileError as exc:
                self.logger.error("%s", exc)
            except Exception:
                self.logger.exception("Unexpected daemon error")
            time.sleep(self.config.daemon.interval_seconds)


def build_parser() -> argparse.ArgumentParser:
    """Build daemon argument parser."""
    parser = argparse.ArgumentParser(description="ASUS Control automation daemon")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one automation tick and exit",
    )
    return parser


def main() -> int:
    """Daemon entry point."""
    args = build_parser().parse_args()
    log = setup_logging("asus-control.daemon")
    try:
        app_config = load_config(args.config)
        daemon = AsusControlDaemon(
            config=app_config,
            controller=PlatformProfileController(),
            logger=log,
        )
        if args.once:
            daemon.tick()
        else:
            daemon.run_forever()
    except (PlatformProfileError, RuntimeError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
