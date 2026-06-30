"""ViewModel for the ASUS Control GUI, implementing MVVM architecture."""

from __future__ import annotations

import json
from typing import Any, Dict, List
from PySide6.QtCore import QObject, Signal, Slot, QThreadPool, QRunnable
from PySide6.QtDBus import QDBusConnection, QDBusInterface, QDBusMessage


class StatusFetcher(QRunnable):
    """Runnable to fetch status in a background thread."""

    def __init__(self, view_model: AsusControlViewModel) -> None:
        super().__init__()
        self.view_model = view_model

    def run(self) -> None:
        try:
            status_data = self.view_model._fetch_status_impl()
            self.view_model.status_fetched.emit(status_data)
        except Exception as exc:
            self.view_model.error_occurred.emit(str(exc))


class ProfileSetter(QRunnable):
    """Runnable to set active profile in a background thread to prevent GUI lock during auth."""

    def __init__(self, view_model: AsusControlViewModel, profile: str) -> None:
        super().__init__()
        self.view_model = view_model
        self.profile = profile

    def run(self) -> None:
        try:
            self.view_model._set_profile_impl(self.profile)
            self.view_model.profile_changed.emit(self.profile)
            # Fetch status immediately to reflect change
            self.view_model.trigger_refresh()
        except Exception as exc:
            # Check if it is a Polkit / Permission error
            err_msg = str(exc)
            if "NotAuthorized" in err_msg or "Permission denied" in err_msg:
                self.view_model.error_occurred.emit(
                    "Polkit authorization denied. Profile change was not applied."
                )
            else:
                self.view_model.error_occurred.emit(err_msg)


class SettingsSaver(QRunnable):
    """Runnable to save configuration and restart daemon if necessary."""

    def __init__(self, view_model: AsusControlViewModel, config_data: Dict[str, Any]) -> None:
        super().__init__()
        self.view_model = view_model
        self.config_data = config_data

    def run(self) -> None:
        try:
            self.view_model._save_settings_impl(self.config_data)
            self.view_model.settings_saved.emit()
            self.view_model.trigger_refresh()
        except Exception as exc:
            self.view_model.error_occurred.emit(f"Failed to save settings: {exc}")


