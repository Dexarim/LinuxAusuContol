"""Desktop notification helpers."""

from __future__ import annotations

import subprocess


def notify_send(title: str, message: str, enabled: bool = True) -> None:
    """Send a desktop notification through notify-send when available."""
    if not enabled:
        return
    try:
        subprocess.run(
            ["notify-send", title, message],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return
