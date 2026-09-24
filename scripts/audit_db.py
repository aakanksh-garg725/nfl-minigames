"""Read-only RLS and schema checks against the configured database."""
from sqlalchemy import text
from app.core.db import engine

with engine.connect() as connection:
    rows = connection.execute(text("""
        SELECT c.relname, c.relrowsecurity,
          has_table_privilege('anon', c.oid, 'SELECT') AS anon_read,
          has_table_privilege('authenticated', c.oid, 'SELECT') AS user_read,
          has_table_privilege('authenticated', c.oid, 'INSERT,UPDATE,DELETE') AS user_write
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname
    """)).mappings().all()
    hidden = {"deal_games", "deal_game_cases", "deal_game_offers", "deal_game_events", "player_week_projections", "player_week_results", "lineup_slots", "rivalries", "rivalry_matchups"}
    for row in rows:
        assert row["relrowsecurity"], f"RLS disabled on {row['relname']}"
        assert not row["user_write"], f"Client write allowed on {row['relname']}"
        if row["relname"] in hidden:
            assert not row["anon_read"] and not row["user_read"], f"Hidden data readable on {row['relname']}"
    print("RLS enabled and client writes denied on", len(rows), "tables.")
    print("Hidden case, offer, event, projection, result and lineup tables inaccessible to browser roles.")
    counts = connection.execute(text("SELECT position, count(*) FROM players GROUP BY position ORDER BY position")).all()
    print("Player counts:", counts)
    weeks = connection.execute(text("SELECT season, week, scoring_status, projection_snapshot_id IS NOT NULL AS data_ready FROM nfl_weeks")).all()
    print("Weeks:", weeks)
    payload = connection.scalar(text("SELECT raw_payload FROM player_week_projections LIMIT 1"))
    print("Projection record fields:", list(payload) if payload else [])
