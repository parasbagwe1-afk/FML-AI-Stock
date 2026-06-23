from sqlalchemy import inspect, text

from app.extensions import db


def ensure_runtime_schema():
    """Apply small additive schema upgrades for existing Docker databases."""
    inspector = inspect(db.engine)
    if not inspector.has_table("user"):
        return
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "company_id" in columns:
        return

    table_name = db.engine.dialect.identifier_preparer.quote("user")
    with db.engine.begin() as connection:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN company_id INTEGER NULL"))
