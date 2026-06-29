"""Command line interface for Linux ASUS Control."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from config import DEFAULT_CONFIG_PATH
from profile_journal import read_profile_switches
from profiles import PlatformProfileController, PlatformProfileError, Profile
from status import ControlStatus, collect_status
from version import APP_NAME, __version__


PROFILE_ALIASES: dict[str, Profile] = {
    "basic": Profile.BALANCED,
}
DEFAULT_INSTALL_DIR = Path("/opt/asus-control")


try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
except ImportError:  # pragma: no cover - optional dependency
    Console = None
    Live = None
    Table = None


def _rich_status_table(status: ControlStatus) -> Any:
    status_map = status.to_dict()
    table = Table(title="ASUS Control", show_header=False)
    table.add_column("Name", style="bold cyan")
    table.add_column("Value", style="bold")
    table.add_row("Profile", str(status_map["profile"]))
    table.add_row("CPU Temp", _format_temp(status_map["cpu_temp_c"]))
    table.add_row("GPU Temp", _format_temp(status_map["gpu_temp_c"]))
    table.add_row("CPU Fan", _format_rpm(status_map["cpu_fan_rpm"]))
    table.add_row("GPU Fan", _format_rpm(status_map["gpu_fan_rpm"]))
    table.add_row("Power", str(status_map["power"]))
    table.add_row("Battery", _format_percent(status_map["battery_percent"]))
    return table


def print_status(status: ControlStatus, use_rich: bool) -> None:
    """Print one complete status snapshot."""
    status_map = status.to_dict()
    if use_rich and Console is not None and Table is not None:
        console = Console()
        console.print(_rich_status_table(status))
        return

    print(f"Profile : {status_map['profile']}")
    print(f"CPU Temp: {_format_temp(status_map['cpu_temp_c'])}")
    print(f"GPU Temp: {_format_temp(status_map['gpu_temp_c'])}")
    print(f"CPU Fan : {_format_rpm(status_map['cpu_fan_rpm'])}")
    print(f"GPU Fan : {_format_rpm(status_map['gpu_fan_rpm'])}")
    print(f"Power   : {status_map['power']}")
    print(f"Battery : {_format_percent(status_map['battery_percent'])}")


def _format_temp(value: float | None) -> str:
    return f"{value:.0f}°C" if value is not None else "N/A"


def _format_rpm(value: int | None) -> str:
    return f"{value} RPM" if value is not None else "N/A"


def _format_percent(value: int | None) -> str:
    return f"{value}%" if value is not None else "N/A"


def print_monitor(
    controller: PlatformProfileController,
    interval: float,
    use_rich: bool,
) -> None:
    """Continuously print compact status once per interval."""
    if use_rich and Live is not None and Table is not None:
        with Live(
            _rich_status_table(collect_status(controller)),
            refresh_per_second=max(1, int(1 / max(interval, 0.1))),
        ) as live:
            while True:
                live.update(_rich_status_table(collect_status(controller)))
                time.sleep(interval)

    while True:
        status = collect_status(controller).to_dict()
        print("\033[2J\033[H", end="")
        print(f"CPU {_format_temp(status['cpu_temp_c'])}")
        print(f"GPU {_format_temp(status['gpu_temp_c'])}")
        print()
        print(f"CPU FAN {_format_rpm(status['cpu_fan_rpm'])}")
        print(f"GPU FAN {_format_rpm(status['gpu_fan_rpm'])}")
        print()
        print(f"Profile {status['profile']}")
        print(f"Power {status['power']}")
        print(f"Battery {_format_percent(status['battery_percent'])}")
        time.sleep(interval)


def _default_update_source() -> Path:
    """Prefer the current source checkout when it contains install.sh."""
    cwd = Path.cwd()
    if (cwd / "install.sh").exists():
        return cwd
    return Path(__file__).resolve().parent


def run_update(args: argparse.Namespace) -> int:
    """Run the installer in update mode."""
    source = args.source.resolve()
    installer = source / "install.sh"
    if not installer.exists():
        print(f"Error: install.sh was not found in {source}", file=sys.stderr)
        return 1

    command = [
        "bash",
        str(installer),
        "--update",
        "--install-dir",
        str(args.install_dir),
    ]
    if args.enable:
        command.append("--enable")
    if args.force_config:
        command.append("--force-config")
    if args.skip_deps:
        command.append("--skip-deps")

    if args.dry_run:
        print(" ".join(command))
        return 0

    return subprocess.run(command, check=False).returncode


def print_journal(limit: int) -> None:
    """Print recent profile switch journal entries."""
    records = read_profile_switches(limit=limit)
    if not records:
        print("No profile switches recorded yet.")
        return
    for record in records:
        print(
            f"{record.timestamp} "
            f"{record.previous_profile} -> {record.new_profile} "
            f"({record.reason})"
        )


def print_version() -> None:
    """Print application version."""
    print(f"{APP_NAME} {__version__}")


def build_parser() -> argparse.ArgumentParser:
    """Build command line parser."""
    parser = argparse.ArgumentParser(
        prog="fan",
        description="Linux ASUS Control for platform-profile and hwmon",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to config.yaml. Reserved for future CLI policy commands.",
    )
    parser.add_argument(
        "--no-rich",
        action="store_true",
        help="Disable Rich output even when Rich is installed.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command")
    for profile in Profile:
        subparsers.add_parser(profile.value, help=f"Switch to {profile.value} mode")
    subparsers.add_parser("basic", help="Alias for balanced mode")
    subparsers.add_parser("status", help="Show current status")
    subparsers.add_parser("version", help="Show application version")
    subparsers.add_parser("json", help="Export current status as JSON")
    journal_parser = subparsers.add_parser("journal", help="Show profile switch journal")
    journal_parser.add_argument("--limit", type=int, default=20)
    monitor_parser = subparsers.add_parser("monitor", help="Watch current status")
    monitor_parser.add_argument("--interval", type=float, default=1.0)
    watch_parser = subparsers.add_parser("watch", help="Alias for monitor")
    watch_parser.add_argument("--interval", type=float, default=1.0)
    dbus_parser = subparsers.add_parser("dbus", help="Run the optional D-Bus API")
    dbus_parser.add_argument("--bus", choices=("session", "system"), default="session")
    dbus_parser.add_argument("--bus-name", default="org.asuslinux.Control")
    update_parser = subparsers.add_parser("update", help="Update installed files")
    update_parser.add_argument(
        "--source",
        type=Path,
        default=_default_update_source(),
        help="Project source directory. Defaults to current directory when it has install.sh.",
    )
    update_parser.add_argument(
        "--install-dir",
        type=Path,
        default=DEFAULT_INSTALL_DIR,
        help="Installed location to update.",
    )
    update_parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable and start asus-control.service after updating.",
    )
    update_parser.add_argument(
        "--force-config",
        action="store_true",
        help="Overwrite installed config.yaml with the source default.",
    )
    update_parser.add_argument(
        "--skip-deps",
        action="store_true",
        help="Do not reinstall Python dependencies.",
    )
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the update command without running it.",
    )
    return parser


def main() -> int:
    """CLI entry point."""
    args = build_parser().parse_args()
    try:
        if args.command is None:
            controller = PlatformProfileController()
            print_status(collect_status(controller), use_rich=not args.no_rich)
            return 0

        if args.command == "version":
            print_version()
            return 0

        if args.command == "update":
            return run_update(args)

        if args.command == "dbus":
            import dbus_api

            return dbus_api.main_from_cli(args.bus, args.bus_name)

        if args.command == "journal":
            print_journal(args.limit)
            return 0

        controller = PlatformProfileController()
        profile_commands = {profile.value for profile in Profile} | set(PROFILE_ALIASES)
        if args.command in profile_commands:
            profile = PROFILE_ALIASES.get(args.command, Profile.from_string(args.command))
            controller.set_profile(profile)
            print(f"Profile changed to {profile.value}")
            return 0

        if args.command == "status":
            print_status(collect_status(controller), use_rich=not args.no_rich)
            return 0

        if args.command == "json":
            print(
                json.dumps(
                    collect_status(controller).to_dict(),
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0

        if args.command in {"monitor", "watch"}:
            print_monitor(
                controller,
                interval=args.interval,
                use_rich=not args.no_rich,
            )
            return 0
    except KeyboardInterrupt:
        return 130
    except PlatformProfileError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
