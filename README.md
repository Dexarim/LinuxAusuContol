# Linux ASUS Control

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)](#)

Linux ASUS Control is an autonomous power profile daemon and graphical control center for ASUS laptops (and other ACPI-compatible laptops) using standard Linux kernel interfaces: `platform-profile`, `hwmon`, and `power_supply`.

It requires no Wine, MyASUS, or proprietary ASUS userspace drivers.

---

## 🚀 Key Features

* **Desktop GUI**: Sleek PySide6 / Qt6 dashboard that adapts to KDE Plasma Light/Dark themes and provides real-time system monitoring.
* **Hardware Abstraction Layer (HAL)**: Decoupled design supporting both ASUS-specific WMI interfaces (`asus-nb-wmi`) and Generic ACPI platform profiles.
* **CLI Controller**: Fully featured CLI for status querying, JSON export, log viewing, and profile switching.
* **Autonomous Daemon**: Background daemon running an event-driven automation policy to automatically select the optimal profile based on AC state, battery capacity, CPU/GPU temperatures, and running applications (e.g., games).
* **D-Bus System Bus Integration**: Runs as a privileged system bus daemon `org.asuslinux.Control` utilizing Polkit checks for secure profile modifications.
* **Multi-Language Support**: Complete English and Russian localization.
* **KDE Integration**: Desktop notifications via `notify-send`.

---

## 📂 Project Structure

```text
AsusControl/
├── asus_control/
│   ├── gui/                    # PySide6 Qt6 GUI thin client
│   │   ├── translations/       # English & Russian TS/QM files
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── dashboard.py
│   │   ├── view_model.py
│   │   └── ...
│   ├── cli.py                  # CLI Subcommands & Formatters
│   ├── daemon.py               # Asynchronous Background Automation
│   ├── dbus_api.py             # Polkit-authorized D-Bus System Bus
│   ├── hardware_abstraction.py # HAL interface (ASUS vs Generic ACPI)
│   ├── status.py               # Immutable system metrics collectors
│   ├── profiles.py             # Platform profile controller
│   └── ...
├── config/
│   └── config.yaml             # YAML Automation Policy Configuration
├── systemd/
│   ├── asus-control.service    # Systemd daemon service
│   ├── org.asuslinux.Control.conf # D-Bus system policy
│   └── org.asuslinux.control.policy # Polkit action configurations
├── install.sh                  # Interactive system installer script
└── README.md
```

---

## 🛠️ Installation

Clone the repository and run the installation script:
```bash
./install.sh
```
To update an existing installation without overwriting your `config.yaml`:
```bash
./install.sh --update
```

This will:
1. Copy project files to `/opt/asus-control/`
2. Create a virtual environment and install dependencies (`PySide6`, `dbus-next`, `PyYAML`, `rich`)
3. Install system-wide Polkit and D-Bus policies
4. Symlink `/usr/local/bin/fan` to target the virtual environment CLI wrapper
5. Install and enable the systemd unit `asus-control.service`

---

## 💻 CLI Usage

All controls are unified under the `fan` executable.

```bash
# Switch profiles manually (sets mode to MANUAL, disabling daemon automatic triggers)
fan quiet
fan balanced    # (or: fan basic)
fan performance

# Switch back to automatic policy execution
fan auto

# Show current snapshot
fan status

# Live status monitor
fan monitor

# Export current metrics as JSON
fan json

# View profile change logs
fan journal --limit 10
```

---

## 🖥️ Desktop GUI

Launch the graphical dashboard:
```bash
fan gui
```

### GUI Design
* **Dashboard Tab**: Displays a sleek power profile switcher, real-time battery status, system temperatures (CPU, GPU, NVMe SSD), fan speeds, and hardware utilization (CPU, RAM, AMD, NVIDIA).
* **Logs Tab**: Lists the profile switches history with timestamps and reasons.
* **Settings Tab**: Allows editing daemon update intervals, autostart (`~/.config/autostart/asus-control-gui.desktop`), logging directories, notification preferences, AC/battery profile maps, temperature thresholds, and language preferences.
* **Locales**: Toggle between English and Русский from settings.
* **Geometry Preservation**: QSettings preserves window position, sizing, active tab, and splitter positions.

---

## ⚙️ Configuration (`config.yaml`)

The daemon evaluates system state every tick according to rules declared in `/etc/opt/asus-control/config.yaml` or `/opt/asus-control/config/config.yaml`:

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
  interval_seconds: 5.0
  notify: true
  profile_switch_journal: true
  log_dir: ""
  profile_mode: auto          # auto or manual
  language: en                # en or ru
  performance_apps:
    - steam
    - wine
    - lutris
```

---

## 🔒 Security & Polkit

Changing the platform profile requires administrator privileges. Instead of running the GUI as root or using `sudo` aliases, ASUS Control registers a Polkit action `org.asuslinux.control.set-profile`.

When calling `SetProfile` via the D-Bus system service, the caller's bus connection is authorized using `pkcheck`. If you belong to the local active session, the action is allowed without a password prompt.

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
