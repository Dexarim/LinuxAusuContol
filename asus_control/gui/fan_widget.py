"""Widget for displaying fan speeds."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QGridLayout, QWidget


class FanWidget(QFrame):
    """Widget showing CPU and GPU fan RPMs."""

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
        icon = QIcon.fromTheme("fan", QIcon(":/icons/fan.png"))
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(24, 24))
        
        title = QLabel(self.tr("Cooling Fans"))
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Grid layout for values
        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(20)
        
        grid.addWidget(QLabel(self.tr("CPU Fan Speed:")), 0, 0)
        self.cpu_fan_val = QLabel(self.tr("N/A"))
        self.cpu_fan_val.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.cpu_fan_val, 0, 1)
        
        grid.addWidget(QLabel(self.tr("GPU Fan Speed:")), 1, 0)
        self.gpu_fan_val = QLabel(self.tr("N/A"))
        self.gpu_fan_val.setStyleSheet("font-weight: bold;")
        grid.addWidget(self.gpu_fan_val, 1, 1)
        
        layout.addLayout(grid)

    def update_status(self, status: dict) -> None:
        cpu = status.get("cpu_fan_rpm")
        gpu = status.get("gpu_fan_rpm")
        
        self.cpu_fan_val.setText(f"{cpu} RPM" if cpu is not None else self.tr("N/A"))
        self.gpu_fan_val.setText(f"{gpu} RPM" if gpu is not None else self.tr("N/A"))
