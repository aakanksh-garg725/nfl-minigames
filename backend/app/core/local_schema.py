"""Additive upgrades for existing local practice databases."""

from sqlalchemy import inspect


def upgrade_practice_schema(engine):
    if engine.dialect.name != "sqlite":
        raise ValueError("Practice migrations require SQLite.")
    columns = {column["name"] for column in inspect(engine).get_columns("profiles")}
    if "favorite_team" not in columns:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE profiles ADD COLUMN favorite_team VARCHAR(3)")
