"""Widget for choosing the active platform profile."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QMessageBox, QWidget


class ProfileWidget(QFrame):
    """Widget allowing the user to select Quiet, Balanced, or Performance profile."""

    def __init__(self, view_model: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        
        # Native styling
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        self._init_ui()
        
        # Bind events
        self.view_model.status_fetched.connect(self.update_status)
        self.view_model.profile_changed.connect(self.update_active_profile)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        header_layout = QHBoxLayout()
        icon = QIcon.fromTheme("preferences-system-power", QIcon(":/icons/power.png"))
        icon_label = QLabel()
        icon_label.setPixmap(icon.pixmap(24, 24))
        
        self.title_label = QLabel(self.tr("Platform Profile"))
        self.title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Buttons layout
        btn_layout = QHBoxLayout()
        
        self.btn_quiet = QPushButton(self.tr("Quiet"))
        self.btn_quiet.setIcon(QIcon.fromTheme("power-profile-power-saver", QIcon(":/icons/quiet.png")))
        self.btn_quiet.setCheckable(True)
        self.btn_quiet.clicked.connect(lambda: self.set_profile("quiet"))
        
        self.btn_balanced = QPushButton(self.tr("Balanced"))
        self.btn_balanced.setIcon(QIcon.fromTheme("power-profile-balanced", QIcon(":/icons/balanced.png")))
        self.btn_balanced.setCheckable(True)
        self.btn_balanced.clicked.connect(lambda: self.set_profile("balanced"))
        
        self.btn_performance = QPushButton(self.tr("Performance"))
        self.btn_performance.setIcon(QIcon.fromTheme("power-profile-performance", QIcon(":/icons/performance.png")))
        self.btn_performance.setCheckable(True)
        self.btn_performance.clicked.connect(lambda: self.set_profile("performance"))
        
        btn_layout.addWidget(self.btn_quiet)
        btn_layout.addWidget(self.btn_balanced)
        btn_layout.addWidget(self.btn_performance)
        layout.addLayout(btn_layout)

    def set_profile(self, profile: str) -> None:
        # Disable buttons temporarily during setting
        self.setEnabled(False)
        self.view_model.set_profile(profile)

    def update_active_profile(self, profile: str) -> None:
        self.setEnabled(True)
        
        # Uncheck all
        self.btn_quiet.setChecked(False)
        self.btn_balanced.setChecked(False)
        self.btn_performance.setChecked(False)
        
        # Highlight active
        if profile == "quiet":
            self.btn_quiet.setChecked(True)
        elif profile == "balanced":
            self.btn_balanced.setChecked(True)
        elif profile == "performance":
            self.btn_performance.setChecked(True)

    def update_status(self, status: dict) -> None:
        profile = status.get("profile", "")
        self.update_active_profile(profile)
