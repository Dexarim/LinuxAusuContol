"""Widget for displaying profile switch journal logs."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHeaderView
)


class LogsWindow(QWidget):
    """View log journal for profile switches in a spreadsheet-like grid."""

    def __init__(self, view_model: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        
        self._init_ui()
        self.refresh_logs()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        # Header / toolbar
        toolbar = QHBoxLayout()
        icon = QIcon.fromTheme("utilities-log-viewer", QIcon(":/icons/log.png"))
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(24, 24))
        
        title = QLabel(self.tr("Profile Switches Log"))
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        self.btn_refresh = QPushButton(self.tr("Refresh"))
        self.btn_refresh.setIcon(QIcon.fromTheme("view-refresh", QIcon(":/icons/refresh.png")))
        self.btn_refresh.clicked.connect(self.refresh_logs)
        
        toolbar.addWidget(icon_label)
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self.btn_refresh)
        layout.addLayout(toolbar)
        
        # Log Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            self.tr("Timestamp"),
            self.tr("Previous Profile"),
            self.tr("New Profile"),
            self.tr("Reason"),
            self.tr("CPU Temp"),
            self.tr("GPU Temp"),
            self.tr("Power"),
            self.tr("Battery")
        ])
        
        # Expand columns
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents) # Timestamp
        
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)

    def refresh_logs(self) -> None:
        self.btn_refresh.setEnabled(False)
        # We can run fetching directly since it reads a small local file or lightweight DBus method.
        # But we'll do it safely.
        records = self.view_model.fetch_logs(limit=50)
        
        self.table.setRowCount(0)
        for row_idx, record in enumerate(reversed(records)):
            self.table.insertRow(row_idx)
            
            # Format and insert cells
            self.table.setItem(row_idx, 0, QTableWidgetItem(self._format_timestamp(record.get("timestamp", ""))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(record.get("previous_profile", "")).capitalize()))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(record.get("new_profile", "")).capitalize()))
            self.table.setItem(row_idx, 3, QTableWidgetItem(self._translate_reason(record.get("reason", ""))))
            
            cpu = record.get("cpu_temp_c")
            self.table.setItem(row_idx, 4, QTableWidgetItem(f"{cpu:.0f}°C" if cpu is not None else "N/A"))
            
            gpu = record.get("gpu_temp_c")
            self.table.setItem(row_idx, 5, QTableWidgetItem(f"{gpu:.0f}°C" if gpu is not None else "N/A"))
            
            self.table.setItem(row_idx, 6, QTableWidgetItem(str(record.get("power", "N/A")).upper()))
            
            bat = record.get("battery_percent")
            self.table.setItem(row_idx, 7, QTableWidgetItem(f"{bat}%" if bat is not None else "N/A"))
            
        self.btn_refresh.setEnabled(True)

    def _format_timestamp(self, ts: str) -> str:
        if not ts:
            return ""
        # Simply show date/time from ISO string
        try:
            # e.g., 2026-06-30T18:05:00+05:00 -> 2026-06-30 18:05:00
            if "T" in ts:
                date, time_part = ts.split("T")
                time_val = time_part.split("+")[0].split(".")[0]
                return f"{date} {time_val}"
        except Exception:
            pass
        return ts

    def _translate_reason(self, reason: str) -> str:
        mapping = {
            "ac_power": self.tr("AC Connected"),
            "battery_power": self.tr("Battery Mode"),
            "low_battery": self.tr("Low Battery"),
            "performance_app": self.tr("Performance Application"),
            "temperature_performance": self.tr("Temperature (High Performance)"),
            "temperature_balanced": self.tr("Temperature (Balanced)"),
        }
        return mapping.get(reason, reason)
