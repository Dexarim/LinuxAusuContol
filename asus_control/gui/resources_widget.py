"""Widget for displaying system resource utilization (CPU, RAM, GPUs)."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QGridLayout, QWidget


class ResourcesWidget(QFrame):
    """Widget showing CPU, RAM, and GPU usage metrics."""

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
        icon = QIcon.fromTheme("utilities-system-monitor", QIcon(":/icons/monitor.png"))
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(24, 24))
        
        title = QLabel(self.tr("System Resources"))
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Grid layout for progress bars
        grid = QGridLayout()
        grid.setVerticalSpacing(12)
        grid.setHorizontalSpacing(15)
        
        # CPU
        grid.addWidget(QLabel(self.tr("CPU Usage:")), 0, 0)
        self.cpu_progress = QProgressBar()
        self.cpu_progress.setRange(0, 100)
        grid.addWidget(self.cpu_progress, 0, 1)
        
        # RAM
        grid.addWidget(QLabel(self.tr("RAM Usage:")), 1, 0)
        self.ram_progress = QProgressBar()
        self.ram_progress.setRange(0, 100)
        grid.addWidget(self.ram_progress, 1, 1)
        
        # AMD GPU
        grid.addWidget(QLabel(self.tr("AMD GPU:")), 2, 0)
        self.amd_progress = QProgressBar()
        self.amd_progress.setRange(0, 100)
        grid.addWidget(self.amd_progress, 2, 1)
        
        # NVIDIA GPU
        grid.addWidget(QLabel(self.tr("NVIDIA GPU:")), 3, 0)
        self.nv_progress = QProgressBar()
        self.nv_progress.setRange(0, 100)
        grid.addWidget(self.nv_progress, 3, 1)
        
        # NVIDIA Status Info
        self.nv_status_label = QLabel(self.tr("NVIDIA State: N/A"))
        self.nv_status_label.setStyleSheet("font-size: 11px; color: gray;")
        
        layout.addLayout(grid)
        layout.addWidget(self.nv_status_label)

    def update_status(self, status: dict) -> None:
        cpu = status.get("cpu_usage_percent")
        ram = status.get("ram_usage_percent")
        amd = status.get("amd_gpu_usage_percent")
        nv_gpu = status.get("nvidia_gpu_usage_percent")
        nv_state = status.get("nvidia_status")
        
        # CPU
        if cpu is not None:
            self.cpu_progress.setValue(int(cpu))
            self.cpu_progress.setEnabled(True)
            self.cpu_progress.setFormat("%p%")
        else:
            self.cpu_progress.setValue(0)
            self.cpu_progress.setEnabled(False)
            self.cpu_progress.setFormat(self.tr("N/A"))
            
        # RAM
        if ram is not None:
            self.ram_progress.setValue(int(ram))
            self.ram_progress.setEnabled(True)
            self.ram_progress.setFormat("%p%")
        else:
            self.ram_progress.setValue(0)
            self.ram_progress.setEnabled(False)
            self.ram_progress.setFormat(self.tr("N/A"))
            
        # AMD
        if amd is not None:
            self.amd_progress.setValue(amd)
            self.amd_progress.setEnabled(True)
            self.amd_progress.setFormat("%p%")
        else:
            self.amd_progress.setValue(0)
            self.amd_progress.setEnabled(False)
            self.amd_progress.setFormat(self.tr("N/A"))
            
        # NVIDIA GPU
        if nv_gpu is not None:
            self.nv_progress.setValue(nv_gpu)
            self.nv_progress.setEnabled(True)
            self.nv_progress.setFormat("%p%")
        else:
            self.nv_progress.setValue(0)
            self.nv_progress.setEnabled(False)
            self.nv_progress.setFormat(self.tr("N/A"))
            
        # NVIDIA Status text
        if nv_state:
            self.nv_status_label.setText(self.tr("NVIDIA State: {state}").format(state=nv_state))
        else:
            self.nv_status_label.setText(self.tr("NVIDIA State: Not Detected"))
