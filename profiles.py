"""Platform profile management through Linux sysfs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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
    """Read and write ASUS platform profiles."""

    def __init__(self, paths: PlatformProfilePaths | None = None) -> None:
        self.paths = paths or self.discover()

    @staticmethod
    def discover() -> PlatformProfilePaths:
        """Find platform-profile files for asus-nb-wmi."""
        candidates = sorted(
            SYS_PLATFORM_PROFILE_ROOT.glob("platform-profile/platform-profile-*")
        )
        for root in candidates:
            profile = root / "profile"
            choices = root / "choices"
            if profile.exists() and choices.exists():
                return PlatformProfilePaths(root=root, profile=profile, choices=choices)

        raise PlatformProfileError(
            "platform-profile sysfs interface was not found. "
            "Expected /sys/devices/platform/asus-nb-wmi/platform-profile/..."
        )

    def available_profiles(self) -> list[Profile]:
        """Return profiles supported by the current kernel driver."""
        try:
            raw_choices = self.paths.choices.read_text(encoding="utf-8").split()
        except OSError as exc:
            raise PlatformProfileError(f"Cannot read {self.paths.choices}: {exc}") from exc

        profiles: list[Profile] = []
        for value in raw_choices:
            try:
                profiles.append(Profile.from_string(value))
            except ValueError:
                continue
        return profiles

    def get_profile(self) -> Profile:
        """Read the active platform profile."""
        try:
            return Profile.from_string(self.paths.profile.read_text(encoding="utf-8"))
        except OSError as exc:
            raise PlatformProfileError(f"Cannot read {self.paths.profile}: {exc}") from exc

    def set_profile(self, profile: Profile) -> None:
        """Set the active platform profile."""
        available = self.available_profiles()
        if profile not in available:
            values = ", ".join(item.value for item in available) or "none"
            raise PlatformProfileError(
                f"Profile {profile.value!r} is not available. Available: {values}"
            )

        try:
            self.paths.profile.write_text(f"{profile.value}\n", encoding="utf-8")
        except PermissionError as exc:
            raise PlatformProfileError(
                f"Permission denied while writing {self.paths.profile}. "
                "Run with sudo or install a suitable polkit/systemd rule."
            ) from exc
        except OSError as exc:
            raise PlatformProfileError(f"Cannot write {self.paths.profile}: {exc}") from exc


def max_profile(left: Profile, right: Profile) -> Profile:
    """Return the more aggressive profile."""
    return left if PROFILE_PRIORITY[left] >= PROFILE_PRIORITY[right] else right
