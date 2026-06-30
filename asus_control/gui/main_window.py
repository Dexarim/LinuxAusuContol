"""Main Window container for the ASUS Control GUI application."""

from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QWidget, QStatusBar, QMessageBox, QLabel
)

from .view_model import AsusControlViewModel
from .dashboard import DashboardWidget
from .settings_window import SettingsWindow
from .logs_window import LogsWindow


class MainWindow(QMainWindow):
    """Primary application window containing tabs for Dashboard, Settings, and Logs."""

    def __init__(self) -> None:
        super().__init__()
        self.view_model = AsusControlViewModel()
        
        self.setWindowIcon(QIcon.fromTheme("preferences-system-power", QIcon(":/icons/app.png")))
        self.resize(800, 600)
        
        self._init_ui()
        self._init_timer()
        
        # Subscribe to error signal
        self.view_model.error_occurred.connect(self.show_error)
        self.view_model.settings_saved.connect(self.on_settings_saved)
        
        # Initial refresh
        self.view_model.trigger_refresh()

    def _init_ui(self) -> None:
        # Update title based on D-Bus client mode or fallback
        mode_str = self.tr("D-Bus Mode") if self.view_model.use_dbus else self.tr("Direct Mode")
        self.setWindowTitle(f"ASUS Control ({mode_str})")
        
        # Central widget and tabs
        tabs = QTabWidget()
        
        self.dashboard_tab = DashboardWidget(self.view_model)
        self.settings_tab = SettingsWindow(self.view_model)
        self.logs_tab = LogsWindow(self.view_model)
        
        tabs.addTab(self.dashboard_tab, QIcon.fromTheme("utilities-system-monitor"), self.tr("Dashboard"))
        tabs.addTab(self.logs_tab, QIcon.fromTheme("utilities-log-viewer"), self.tr("Logs"))
        tabs.addTab(self.settings_tab, QIcon.fromTheme("preferences-system"), self.tr("Settings"))
        
        self.setCentralWidget(tabs)
        
        # Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.status_lbl = QLabel(self.tr("Monitoring active..."))
        self.status_bar.addWidget(self.status_lbl)
        
        # Listen to fetched status to update status bar
        self.view_model.status_fetched.connect(self.update_status_bar)

    def _init_timer(self) -> None:
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.view_model.trigger_refresh)
        
        # Load refresh interval from config (default to 5 seconds)
        config = self.view_model.fetch_config()
        interval = 5.0
        if config and "daemon" in config:
            interval = float(config["daemon"]["interval_seconds"])
            
        self.timer.start(int(interval * 1000))

    def show_error(self, message: str) -> None:
        """Show error message dialog."""
        # Print to stderr for console visibility
        import sys
        print(f"GUI Error: {message}", file=sys.stderr)
        
        self.status_lbl.setText(self.tr("Error: {error}").format(error=message))
        self.status_lbl.setStyleSheet("color: red;")
        
        # Stop spamming dialog box on every timer tick, only show dialog box for major errors if needed
        # We will just show a nice QMessageBox if we try to set a profile and it fails
        # So we can keep it in the status bar for background errors (like a sleeping GPU)

    def update_status_bar(self, status: dict) -> None:
        self.status_lbl.setStyleSheet("")
        profile = status.get("profile", "").upper()
        power = status.get("power", "DC").upper()
        bat = status.get("battery_percent")
        bat_str = f" ({bat}%)" if bat is not None else ""
        
        self.status_lbl.setText(
            self.tr("Active Profile: {profile} | Power: {power}{battery}").format(
                profile=profile, power=power, battery=bat_str
            )
        )

    def on_settings_saved(self) -> None:
        """Restart timer with new interval value if changed."""
        config = self.view_model.fetch_config()
        if config and "daemon" in config:
            interval = float(config["daemon"]["interval_seconds"])
            self.timer.setInterval(int(interval * 1000))
