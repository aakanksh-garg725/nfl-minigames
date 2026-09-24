from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app import scheduled_sync


@pytest.mark.parametrize("season,week", [(2026, 3), (2026, 4), (2027, 1)])
def test_scheduled_refresh_discovers_week_and_only_imports_projections(
    db, monkeypatch, season, week
):
    provider = SimpleNamespace(get_nfl_state=lambda: (season, week))
    importer = MagicMock(return_value={"snapshot_id": "test-snapshot", "players": 212})
    monkeypatch.setattr(scheduled_sync, "run_sync", importer)
    result = scheduled_sync.refresh_current_projections(db, provider)
    importer.assert_called_once_with(db, provider, "projections", season, week)
    assert result == {
        "season": season,
        "week": week,
        "snapshot_id": "test-snapshot",
        "players": 212,
    }


def postgres_session(lock_acquired):
    db = MagicMock()
    db.get_bind.return_value.dialect.name = "postgresql"
    connection = db.get_bind.return_value.connect.return_value.__enter__.return_value
    connection.scalar.return_value = lock_acquired
    return db, connection


def test_busy_sync_fails_for_scheduler_retry_without_touching_data():
    db, connection = postgres_session(False)
    with pytest.raises(scheduled_sync.SyncInProgress):
        with scheduled_sync.sync_lock(db):
            pytest.fail("A competing sync must not run")
    connection.execute.assert_not_called()


@pytest.mark.parametrize("fails", [False, True])
def test_postgres_lock_is_released_on_success_and_failure(fails):
    db, connection = postgres_session(True)
    try:
        with scheduled_sync.sync_lock(db):
            if fails:
                raise RuntimeError("test provider failure")
    except RuntimeError:
        assert fails
    connection.execute.assert_called_once()
    assert "pg_advisory_unlock" in str(connection.execute.call_args.args[0])


def test_scheduled_entrypoint_rejects_practice_mode(monkeypatch):
    monkeypatch.setattr(scheduled_sync, "configure_job_logging", lambda: None)
    monkeypatch.setattr(scheduled_sync, "get_settings", lambda: SimpleNamespace(demo=True))
    provider = MagicMock()
    monkeypatch.setattr(scheduled_sync, "ESPNProvider", provider)
    assert scheduled_sync.main() == 1
    provider.assert_not_called()
