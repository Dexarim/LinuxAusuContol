"""Optional D-Bus API for future graphical frontends."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from profiles import PlatformProfileController, Profile
from status import collect_status


BUS_NAME = "org.asuslinux.Control"
OBJECT_PATH = "/org/asuslinux/Control"
INTERFACE_NAME = "org.asuslinux.Control"


def _load_dbus_next() -> tuple[object, object, object, object]:
    try:
        from dbus_next import BusType
        from dbus_next.aio import MessageBus
        from dbus_next.service import ServiceInterface, method, signal
    except ImportError as exc:
        raise RuntimeError(
            "dbus-next is required for D-Bus support. Install requirements.txt first."
        ) from exc
    return BusType, MessageBus, ServiceInterface, method, signal


def build_interface_class() -> type:
    """Create the D-Bus interface class after importing dbus-next."""
    _bus_type, _message_bus, service_interface, method, signal = _load_dbus_next()

    class AsusControlInterface(service_interface):  # type: ignore[misc, valid-type]
        """D-Bus service exposing status and profile controls."""

        def __init__(self) -> None:
            super().__init__(INTERFACE_NAME)
            self.controller = PlatformProfileController()

        @method()
        def GetStatusJson(self) -> "s":
            return json.dumps(collect_status(self.controller).to_dict(), ensure_ascii=False)

        @method()
        def GetProfile(self) -> "s":
            return self.controller.get_profile().value

        @method()
        def SetProfile(self, profile: "s") -> "b":
            next_profile = Profile.from_string(profile)
            self.controller.set_profile(next_profile)
            self.ProfileChanged(next_profile.value)
            return True

        @signal()
        def ProfileChanged(self, profile: "s") -> "s":
            return profile

    return AsusControlInterface


async def serve(bus_name: str, bus_kind: str) -> None:
    """Run the D-Bus service until interrupted."""
    bus_type, message_bus, _service_interface, _method, _signal = _load_dbus_next()
    selected_bus = bus_type.SYSTEM if bus_kind == "system" else bus_type.SESSION
    bus = await message_bus(bus_type=selected_bus).connect()
    interface_class = build_interface_class()
    bus.export(OBJECT_PATH, interface_class())
    await bus.request_name(bus_name)
    await asyncio.Future()


def build_parser() -> argparse.ArgumentParser:
    """Build D-Bus service argument parser."""
    parser = argparse.ArgumentParser(description="ASUS Control D-Bus API")
    parser.add_argument("--bus-name", default=BUS_NAME)
    parser.add_argument("--bus", choices=("session", "system"), default="session")
    parser.add_argument(
        "--config",
        type=Path,
        help="Reserved for future D-Bus policy configuration.",
    )
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
