"""Settings window for editing configurations and managing autostart."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QCheckBox,
    QLineEdit, QFileDialog, QPushButton, QComboBox, QGroupBox, QFormLayout, QMessageBox
)

AUTOSTART_DIR = Path.home() / ".config" / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / "asus-control-gui.desktop"


class SettingsWindow(QWidget):
    """Configuration editor containing daemon, battery, temperature rules, and autostart settings."""

    def __init__(self, view_model: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        
        self._init_ui()
        self.load_settings()
        self.view_model.settings_saved.connect(self.on_settings_saved)

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 1. Daemon settings group
        daemon_group = QGroupBox(self.tr("Daemon Settings"))
        daemon_layout = QFormLayout(daemon_group)
        
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 60)
        self.spin_interval.setSuffix(self.tr(" sec"))
        daemon_layout.addRow(self.tr("Update Interval:"), self.spin_interval)
        
        self.chk_notify = QCheckBox(self.tr("Enable desktop notifications"))
        daemon_layout.addRow(self.chk_notify)
        
        self.chk_journal = QCheckBox(self.tr("Enable profile switch journal"))
        daemon_layout.addRow(self.chk_journal)
        
        self.chk_autostart_gui = QCheckBox(self.tr("Autostart GUI on login"))
        daemon_layout.addRow(self.chk_autostart_gui)
        
        # Log path selection
        log_path_layout = QHBoxLayout()
        self.txt_log_dir = QLineEdit()
        self.btn_browse_log = QPushButton(self.tr("Browse..."))
        self.btn_browse_log.clicked.connect(self.browse_log_dir)
        log_path_layout.addWidget(self.txt_log_dir)
        log_path_layout.addWidget(self.btn_browse_log)
        daemon_layout.addRow(self.tr("Log Directory:"), log_path_layout)
        
        main_layout.addWidget(daemon_group)
        
        # 2. Battery & Power policy group
        battery_group = QGroupBox(self.tr("Power Policy Rules"))
        battery_layout = QFormLayout(battery_group)
        
        self.cmb_on_ac = QComboBox()
        self.cmb_on_battery = QComboBox()
        self.cmb_low_battery = QComboBox()
        for p in ["quiet", "balanced", "performance"]:
            self.cmb_on_ac.addItem(p.capitalize(), p)
            self.cmb_on_battery.addItem(p.capitalize(), p)
            self.cmb_low_battery.addItem(p.capitalize(), p)
            
        battery_layout.addRow(self.tr("Profile on AC Power:"), self.cmb_on_ac)
        battery_layout.addRow(self.tr("Profile on Battery:"), self.cmb_on_battery)
        battery_layout.addRow(self.tr("Low Battery Profile:"), self.cmb_low_battery)
        
        self.spin_low_battery_pct = QSpinBox()
        self.spin_low_battery_pct.setRange(5, 95)
        self.spin_low_battery_pct.setSuffix(" %")
        battery_layout.addRow(self.tr("Low Battery Threshold:"), self.spin_low_battery_pct)
        
        main_layout.addWidget(battery_group)
        
        # 3. Temperature policy rules group
        temp_group = QGroupBox(self.tr("Temperature Threshold Rules"))
        temp_layout = QFormLayout(temp_group)
        
        self.spin_quiet_max = QSpinBox()
        self.spin_quiet_max.setRange(30, 100)
        self.spin_quiet_max.setSuffix(" °C")
        temp_layout.addRow(self.tr("Quiet Max Temp:"), self.spin_quiet_max)
        
        self.spin_balanced_max = QSpinBox()
        self.spin_balanced_max.setRange(30, 100)
        self.spin_balanced_max.setSuffix(" °C")
        temp_layout.addRow(self.tr("Balanced Max Temp:"), self.spin_balanced_max)
        
        self.spin_perf_above = QSpinBox()
        self.spin_perf_above.setRange(30, 100)
        self.spin_perf_above.setSuffix(" °C")
        temp_layout.addRow(self.tr("Performance Above:"), self.spin_perf_above)
        
        main_layout.addWidget(temp_group)
        
        # Buttons
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        self.btn_save = QPushButton(self.tr("Save Changes"))
        self.btn_save.setIcon(QIcon.fromTheme("document-save", QIcon(":/icons/save.png")))
        self.btn_save.clicked.connect(self.save_settings)
        
        actions_layout.addWidget(self.btn_save)
        main_layout.addLayout(actions_layout)

    def load_settings(self) -> None:
        config = self.view_model.fetch_config()
        if not config:
            return
        
        # Daemon
        self.spin_interval.setValue(int(config["daemon"]["interval_seconds"]))
        self.chk_notify.setChecked(bool(config["daemon"]["notify"]))
        self.chk_journal.setChecked(bool(config["daemon"]["profile_switch_journal"]))
        self.txt_log_dir.setText(config["daemon"]["log_dir"])
        
        # Autostart GUI status
        self.chk_autostart_gui.setChecked(AUTOSTART_FILE.exists())
        
        # Battery
        self.cmb_on_ac.setCurrentIndex(self.cmb_on_ac.findData(config["battery"]["on_ac"]))
        self.cmb_on_battery.setCurrentIndex(self.cmb_on_battery.findData(config["battery"]["on_battery"]))
        self.cmb_low_battery.setCurrentIndex(self.cmb_low_battery.findData(config["battery"]["low_battery"]))
        self.spin_low_battery_pct.setValue(int(config["battery"]["low_battery_percent"]))
        
        # Temp
        self.spin_quiet_max.setValue(int(config["temperature"]["quiet_max"]))
        self.spin_balanced_max.setValue(int(config["temperature"]["balanced_max"]))
        self.spin_perf_above.setValue(int(config["temperature"]["performance_above"]))

    def browse_log_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, self.tr("Select Log Directory"), self.txt_log_dir.text())
        if directory:
            self.txt_log_dir.setText(directory)

    def save_settings(self) -> None:
        # Construct config dict
        config = {
            "battery": {
                "on_ac": self.cmb_on_ac.currentData(),
                "on_battery": self.cmb_on_battery.currentData(),
                "low_battery": self.cmb_low_battery.currentData(),
                "low_battery_percent": self.spin_low_battery_pct.value(),
            },
            "temperature": {
                "quiet_max": self.spin_quiet_max.value(),
                "balanced_max": self.spin_balanced_max.value(),
                "performance_above": self.spin_perf_above.value(),
            },
            "daemon": {
                "interval_seconds": float(self.spin_interval.value()),
                "notify": self.chk_notify.isChecked(),
                "profile_switch_journal": self.chk_journal.isChecked(),
                "log_dir": self.txt_log_dir.text().strip(),
                "performance_apps": self.view_model.fetch_config().get("daemon", {}).get("performance_apps", []),
            }
        }
        
        # Update autostart GUI .desktop file
        enabled = self.chk_autostart_gui.isChecked()
        try:
            if enabled:
                AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
                content = f"""[Desktop Entry]
Type=Application
Exec=fan gui
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
Name=ASUS Control GUI
Comment=ASUS laptop profile controller GUI
Icon=preferences-system-power
"""
                AUTOSTART_FILE.write_text(content, encoding="utf-8")
            else:
                if AUTOSTART_FILE.exists():
                    AUTOSTART_FILE.unlink()
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Autostart Error"), self.tr("Failed to modify autostart: {error}").format(error=exc))

        self.btn_save.setEnabled(False)
        self.view_model.save_settings(config)

    def on_settings_saved(self) -> None:
        self.btn_save.setEnabled(True)
        QMessageBox.information(
            self,
            self.tr("Settings Saved"),
            self.tr("Settings saved successfully. Daemon configuration has been reloaded.")
        )
