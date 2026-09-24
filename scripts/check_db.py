"""Read-only connectivity and schema collision check; no credentials in output."""
from sqlalchemy import inspect, text
from app.core.db import engine

try:
    with engine.connect() as connection:
        print("Connected:", connection.scalar(text("select current_database()")))
        print("Public tables:", inspect(connection).get_table_names(schema="public"))
        print("Auth schema:", "auth" in inspect(connection).get_schema_names())
except Exception as error:
    print("Database connection failed:", type(error).__name__)
    raise SystemExit(1)