class AsusControlViewModel(QObject):
    """Main ViewModel managing D-Bus signals, fallbacks, and backend calls."""

    status_fetched = Signal(dict)
    profile_changed = Signal(str)
    error_occurred = Signal(str)
    settings_saved = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.use_dbus = False
        self.dbus_interface: QDBusInterface | None = None
        self.direct_backend: Any = None
        
        self.thread_pool = QThreadPool.globalInstance()
        
        # Connect to D-Bus system bus
        connection = QDBusConnection.systemBus()
        if connection.isConnected():
            self.dbus_interface = QDBusInterface(
                "org.asuslinux.Control",
                "/org/asuslinux/Control",
                "org.asuslinux.Control",
                connection,
                self
            )
            if self.dbus_interface.isValid():
                self.use_dbus = True
                # Connect to StatusChanged signal on System Bus
                connection.connect(
                    "org.asuslinux.Control",
                    "/org/asuslinux/Control",
                    "org.asuslinux.Control",
                    "StatusChanged",
                    self,
                    "on_dbus_status_changed"
                )
                # Connect to ProfileChanged signal on System Bus
                connection.connect(
                    "org.asuslinux.Control",
                    "/org/asuslinux/Control",
                    "org.asuslinux.Control",
                    "ProfileChanged",
                    self,
                    "on_dbus_profile_changed"
                )

        if not self.use_dbus:
            # Fallback to direct backend
            from asus_control.gui_adapter import AsusControlBackend
            self.direct_backend = AsusControlBackend()

    def trigger_refresh(self) -> None:
        """Trigger background status fetch."""
        self.thread_pool.start(StatusFetcher(self))

    def set_profile(self, profile: str) -> None:
        """Asynchronously change platform profile."""
        self.thread_pool.start(ProfileSetter(self, profile))

    def save_settings(self, config_data: Dict[str, Any]) -> None:
        """Asynchronously save settings to config file."""
        self.thread_pool.start(SettingsSaver(self, config_data))

    def fetch_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch logs from D-Bus or directly."""
        if self.use_dbus and self.dbus_interface:
            reply = self.dbus_interface.call("GetLogsJson", limit)
            if reply.type() == QDBusMessage.MessageType.ReplyMessage:
                return json.loads(reply.arguments()[0])
        
        # Fallback to reading directly via backend
        try:
            from asus_control.profile_journal import read_profile_switches
            from dataclasses import asdict
            records = read_profile_switches(limit=limit)
            return [asdict(r) for r in records]
        except Exception as exc:
            self.error_occurred.emit(f"Failed to fetch logs: {exc}")
            return []

    def fetch_config(self) -> Dict[str, Any]:
        """Fetch current configuration."""
        try:
            from asus_control.config import load_config
            config = load_config()
            return {
                "battery": {
                    "on_ac": config.battery.on_ac.value,
                    "on_battery": config.battery.on_battery.value,
                    "low_battery": config.battery.low_battery.value,
                    "low_battery_percent": config.battery.low_battery_percent,
                },
                "temperature": {
                    "quiet_max": config.temperature.quiet_max,
                    "balanced_max": config.temperature.balanced_max,
                    "performance_above": config.temperature.performance_above,
                },
                "daemon": {
                    "interval_seconds": config.daemon.interval_seconds,
                    "notify": config.daemon.notify,
                    "profile_switch_journal": config.daemon.profile_switch_journal,
                    "log_dir": config.daemon.log_dir,
                    "performance_apps": list(config.daemon.performance_apps),
                }
            }
        except Exception as exc:
            self.error_occurred.emit(f"Failed to load config: {exc}")
            return {}

    # --- Internal Implementation methods (run in background threads) ---

    def _fetch_status_impl(self) -> Dict[str, Any]:
        if self.use_dbus and self.dbus_interface:
            reply = self.dbus_interface.call("GetStatusJson")
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                raise RuntimeError(reply.errorMessage())
            return json.loads(reply.arguments()[0])
        
        # Fallback
        return self.direct_backend.status().to_dict()

    def _set_profile_impl(self, profile: str) -> None:
        if self.use_dbus and self.dbus_interface:
            reply = self.dbus_interface.call("SetProfile", profile)
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                raise RuntimeError(reply.errorMessage())
            if not reply.arguments()[0]:
                raise RuntimeError("Failed to set profile over D-Bus")
        else:
            self.direct_backend.set_profile(profile)

    def _save_settings_impl(self, config_data: Dict[str, Any]) -> None:
        from asus_control.config import AppConfig, BatteryConfig, TemperatureConfig, DaemonConfig, save_config
        from asus_control.profiles import Profile
        
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
        daemon = DaemonConfig(
            interval_seconds=float(config_data["daemon"]["interval_seconds"]),
            notify=bool(config_data["daemon"]["notify"]),
            profile_switch_journal=bool(config_data["daemon"]["profile_switch_journal"]),
            log_dir=str(config_data["daemon"]["log_dir"]),
            performance_apps=tuple(config_data["daemon"]["performance_apps"]),
        )
        
        app_config = AppConfig(battery=battery, temperature=temp, daemon=daemon)
        save_config(app_config)
        
        # Try to reload daemon via systemd (systemctl kill -s HUP asus-control.service)
        try:
            import subprocess
            subprocess.run(
                ["systemctl", "kill", "-s", "HUP", "asus-control.service"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

    # --- Slots connected to DBus Signals ---

    @Slot()
    def on_dbus_status_changed(self) -> None:
        """Trigger update when D-Bus signals that status changed."""
        self.trigger_refresh()

    @Slot(str)
    def on_dbus_profile_changed(self, profile: str) -> None:
        """Handle D-Bus ProfileChanged signal."""
        self.profile_changed.emit(profile)
