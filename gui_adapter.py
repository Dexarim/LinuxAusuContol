"""Small facade intended for a future PySide6 GUI."""

from __future__ import annotations

from profiles import PlatformProfileController, Profile
from status import ControlStatus, collect_status


class AsusControlBackend:
    """GUI-friendly wrapper around the core control modules."""

    def __init__(self, controller: PlatformProfileController | None = None) -> None:
        self.controller = controller or PlatformProfileController()

    def status(self) -> ControlStatus:
        """Return the current status for widgets or models."""
        return collect_status(self.controller)

    def set_profile(self, profile: str) -> None:
        """Set the current platform profile from GUI input."""
        self.controller.set_profile(Profile.from_string(profile))
