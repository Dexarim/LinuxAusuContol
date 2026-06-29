"""Profile switch journal."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from logger import FALLBACK_LOG_DIR, LOG_DIR


JOURNAL_FILE_NAME = "profile-switches.jsonl"


@dataclass(frozen=True)
class ProfileSwitchRecord:
    """One profile switch journal entry."""

    timestamp: str
    previous_profile: str
    new_profile: str
    reason: str
    cpu_temp_c: float | None
    gpu_temp_c: float | None
    power: str
    battery_percent: int | None
    performance_app_running: bool


def _journal_dir() -> Path:
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        return LOG_DIR
    except OSError:
        FALLBACK_LOG_DIR.mkdir(parents=True, exist_ok=True)
        return FALLBACK_LOG_DIR


def append_profile_switch(record: ProfileSwitchRecord) -> Path:
    """Append a profile switch entry as JSON Lines."""
    path = _journal_dir() / JOURNAL_FILE_NAME
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(asdict(record), ensure_ascii=False))
        file.write("\n")
    return path


def read_profile_switches(limit: int = 20) -> list[ProfileSwitchRecord]:
    """Read recent profile switch entries."""
    path = _journal_dir() / JOURNAL_FILE_NAME
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    records: list[ProfileSwitchRecord] = []
    for line in lines[-limit:]:
        try:
            raw = json.loads(line)
            records.append(ProfileSwitchRecord(**raw))
        except (TypeError, json.JSONDecodeError):
            continue
    return records


def now_timestamp() -> str:
    """Return a local timestamp for journal entries."""
    return datetime.now().astimezone().isoformat(timespec="seconds")
