"""Main dashboard view coordinating the hardware status cards."""

from __future__ import annotations

from typing import Any
from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout, QScrollArea

from .profile_widget import ProfileWidget
from .resources_widget import ResourcesWidget
from .battery_widget import BatteryWidget
from .temperatures_widget import TemperaturesWidget
from .fan_widget import FanWidget


class DashboardWidget(QWidget):
    """Dashboard container laying out all card sub-widgets in a grid."""

    def __init__(self, view_model: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view_model = view_model
        
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Scroll area in case screen size is small
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(15)
        
        # Instantiate widgets
        self.profile_card = ProfileWidget(self.view_model)
        self.resources_card = ResourcesWidget(self.view_model)
        self.battery_card = BatteryWidget(self.view_model)
        self.temps_card = TemperaturesWidget(self.view_model)
        self.fans_card = FanWidget(self.view_model)
        
        # Add widgets to grid layout
        grid.addWidget(self.profile_card, 0, 0, 1, 2)
        grid.addWidget(self.resources_card, 1, 0)
        grid.addWidget(self.battery_card, 1, 1)
        grid.addWidget(self.temps_card, 2, 0)
        grid.addWidget(self.fans_card, 2, 1)
        
        scroll.setWidget(container)
        main_layout.addWidget(scroll)
