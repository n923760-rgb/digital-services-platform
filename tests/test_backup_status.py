"""Backup freshness determines what administrators see without exposing archive files."""

import os
from datetime import datetime, timedelta, timezone

from platform_core.backup_status import backup_health


def test_backup_freshness_and_missing_marker(tmp_path):
    now = datetime(2026, 9, 12, tzinfo=timezone.utc)
    marker = tmp_path / "latest"
    assert backup_health(str(marker), now=now) == {"status": "missing", "last_success_at": None}
    marker.write_text("success\n")
    fresh = now - timedelta(hours=25)
    os.utime(marker, (fresh.timestamp(), fresh.timestamp()))
    result = backup_health(str(marker), now=now)
    assert result["status"] == "ok"
    assert result["last_success_at"] == fresh.isoformat()

    old = now - timedelta(hours=27)
    os.utime(marker, (old.timestamp(), old.timestamp()))
    assert backup_health(str(marker), now=now)["status"] == "stale"
    future = now + timedelta(minutes=10)
    os.utime(marker, (future.timestamp(), future.timestamp()))
    assert backup_health(str(marker), now=now)["status"] == "stale"
