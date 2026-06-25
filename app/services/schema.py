from sqlalchemy import inspect, text

from app.extensions import db


def ensure_runtime_schema():
    """Apply small additive schema upgrades for existing Docker databases."""
    inspector = inspect(db.engine)
    if inspector.has_table("user"):
        ensure_columns(
            "user",
            {
                "company_id": "INTEGER NULL",
            },
            inspector,
        )
    if inspector.has_table("customer"):
        ensure_columns(
            "customer",
            {
                "contact_person": "VARCHAR(160) NULL",
                "whatsapp": "VARCHAR(40) NULL",
                "city": "VARCHAR(120) NULL",
                "state": "VARCHAR(120) NULL",
            },
            inspector,
        )


def ensure_columns(table, columns, inspector):
    existing = {column["name"] for column in inspector.get_columns(table)}
    missing = {name: definition for name, definition in columns.items() if name not in existing}
    if not missing:
        return
    table_name = db.engine.dialect.identifier_preparer.quote(table)
    with db.engine.begin() as connection:
        for name, definition in missing.items():
            column_name = db.engine.dialect.identifier_preparer.quote(name)
            connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"))
