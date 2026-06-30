"""Widget for choosing the active platform profile and auto/manual modes."""

from __future__ import annotations

from typing import Any
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QCheckBox, QWidget


class ProfileWidget(QFrame):
    """Widget allowing the user to select Quiet, Balanced, or Performance profile and toggle Auto Mode."""

    def __init__(self, view_model: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        self._init_ui()
        
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

        # Auto/Manual mode toggle
        self.chk_auto = QCheckBox(self.tr("Automatic Profile Switching (Auto Mode)"))
        self.chk_auto.setStyleSheet("margin-top: 5px;")
        self.chk_auto.clicked.connect(self.toggle_auto_mode)
        layout.addWidget(self.chk_auto)

    def set_profile(self, profile: str) -> None:
        self.setEnabled(False)
        self.view_model.set_profile(profile)

    def toggle_auto_mode(self, checked: bool) -> None:
        self.setEnabled(False)
        mode = "auto" if checked else "manual"
        self.view_model.set_profile_mode(mode)

    def update_active_profile(self, profile: str) -> None:
        self.setEnabled(True)
        
        self.btn_quiet.setChecked(False)
        self.btn_balanced.setChecked(False)
        self.btn_performance.setChecked(False)
        
        if profile == "quiet":
            self.btn_quiet.setChecked(True)
        elif profile == "balanced":
            self.btn_balanced.setChecked(True)
        elif profile == "performance":
            self.btn_performance.setChecked(True)

    def update_status(self, status: dict) -> None:
        profile = status.get("profile", "")
        self.update_active_profile(profile)
        
        # Update Auto Mode checkbox
        mode = status.get("profile_mode", "auto")
        is_auto = (mode == "auto")
        
        self.chk_auto.blockSignals(True)
        self.chk_auto.setChecked(is_auto)
        self.chk_auto.blockSignals(False)
        self.setEnabled(True)
