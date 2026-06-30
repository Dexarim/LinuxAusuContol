"""D-Bus API service exposing status and profile controls on the system bus."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any
from contextvars import ContextVar

from .profiles import PlatformProfileController, Profile, PlatformProfileError
from .status import collect_status


BUS_NAME = "org.asuslinux.Control"
OBJECT_PATH = "/org/asuslinux/Control"
INTERFACE_NAME = "org.asuslinux.Control"


# Context variable to store the active D-Bus message context for the current task
current_dbus_message: ContextVar[Any] = ContextVar("current_dbus_message")


def _load_dbus_next() -> tuple[object, object, object, object, object]:
    try:
        from dbus_next import BusType, DBusError
        from dbus_next.aio import MessageBus
        from dbus_next.service import ServiceInterface, method, signal
    except ImportError as exc:
        raise RuntimeError(
            "dbus-next is required for D-Bus support. Install requirements.txt first."
        ) from exc
    return BusType, MessageBus, ServiceInterface, method, signal


# Monkey-patch ServiceInterface to track the active message sender in a task-local context
try:
    _, _, ServiceInterface, _, _ = _load_dbus_next()
    _original_msg_body_to_args = ServiceInterface._msg_body_to_args

    @staticmethod
    def _custom_msg_body_to_args(msg):
        current_dbus_message.set(msg)
        return _original_msg_body_to_args(msg)

    ServiceInterface._msg_body_to_args = _custom_msg_body_to_args
except Exception:
    pass


def check_polkit_auth(sender: str) -> None:
    """Authorize the sender using Polkit for the set-profile action."""
    try:
        from dbus_next import DBusError
    except ImportError:
        return

    # If sender is empty or none, we can't check
    if not sender:
        raise DBusError(
            "org.asuslinux.Control.Error.NotAuthorized",
            "Polkit check failed: sender context is missing."
        )

    try:
        # Run pkcheck to verify authorization
        res = subprocess.run(
            [
                "pkcheck",
                "-a", "org.asuslinux.control.set-profile",
                "-s", sender,
                "-u"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode != 0:
            raise DBusError(
                "org.asuslinux.Control.Error.NotAuthorized",
                f"Polkit authorization denied: {res.stderr.strip() or 'Action not allowed'}"
            )
    except FileNotFoundError:
        # pkcheck is not available (e.g. non-systemd environment or minimal container)
        # Fallback: allow if running as root
        import os
        if os.getuid() != 0:
            raise DBusError(
                "org.asuslinux.Control.Error.NotAuthorized",
                "Polkit (pkcheck) is missing, and caller is not root."
            )


def build_interface_class(bus_kind: str = "session", daemon: Any = None) -> type:
    """Create the D-Bus interface class."""
    _, _, service_interface, method, signal = _load_dbus_next()
    from dbus_next import DBusError

    class AsusControlInterface(service_interface):  # type: ignore[misc, valid-type]
        """D-Bus service exposing status and profile controls."""

        def __init__(self) -> None:
            super().__init__(INTERFACE_NAME)
            self.daemon = daemon
            self.controller = daemon.controller if daemon else PlatformProfileController()
            self.bus_kind = bus_kind

        @method()
        def GetStatusJson(self) -> "s":
            try:
                status = collect_status(self.controller)
                return json.dumps(status.to_dict(), ensure_ascii=False)
            except Exception as exc:
                raise DBusError("org.asuslinux.Control.Error.Internal", str(exc))

        @method()
        def GetProfile(self) -> "s":
            try:
                return self.controller.get_profile().value
            except Exception as exc:
                raise DBusError("org.asuslinux.Control.Error.Internal", str(exc))

        @method()
        def SetProfile(self, profile: "s") -> "b":
            try:
                next_profile = Profile.from_string(profile)
                
                # Check Polkit if running on the system bus
                if self.bus_kind == "system":
                    msg = current_dbus_message.get(None)
                    sender = msg.sender if msg else None
                    check_polkit_auth(sender)

                self.controller.set_profile(next_profile)
                self.ProfileChanged(next_profile.value)
                
                # Automatically switch to MANUAL mode
                from .config import ProfileMode, load_config, save_config
                from dataclasses import replace
                if self.daemon:
                    new_daemon_config = replace(self.daemon.config.daemon, profile_mode=ProfileMode.MANUAL)
                    self.daemon.config = replace(self.daemon.config, daemon=new_daemon_config)
                    save_config(self.daemon.config, self.daemon.config_path)
                else:
                    config = load_config()
                    new_daemon_config = replace(config.daemon, profile_mode=ProfileMode.MANUAL)
                    new_config = replace(config, daemon=new_daemon_config)
                    save_config(new_config)

                self.StatusChanged()
                return True
            except PlatformProfileError as exc:
                raise DBusError("org.asuslinux.Control.Error.PlatformError", str(exc))
            except ValueError as exc:
                raise DBusError("org.asuslinux.Control.Error.InvalidArg", str(exc))

        @method()
        def SetProfileMode(self, mode: "s") -> "b":
            try:
                from .config import ProfileMode, load_config, save_config
                next_mode = ProfileMode(mode.strip().lower())
                
                # Check Polkit if running on the system bus
                if self.bus_kind == "system":
                    msg = current_dbus_message.get(None)
                    sender = msg.sender if msg else None
                    check_polkit_auth(sender)

                from dataclasses import replace
                if self.daemon:
                    new_daemon_config = replace(self.daemon.config.daemon, profile_mode=next_mode)
                    self.daemon.config = replace(self.daemon.config, daemon=new_daemon_config)
                    save_config(self.daemon.config, self.daemon.config_path)
                else:
                    config = load_config()
                    new_daemon_config = replace(config.daemon, profile_mode=next_mode)
                    new_config = replace(config, daemon=new_daemon_config)
                    save_config(new_config)

                self.StatusChanged()
                return True
            except Exception as exc:
                raise DBusError("org.asuslinux.Control.Error.Internal", str(exc))

        @method()
        def GetProfileMode(self) -> "s":
            try:
                if self.daemon:
                    return self.daemon.config.daemon.profile_mode.value
                from .config import load_config
                return load_config().daemon.profile_mode.value
            except Exception as exc:
                raise DBusError("org.asuslinux.Control.Error.Internal", str(exc))

        @method()
        def SaveConfigJson(self, config_json: "s") -> "b":
            try:
                # Check Polkit if running on the system bus
                if self.bus_kind == "system":
                    msg = current_dbus_message.get(None)
                    sender = msg.sender if msg else None
                    check_polkit_auth(sender)

                import json
                from .config import AppConfig, BatteryConfig, TemperatureConfig, DaemonConfig, save_config, ProfileMode
                from .profiles import Profile
                
                config_data = json.loads(config_json)
                
                battery = BatteryConfig(
                    on_ac=Profile.from_string(config_data["battery"]["on_ac"]),
                    on_battery=Profile.from_string(config_data["battery"]["on_battery"]),
                    low_battery=Profile.from_string(config_data["battery"]["low_battery"]),
                    low_battery_percent=int(config_data["battery"]["low_battery_percent"]),
                )
                temp = TemperatureConfig(
                    quiet_max=int(config_data["temperature"]["quiet_max"]),
                    balanced_max=int(config_data["temperature"]["balanced_max"]),
                    performance_above=int(config_data["temperature"]["performance_above"]),
                )
                daemon_data = config_data["daemon"]
                
                # Keep current in-memory mode or use default
                current_mode = self.daemon.config.daemon.profile_mode if self.daemon else ProfileMode(daemon_data.get("profile_mode", "auto"))
                
                daemon = DaemonConfig(
                    interval_seconds=float(daemon_data["interval_seconds"]),
                    notify=bool(daemon_data["notify"]),
                    profile_switch_journal=bool(daemon_data["profile_switch_journal"]),
                    log_dir=str(daemon_data["log_dir"]),
                    profile_mode=current_mode,
                    language=str(daemon_data.get("language", "en")),
                    performance_apps=tuple(daemon_data["performance_apps"]),
                )
                
                app_config = AppConfig(battery=battery, temperature=temp, daemon=daemon)
                
                if self.daemon:
                    self.daemon.config = app_config
                    save_config(app_config, self.daemon.config_path)
                else:
                    save_config(app_config)
                
                self.StatusChanged()
                return True
            except Exception as exc:
                raise DBusError("org.asuslinux.Control.Error.Internal", str(exc))

        @method()
        def GetLogsJson(self, limit: "i") -> "s":
            try:
                from .profile_journal import read_profile_switches
                from dataclasses import asdict
                records = read_profile_switches(limit=limit)
                return json.dumps([asdict(r) for r in records], ensure_ascii=False)
            except Exception as exc:
                raise DBusError("org.asuslinux.Control.Error.Internal", str(exc))

        @signal()
        def ProfileChanged(self, profile: "s") -> "s":
            return profile

        @signal()
        def StatusChanged(self) -> "":
            return None

    return AsusControlInterface


async def serve(bus_name: str, bus_kind: str, interface_obj: Any = None) -> None:
    """Run the D-Bus service until interrupted."""
    bus_type, message_bus, _, _, _ = _load_dbus_next()
    selected_bus = bus_type.SYSTEM if bus_kind == "system" else bus_type.SESSION
    
    try:
        bus = await message_bus(bus_type=selected_bus).connect()
    except Exception as exc:
        raise RuntimeError(f"Failed to connect to D-Bus {bus_kind} bus: {exc}")

    obj = interface_obj or build_interface_class(bus_kind)()
    bus.export(OBJECT_PATH, obj)
    
    try:
        await bus.request_name(bus_name)
    except Exception as exc:
        raise RuntimeError(f"Failed to request name '{bus_name}' on {bus_kind} bus: {exc}")

    # Keep running
    await asyncio.Future()


def build_parser() -> argparse.ArgumentParser:
    """Build D-Bus service argument parser."""
    parser = argparse.ArgumentParser(description="ASUS Control D-Bus API")
    parser.add_argument("--bus-name", default=BUS_NAME)
    parser.add_argument("--bus", choices=("session", "system"), default="session")
    return parser


def main() -> int:
    """D-Bus service entry point."""
    args = build_parser().parse_args()
    return main_from_cli(bus_kind=args.bus, bus_name=args.bus_name)


def main_from_cli(bus_kind: str, bus_name: str) -> int:
    """Run the D-Bus service from the main fan CLI."""
    try:
        asyncio.run(serve(bus_name=bus_name, bus_kind=bus_kind))
    except KeyboardInterrupt:
        return 130
    except RuntimeError as exc:
        print(f"Error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
