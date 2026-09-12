"""Read the backup service's minimal timestamp marker; never mount its archives in the API."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_BACKUP_AGE = timedelta(hours=26)


def backup_health(path: str, *, now: datetime | None = None) -> dict[str, str | None]:
    if not path:
        return {"status": "unconfigured", "last_success_at": None}
    try:
        marker = Path(path).stat()
    except OSError:
        return {"status": "missing", "last_success_at": None}
    if marker.st_size == 0:
        return {"status": "missing", "last_success_at": None}
    timestamp = datetime.fromtimestamp(marker.st_mtime, tz=timezone.utc)
    current = now or datetime.now(timezone.utc)
    age = current - timestamp
    return {
        "status": "ok" if timedelta(0) <= age < MAX_BACKUP_AGE else "stale",
        "last_success_at": timestamp.isoformat(),
    }
