"""Generate the initial, reviewable PostgreSQL DDL from the shared ORM schema."""
from pathlib import Path
from sqlalchemy.schema import CreateIndex, CreateTable
from sqlalchemy.dialects import postgresql
from app.core.db import Base
from app import models  # noqa: F401

target = Path(__file__).resolve().parents[1] / "supabase" / "migrations" / "202609220001_initial.sql"
if target.exists():
    raise SystemExit("Refusing to overwrite an existing migration")
target.parent.mkdir(parents=True, exist_ok=True)
dialect = postgresql.dialect()
statements = ["-- Generated initial schema. Applied atomically; never drops existing tables."]
for table in Base.metadata.sorted_tables:
    statements.append(str(CreateTable(table).compile(dialect=dialect)) + ";")
    statements.extend(str(CreateIndex(index).compile(dialect=dialect)) + ";" for index in table.indexes)
    statements.extend([
        f'ALTER TABLE public."{table.name}" ENABLE ROW LEVEL SECURITY;',
        f'REVOKE ALL ON public."{table.name}" FROM anon, authenticated;',
    ])
# FastAPI is the only reader/writer of game data; no browser role gets hidden data.
statements.extend([
    "GRANT SELECT ON public.profiles TO authenticated;",
    "CREATE POLICY profiles_own_read ON public.profiles FOR SELECT TO authenticated USING (auth.uid()::text = user_id);",
    "GRANT SELECT ON public.weekly_entries TO authenticated;",
    "CREATE POLICY entries_own_read ON public.weekly_entries FOR SELECT TO authenticated USING (auth.uid()::text = user_id);",
    "CREATE INDEX active_game_lookup ON public.deal_games(entry_id, slot) WHERE status NOT IN ('COMPLETE', 'EXPIRED');",
    "ALTER TABLE public.profiles ADD CONSTRAINT username_valid CHECK (username ~ '^[a-z0-9_]{3,24}$');",
    "ALTER TABLE public.nfl_weeks ADD CONSTRAINT week_valid CHECK (week BETWEEN 1 AND 18 AND opens_at < closes_at);",
    "ALTER TABLE public.deal_game_cases ADD CONSTRAINT case_number_valid CHECK (case_number BETWEEN 1 AND 12);",
    "ALTER TABLE public.lineup_slots ADD CONSTRAINT slot_valid CHECK (slot IN ('RB1','RB2','WR1','WR2','TE','FLEX'));",
    "REVOKE ALL ON public.sunday_vault_migrations FROM anon, authenticated;",
    "ALTER TABLE public.sunday_vault_migrations ENABLE ROW LEVEL SECURITY;",
])
target.write_text("\n\n".join(statements) + "\n", encoding="utf-8")
print("Generated", target.name)
