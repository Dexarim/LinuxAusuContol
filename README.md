# Linux ASUS Control

Linux ASUS Control is a small autonomous control utility for ASUS laptops using
standard Linux kernel interfaces: `platform-profile`, `hwmon`, and
`power_supply`. It is intended for Arch Linux, CachyOS, KDE Plasma 6, and the
ASUS Vivobook M6500QC.

No Wine, MyASUS, or proprietary ASUS userspace drivers are required.

## Features

- CLI profile switching: `quiet`, `balanced`, `performance`
- MyASUS-style `basic` alias for Linux `balanced`
- Status output for profile, temperatures, fans, AC/DC power, and battery
- Live monitor mode
- Rich table output for `status`, `monitor`, and `watch`
- Background daemon with YAML policy
- Automatic profile switching by AC state, low battery, temperature, and running apps
- KDE notifications through `notify-send` when available
- Profile switch journal as JSON Lines
- JSON status export
- Logging to `~/.local/share/asus-control/logs/`
- Optional D-Bus API for future GUI frontends
- GUI-ready backend facade for a future PySide6 application

## Project Layout

```text
asus-control/
├── asus_control/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── daemon.py
│   ├── monitor.py
│   ├── profiles.py
│   ├── battery.py
│   ├── power.py
│   ├── config.py
│   ├── logger.py
│   ├── status.py
│   ├── notifications.py
│   ├── profile_journal.py
│   ├── dbus_api.py
│   ├── gui_adapter.py
│   └── version.py
├── config/
│   └── config.yaml
├── cli.py
├── daemon.py
├── pyproject.toml
├── requirements.txt
├── install.sh
├── systemd/
│   ├── asus-control.service
│   └── asus-control.timer
└── README.md
```

## Installation

Recommended installer:

```bash
chmod +x install.sh
./install.sh
```

Enable and start the daemon immediately:

```bash
./install.sh --enable
```

The installer copies the project to `/opt/asus-control`, creates
`/opt/asus-control/.venv`, installs Python dependencies there, creates the
`fan` command in `/usr/local/bin`, installs systemd units, and runs
`systemctl daemon-reload`.

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

For a system install:

```bash
./install.sh
```

Optional shell alias:

```bash
alias fan='/opt/asus-control/.venv/bin/python /opt/asus-control/cli.py'
```

Direct package execution during development:

```bash
python -m asus_control
python -m asus_control.cli status
python -m asus_control.daemon --once
```

## Usage

Show current status:

```bash
fan
fan status
```

Show version:

```bash
fan version
fan --version
```

Example:

```text
Profile : balanced
CPU Temp: 55°C
GPU Temp: 48°C
CPU Fan : 2850 RPM
GPU Fan : 2200 RPM
Power   : AC
Battery : 100%
```

Switch profiles:

```bash
sudo fan quiet
sudo fan basic
sudo fan balanced
sudo fan performance
```

`basic` is an alias for `balanced`, because Linux `platform-profile` exposes
`quiet`, `balanced`, and `performance` on this laptop.

Live monitor:

```bash
fan monitor
fan watch
```

JSON export:

```bash
fan json
```

Profile switch journal:

```bash
fan journal
fan journal --limit 50
```

Update an installed copy from the current project directory:

```bash
fan update
```

The update command preserves `/opt/asus-control/config/config.yaml` by default.
A fresh default config is saved as `/opt/asus-control/config/config.yaml.example`.

Useful update options:

```bash
fan update --skip-deps
fan update --force-config
fan update --enable
fan update --source /path/to/asus-control --install-dir /opt/asus-control
```

## Configuration

All policy settings live in `config/config.yaml`:

```yaml
battery:
  on_ac: performance
  on_battery: balanced
  low_battery: quiet
  low_battery_percent: 25

temperature:
  quiet_max: 55
  balanced_max: 75
  performance_above: 75

daemon:
  interval_seconds: 5
  notify: true
  profile_switch_journal: true
  performance_apps:
    - steam
    - steamwebhelper
    - prismlauncher
    - blender
    - lutris
    - heroic
    - gamescope
    - wine
    - proton
```

Policy:

- On AC power: use `on_ac`
- On battery below `low_battery_percent`: use `low_battery`
- Otherwise on battery: use `on_battery`
- If CPU or GPU temperature reaches `performance_above`, raise to `performance`
- If configured performance applications are running, raise to `performance`

The daemon only raises profiles for heat or performance apps. It does not lower
below the profile selected by the power and battery policy.

## D-Bus API

The optional D-Bus service is intended for future GUI integration:

```bash
fan dbus --bus session
```

It exports:

- Bus name: `org.asuslinux.Control`
- Object path: `/org/asuslinux/Control`
- Interface: `org.asuslinux.Control`
- Methods: `GetStatusJson`, `GetProfile`, `SetProfile`
- Signal: `ProfileChanged`

For a root-controlled system service, run it on the system bus and add a D-Bus
policy file later. The current implementation keeps the API ready without
forcing a GUI dependency.

## GUI Integration

`asus_control/gui_adapter.py` contains `AsusControlBackend`, a small facade for future
PySide6 widgets or models:

```python
from asus_control.gui_adapter import AsusControlBackend

backend = AsusControlBackend()
status = backend.status()
backend.set_profile("balanced")
```

## systemd

The provided service assumes the project is installed to `/opt/asus-control`.

```bash
sudo cp systemd/asus-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now asus-control.service
```

Check logs:

```bash
journalctl -u asus-control.service -f
tail -f ~/.local/share/asus-control/logs/asus-control.log
```

The timer is included for users who prefer periodic one-shot execution. For the
normal background daemon, the service alone is enough.

## Architecture

- `asus_control/profiles.py` discovers and writes the kernel `platform-profile` sysfs files.
- `asus_control/monitor.py` reads CPU/GPU temperatures and fan RPMs from `hwmon`.
- `asus_control/battery.py` reads battery capacity from `power_supply`.
- `asus_control/power.py` detects AC/DC state from `power_supply`.
- `asus_control/config.py` loads YAML into typed dataclasses.
- `asus_control/status.py` exposes a shared status model for CLI, JSON, D-Bus, and GUI.
- `asus_control/notifications.py` wraps optional KDE notifications through `notify-send`.
- `asus_control/profile_journal.py` stores profile switch records as JSON Lines.
- `asus_control/dbus_api.py` exposes the optional D-Bus service.
- `asus_control/gui_adapter.py` provides a future PySide6-friendly backend facade.
- `asus_control/version.py` stores shared project metadata.
- `asus_control/daemon.py` combines all modules and applies profile policy.
- `asus_control/cli.py` provides the `fan` command interface.
- `asus_control/logger.py` configures standard Python logging.
- Root `cli.py` and `daemon.py` are compatibility wrappers for older commands.

## Safety

The project uses `pathlib`, typed dataclasses, enums, and standard Python
logging. It does not execute shell commands with `shell=True`. `subprocess` is
only used for optional `notify-send` notifications.

Writing `platform-profile` usually requires root privileges:

```bash
echo performance | sudo tee /sys/devices/platform/asus-nb-wmi/platform-profile/platform-profile-0/profile
```

The CLI and daemon perform the same write through Python file I/O, so profile
changes may need `sudo` unless permissions are configured separately.
