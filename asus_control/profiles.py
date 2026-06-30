"""Platform profile management through Linux sysfs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hardware_abstraction import HardwareProvider


SYS_PLATFORM_PROFILE_ROOT = Path("/sys/devices/platform/asus-nb-wmi")


class Profile(str, Enum):
    """Supported Linux platform profiles."""

    QUIET = "quiet"
    BALANCED = "balanced"
    PERFORMANCE = "performance"

    @classmethod
    def from_string(cls, value: str) -> "Profile":
        """Convert a string to a Profile enum."""
        normalized = value.strip().lower()
        for profile in cls:
            if profile.value == normalized:
                return profile
        raise ValueError(f"Unsupported profile: {value}")


PROFILE_PRIORITY: dict[Profile, int] = {
    Profile.QUIET: 0,
    Profile.BALANCED: 1,
    Profile.PERFORMANCE: 2,
}


@dataclass(frozen=True)
class PlatformProfilePaths:
    """Paths exposed by platform-profile sysfs."""

    root: Path
    profile: Path
    choices: Path


class PlatformProfileError(RuntimeError):
    """Raised when platform-profile cannot be read or written."""


class PlatformProfileController:
    """Read and write platform profiles (delegates to the active HardwareProvider)."""

    def __init__(self, provider: HardwareProvider | None = None) -> None:
        from .hardware_abstraction import HardwareRegistry
        self.provider = provider or HardwareRegistry().get_provider()

    def available_profiles(self) -> list[Profile]:
        """Return profiles supported by the current hardware provider."""
        return self.provider.get_available_profiles()

    def get_profile(self) -> Profile:
        """Read the active platform profile."""
        return self.provider.get_profile()

    def set_profile(self, profile: Profile) -> None:
        """Set the active platform profile."""
        self.provider.set_profile(profile)


def max_profile(left: Profile, right: Profile) -> Profile:
    """Return the more aggressive profile."""
    return left if PROFILE_PRIORITY[left] >= PROFILE_PRIORITY[right] else right
