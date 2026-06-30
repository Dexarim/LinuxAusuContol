"""Widget for displaying battery capacity and power status."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget


class BatteryWidget(QFrame):
    """Widget showing current battery capacity, state, and power source."""

    def __init__(self, view_model: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        self._init_ui()
        self.view_model.status_fetched.connect(self.update_status)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        self.icon_label = QLabel()
        self.icon_label.setPixmap(QIcon.fromTheme("battery", QIcon(":/icons/battery.png")).pixmap(24, 24))
        
        title = QLabel(self.tr("Power & Battery"))
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        header_layout.addWidget(self.icon_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Labels
        info_layout = QHBoxLayout()
        self.source_label = QLabel(self.tr("Source: N/A"))
        self.status_label = QLabel(self.tr("Status: N/A"))
        info_layout.addWidget(self.source_label)
        info_layout.addWidget(self.status_label)
        layout.addLayout(info_layout)

    def update_status(self, status: dict) -> None:
        percent = status.get("battery_percent")
        power_source = status.get("power", "Unknown").upper()
        battery_state = status.get("battery_status", "N/A")
        
        # Update progress bar
        if percent is not None:
            self.progress_bar.setValue(percent)
            self.progress_bar.setEnabled(True)
            self.progress_bar.setFormat(f"%p%")
        else:
            self.progress_bar.setValue(0)
            self.progress_bar.setEnabled(False)
            self.progress_bar.setFormat(self.tr("N/A"))
            
        # Update power source
        self.source_label.setText(self.tr("Source: {source}").format(source=power_source))
        self.status_label.setText(self.tr("Status: {status}").format(status=battery_state))
        
        # Dynamically change battery icon based on charging state
        icon_name = "battery"
        if power_source == "AC":
            icon_name = "battery-charging" if percent is not None and percent < 100 else "battery-ready"
        else:
            if percent is not None:
                if percent <= 20:
                    icon_name = "battery-caution"
                elif percent <= 50:
                    icon_name = "battery-low"
                else:
                    icon_name = "battery-good"
                    
        self.icon_label.setPixmap(QIcon.fromTheme(icon_name, QIcon(":/icons/battery.png")).pixmap(24, 24))
