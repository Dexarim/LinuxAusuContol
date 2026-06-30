"""Hardware Abstraction Layer for laptop profiles and monitoring."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from .profiles import Profile, PlatformProfilePaths, PlatformProfileError
from .monitor import HardwareStatus, get_hardware_status

class HardwareProvider(ABC):
    """Abstract base class for laptop hardware control and monitoring."""

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of the hardware provider."""

    @abstractmethod
    def is_compatible(self) -> bool:
        """Check if this provider is compatible with the current system."""

    @abstractmethod
    def get_available_profiles(self) -> List[Profile]:
        """Return the list of available profiles."""

    @abstractmethod
    def get_profile(self) -> Profile:
        """Get the active profile."""

    @abstractmethod
    def set_profile(self, profile: Profile) -> None:
        """Set the active profile."""

    def get_hardware_status(self) -> HardwareStatus:
        """Default hardware status monitoring (uses generic hwmon reading)."""
        return get_hardware_status()


class AsusHardwareProvider(HardwareProvider):
    """Hardware provider for ASUS laptops using asus-nb-wmi."""

    SYS_ROOT = Path("/sys/devices/platform/asus-nb-wmi")

    def get_name(self) -> str:
        return "ASUS (asus-nb-wmi)"

    def is_compatible(self) -> bool:
        candidates = list(self.SYS_ROOT.glob("platform-profile/platform-profile-*"))
        for root in candidates:
            if (root / "profile").exists() and (root / "choices").exists():
                return True
        return False

    def _get_paths(self) -> PlatformProfilePaths:
        candidates = sorted(self.SYS_ROOT.glob("platform-profile/platform-profile-*"))
        for root in candidates:
            profile = root / "profile"
            choices = root / "choices"
            if profile.exists() and choices.exists():
                return PlatformProfilePaths(root=root, profile=profile, choices=choices)
        raise PlatformProfileError("ASUS platform-profile interface not found.")

    def get_available_profiles(self) -> List[Profile]:
        paths = self._get_paths()
        try:
            choices = paths.choices.read_text(encoding="utf-8").split()
        except OSError as exc:
            raise PlatformProfileError(f"Cannot read choices: {exc}")
        
        profiles = []
        for choice in choices:
            try:
                profiles.append(Profile.from_string(choice))
            except ValueError:
                continue
        return profiles

    def get_profile(self) -> Profile:
        paths = self._get_paths()
        try:
            val = paths.profile.read_text(encoding="utf-8").strip()
            return Profile.from_string(val)
        except OSError as exc:
            raise PlatformProfileError(f"Cannot read active profile: {exc}")

    def set_profile(self, profile: Profile) -> None:
        paths = self._get_paths()
        available = self.get_available_profiles()
        if profile not in available:
            choices = ", ".join(p.value for p in available)
            raise PlatformProfileError(f"Profile '{profile.value}' not available. Available: {choices}")
        try:
            paths.profile.write_text(f"{profile.value}\n", encoding="utf-8")
        except PermissionError as exc:
            raise PlatformProfileError(
                f"Permission denied writing to {paths.profile}. Use Polkit/DBus or run as root."
            ) from exc
        except OSError as exc:
            raise PlatformProfileError(f"Cannot write active profile: {exc}")


class GenericHardwareProvider(HardwareProvider):
    """Generic ACPI platform profile provider (supports Lenovo, HP, Dell, etc.)."""

    SYS_DIR = Path("/sys/firmware/acpi")

    def get_name(self) -> str:
        return "Generic ACPI"

    def is_compatible(self) -> bool:
        # Check for generic acpi platform_profile
        profile_file = self.SYS_DIR / "platform_profile"
        choices_file = self.SYS_DIR / "platform_profile_choices"
        return profile_file.exists() and choices_file.exists()

    def get_available_profiles(self) -> List[Profile]:
        choices_file = self.SYS_DIR / "platform_profile_choices"
        try:
            choices = choices_file.read_text(encoding="utf-8").split()
        except OSError as exc:
            raise PlatformProfileError(f"Cannot read generic choices: {exc}")
        
        profiles = []
        for choice in choices:
            try:
                profiles.append(Profile.from_string(choice))
            except ValueError:
                # Map brand-specific profiles to our generic Profile enum if possible, or fallback
                normalized = choice.lower().strip()
                if normalized in ("low-power", "quiet"):
                    profiles.append(Profile.QUIET)
                elif normalized in ("balanced", "medium"):
                    profiles.append(Profile.BALANCED)
                elif normalized in ("performance", "high"):
                    profiles.append(Profile.PERFORMANCE)
        return list(set(profiles))

    def get_profile(self) -> Profile:
        profile_file = self.SYS_DIR / "platform_profile"
        try:
            val = profile_file.read_text(encoding="utf-8").strip().lower()
            if val in ("low-power", "quiet"):
                return Profile.QUIET
            elif val in ("performance", "high"):
                return Profile.PERFORMANCE
            return Profile.BALANCED
        except OSError as exc:
            raise PlatformProfileError(f"Cannot read generic profile: {exc}")

    def set_profile(self, profile: Profile) -> None:
        profile_file = self.SYS_DIR / "platform_profile"
        # Map our profile back to brand-specific if choices list is available
        choices_file = self.SYS_DIR / "platform_profile_choices"
        raw_choices = choices_file.read_text(encoding="utf-8").split() if choices_file.exists() else []
        
        target = profile.value
        # Match target string to choices
        for choice in raw_choices:
            norm = choice.lower().strip()
            if profile == Profile.QUIET and norm in ("low-power", "quiet"):
                target = choice
                break
            elif profile == Profile.BALANCED and norm in ("balanced", "medium"):
                target = choice
                break
            elif profile == Profile.PERFORMANCE and norm in ("performance", "high"):
                target = choice
                break

        try:
            profile_file.write_text(f"{target}\n", encoding="utf-8")
        except PermissionError as exc:
            raise PlatformProfileError(
                f"Permission denied writing to {profile_file}. Use Polkit/DBus or run as root."
            ) from exc
        except OSError as exc:
            raise PlatformProfileError(f"Cannot write generic profile: {exc}")


class HardwareRegistry:
    """Registry to discover and manage the active HardwareProvider."""

    def __init__(self) -> None:
        self.providers: List[HardwareProvider] = [
            AsusHardwareProvider(),
            GenericHardwareProvider(),
        ]
        self._active_provider: HardwareProvider | None = None

    def get_provider(self) -> HardwareProvider:
        """Find the first compatible hardware provider on the system."""
        if self._active_provider is not None:
            return self._active_provider

        for provider in self.providers:
            if provider.is_compatible():
                self._active_provider = provider
                return provider

        # Fallback to Asus anyway to avoid breaking existing setups, but raise warning or log
        self._active_provider = self.providers[0]
        return self._active_provider
