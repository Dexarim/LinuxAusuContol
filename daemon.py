"""Compatibility wrapper for the packaged daemon."""

from __future__ import annotations

from asus_control.daemon import main


if __name__ == "__main__":
    raise SystemExit(main())
