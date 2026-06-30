"""Background automation daemon for ASUS platform profiles with integrated D-Bus service."""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .battery import BatteryStatus, get_battery_status
from .config import AppConfig, DEFAULT_CONFIG_PATH, load_config
from .logger import setup_logging
from .monitor import HardwareStatus, get_hardware_status
from .notifications import notify_send
from .power import PowerState, PowerStatus, get_power_status
from .profile_journal import ProfileSwitchRecord, append_profile_switch, now_timestamp
from .profiles import PlatformProfileController, PlatformProfileError, Profile, max_profile


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
        config_path: Path = DEFAULT_CONFIG_PATH,
    ) -> None:
        self.config = config
        self.controller = controller
        self.logger = logger
        self.config_path = config_path
        self.dbus_interface: Any = None

    def reload_config(self) -> None:
        """Reload configuration from file."""
        self.logger.info("SIGHUP received. Reloading configuration from %s...", self.config_path)
        try:
            self.config = load_config(self.config_path)
            self.logger.info("Configuration reloaded successfully.")
        except Exception as exc:
            self.logger.error("Failed to reload configuration: %s", exc)

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
        # Emit status change signal if D-Bus is running
        if self.dbus_interface:
            try:
                self.dbus_interface.StatusChanged()
            except Exception as exc:
                self.logger.debug("Failed to emit StatusChanged signal: %s", exc)

        from .config import ProfileMode
        if self.config.daemon.profile_mode == ProfileMode.MANUAL:
            return

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

        if self.dbus_interface:
            try:
                self.dbus_interface.ProfileChanged(decision.profile.value)
            except Exception as exc:
                self.logger.debug("Failed to emit ProfileChanged signal: %s", exc)

    def run_forever(self) -> None:
        """Run synchronous daemon loop (fallback)."""
        self.logger.info("asus-control daemon started (sync fallback)")
        # Register SIGHUP signal handler
        signal.signal(signal.SIGHUP, lambda sig, frame: self.reload_config())
        while True:
            try:
                self.tick()
            except PlatformProfileError as exc:
                self.logger.error("%s", exc)
            except Exception:
                self.logger.exception("Unexpected daemon error")
            time.sleep(self.config.daemon.interval_seconds)

    async def run_forever_async(self, bus_kind: str = "system") -> None:
        """Run async daemon loop with integrated D-Bus service."""
        self.logger.info("asus-control daemon starting (async)...")

        # Register SIGHUP signal handler in asyncio loop
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(signal.SIGHUP, self.reload_config)
            self.logger.debug("Registered SIGHUP handler in event loop.")
        except (NotImplementedError, RuntimeError):
            # Fallback for Windows/certain event loops without add_signal_handler
            signal.signal(signal.SIGHUP, lambda sig, frame: self.reload_config())

        # Start D-Bus service if requested
        if bus_kind != "none":
            self.logger.info("Starting D-Bus service on %s bus...", bus_kind)
            try:
                from .dbus_api import serve, build_interface_class, BUS_NAME
                self.dbus_interface = build_interface_class(bus_kind, daemon=self)()
                # Run D-Bus service as a concurrent task, keeping a strong reference
                self.dbus_task = asyncio.create_task(serve(bus_name=BUS_NAME, bus_kind=bus_kind, interface_obj=self.dbus_interface))
                self.logger.info("D-Bus service registered successfully.")
            except Exception as exc:
                self.logger.error("Failed to start D-Bus service: %s. Continuing without D-Bus.", exc)

        self.logger.info("Automation daemon ticker started.")
        while True:
            try:
                self.tick()
            except PlatformProfileError as exc:
                self.logger.error("%s", exc)
            except Exception:
                self.logger.exception("Unexpected daemon error")
            
            # Use float sleep time from config
            await asyncio.sleep(self.config.daemon.interval_seconds)


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
    parser.add_argument(
        "--bus",
        choices=("session", "system", "none"),
        default="system",
        help="D-Bus bus to register on. Default is 'system'. Use 'none' to disable D-Bus.",
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
            config_path=args.config,
        )
        if args.once:
            daemon.tick()
        else:
            try:
                # Try running asynchronously with integrated D-Bus service
                asyncio.run(daemon.run_forever_async(bus_kind=args.bus))
            except KeyboardInterrupt:
                return 130
            except Exception as exc:
                log.warning("Async loop failed: %s. Falling back to sync loop.", exc)
                daemon.run_forever()
    except (PlatformProfileError, RuntimeError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
