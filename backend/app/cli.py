import argparse
import json
from pathlib import Path

from sqlalchemy import select, text

from app.core.db import Base, SessionLocal, engine
from app.models import DealEvent, DealGame, NFLWeek, ProviderRun
from app.providers.csv_provider import CSVProvider
from app.providers.espn import ESPNProvider
from app.services.ingestion import run_sync
from app.services.scoring import finalize, recompute


def migrate():
    from app import models  # noqa: F401

    if engine.dialect.name == "sqlite":
        Base.metadata.create_all(engine)
        print("Local SQLite schema ready.")
        return
    directory = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS public.sunday_vault_migrations (version text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
            )
        )
        for path in sorted(directory.glob("*.sql")):
            if connection.scalar(
                text("SELECT 1 FROM public.sunday_vault_migrations WHERE version=:v"),
                {"v": path.name},
            ):
                continue
            connection.exec_driver_sql(path.read_text(encoding="utf-8"))
            connection.execute(
                text("INSERT INTO public.sunday_vault_migrations(version) VALUES (:v)"),
                {"v": path.name},
            )
            print("Applied", path.name)


def main():
    parser = argparse.ArgumentParser(description="Sunday Vault administration (trusted local CLI)")
    parser.add_argument(
        "command",
        choices=[
            "migrate",
            "sync",
            "import",
            "recompute",
            "finalize",
            "unfinalize",
            "health",
            "audit",
            "expire",
        ],
    )
    parser.add_argument("--season", type=int)
    parser.add_argument("--week", type=int)
    parser.add_argument("--operation", choices=["projections", "results"], default="projections")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--game")
    args = parser.parse_args()
    if args.command == "migrate":
        migrate()
        return
    with SessionLocal() as db:
        if args.command in {"sync", "import", "recompute", "finalize", "unfinalize"} and (
            args.season is None or args.week is None
        ):
            parser.error("--season and --week are required")
        if args.command in {"sync", "import"}:
            if args.command == "import" and args.file is None:
                parser.error("--file is required for CSV import")
            provider = (
                ESPNProvider()
                if args.command == "sync"
                else CSVProvider(args.file.read_text(encoding="utf-8-sig"), args.season, args.week)
            )
            print(run_sync(db, provider, args.operation, args.season, args.week))
        elif args.command in {"recompute", "finalize", "unfinalize"}:
            if args.command == "recompute":
                recompute(db, args.season, args.week)
            else:
                finalize(db, args.season, args.week, args.command == "finalize")
            db.commit()
            print("Week updated.")
        elif args.command == "health":
            print(
                "Weeks:",
                [
                    (w.season, w.week, w.scoring_status, w.projection_snapshot_id)
                    for w in db.scalars(select(NFLWeek))
                ],
            )
            print(
                "Recent provider runs:",
                [
                    (r.operation, r.status, r.message)
                    for r in db.scalars(
                        select(ProviderRun).order_by(ProviderRun.created_at.desc()).limit(10)
                    )
                ],
            )
        elif args.command == "audit":
            for e in db.scalars(
                select(DealEvent)
                .where(DealEvent.deal_game_id == args.game)
                .order_by(DealEvent.created_at)
            ):
                print(e.created_at, e.event_type, json.dumps(e.payload))
        elif args.command == "expire":
            game = db.scalar(select(DealGame).where(DealGame.id == args.game).with_for_update())
            if not game or game.status == "COMPLETE":
                parser.error("Only unfinished games can be expired")
            game.status, game.version = "EXPIRED", game.version + 1
            db.add(
                DealEvent(
                    deal_game_id=game.id,
                    user_id="local-admin",
                    event_type="ADMIN_EXPIRED",
                    payload={},
                )
            )
            db.commit()
            print("Game expired; the unfilled slot may be restarted before the weekly deadline.")


if __name__ == "__main__":
    main()
