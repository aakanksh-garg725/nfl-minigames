"""One-shot ESPN projection refresh for the local Windows scheduled task."""

import logging
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import SessionLocal, engine
from app.core.logging import JSONFormatter
from app.providers.espn import ESPNProvider
from app.services.ingestion import run_sync

log = logging.getLogger(__name__)
LOG_PATH = Path(__file__).resolve().parents[2] / "artifacts" / "espn-daily-projections.log"
# Same lock as app.worker, so daily and continuous sync cannot overlap.
SYNC_LOCK_ID = 72803419


class SyncInProgress(Exception):
    pass


@contextmanager
def sync_lock(db):
    if db.get_bind().dialect.name != "postgresql":
        yield
        return
    with db.get_bind().connect() as connection:
        if not connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": SYNC_LOCK_ID}):
            raise SyncInProgress("Another sync is running; the scheduler should retry.")
        try:
            yield
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": SYNC_LOCK_ID})


def refresh_current_projections(db, provider):
    with sync_lock(db):
        season, week = provider.get_nfl_state()
        result = run_sync(db, provider, "projections", season, week)
        return {"season": season, "week": week, **result}


def configure_job_logging():
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def main():
    configure_job_logging()
    provider = None
    log.info("daily_projection_refresh_started")
    try:
        if get_settings().demo or engine.dialect.name != "postgresql":
            raise ValueError("Scheduled refresh requires live Postgres mode.")
        provider = ESPNProvider()
        with SessionLocal() as db:
            result = refresh_current_projections(db, provider)
        log.info(
            "daily_projection_refresh_succeeded: season=%s week=%s players=%s",
            result["season"],
            result["week"],
            result["players"],
            extra={"snapshot_id": result["snapshot_id"], "provider": "espn"},
        )
        return 0
    except Exception as error:
        # Connection/provider exceptions can contain credentials. Never log their full text.
        log.error("daily_projection_refresh_failed", extra={"reason": type(error).__name__})
        return 1
    finally:
        if provider is not None:
            provider.client.close()


if __name__ == "__main__":
    raise SystemExit(main())
