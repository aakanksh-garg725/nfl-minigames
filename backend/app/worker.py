"""Single local worker. PostgreSQL advisory locking prevents duplicate workers."""

import asyncio
import logging
import time

from sqlalchemy import select, text

from app.core.db import SessionLocal
from app.core.time import EASTERN, aware, utcnow
from app.models import NFLGame, NFLWeek
from app.providers.espn import ESPNProvider
from app.services.ingestion import run_sync, sync_schedule
from app.services.scoring import finalize

log = logging.getLogger(__name__)


class SyncWorker:
    def __init__(self):
        self.provider = ESPNProvider()
        self.last_projection = 0

    def tick(self):
        with SessionLocal() as db:
            # Session-level lock remains held on this dedicated connection through commits.
            with db.bind.connect() as connection:
                postgres = connection.dialect.name == "postgresql"
                if postgres and not connection.scalar(
                    text("select pg_try_advisory_lock(72803419)")
                ):
                    return
                try:
                    self._run(db)
                finally:
                    if postgres:
                        connection.execute(text("select pg_advisory_unlock(72803419)"))

    def _run(self, db):
        season, week = self.provider.get_nfl_state()
        now = utcnow()
        sync_schedule(db, self.provider, season, week)
        db.commit()
        current = db.scalar(select(NFLWeek).where(NFLWeek.season == season, NFLWeek.week == week))
        if now < aware(current.closes_at) and time.monotonic() - self.last_projection > 1800:
            run_sync(db, self.provider, "projections", season, week)
            self.last_projection = time.monotonic()
        weeks = db.scalars(select(NFLWeek).where(NFLWeek.scoring_status != "FINAL")).all()
        for nfl_week in weeks:
            games = db.scalars(
                select(NFLGame).where(
                    NFLGame.season == nfl_week.season, NFLGame.week == nfl_week.week
                )
            ).all()
            if games and any(aware(g.kickoff_at) <= now for g in games):
                run_sync(db, self.provider, "results", nfl_week.season, nfl_week.week)
                # At the following Tuesday opening, finalize only if all games/results are final.
                from datetime import timedelta

                if now >= aware(nfl_week.opens_at).astimezone(EASTERN) + timedelta(days=7):
                    finalize(db, nfl_week.season, nfl_week.week)
                    db.commit()


async def worker_loop():
    worker = SyncWorker()
    while True:
        try:
            await asyncio.to_thread(worker.tick)
        except Exception as error:
            log.error("sync_worker_failed: %s", type(error).__name__)
        await asyncio.sleep(180)


if __name__ == "__main__":
    asyncio.run(worker_loop())
