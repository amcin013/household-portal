"""Bring an existing database up to date with the models.

`db.create_all()` creates missing *tables* but never adds a missing *column* to
a table that already exists. On a live install that is a silent trap: the app
starts, then every query touching the new column fails.

This is deliberately not Alembic. The schema is small, the changes are almost
always "add a nullable column", and a household server should not need a
migration tool installed to survive an update. Anything more complicated than
an added column belongs in a real migration - if that day comes, add Alembic.
"""
import logging

from sqlalchemy import inspect, text

from .extensions import db

log = logging.getLogger(__name__)


def _existing_columns(inspector, table):
    return {c["name"] for c in inspector.get_columns(table)}


def _column_ddl(column):
    """SQLite needs a literal type and default in the ALTER statement."""
    kind = column.type.compile(dialect=db.engine.dialect)
    sql = f"{column.name} {kind}"

    default = column.default
    if default is not None and getattr(default, "is_scalar", False):
        value = default.arg
        if isinstance(value, bool):
            sql += f" DEFAULT {1 if value else 0}"
        elif isinstance(value, (int, float)):
            sql += f" DEFAULT {value}"
        elif isinstance(value, str):
            escaped = value.replace("'", "''")
            sql += f" DEFAULT '{escaped}'"
    return sql


def sync_columns():
    """Add any column the models define that the database is missing.

    Only ever adds; nothing is dropped, renamed, or retyped, so running it
    against an up-to-date database does nothing at all.
    """
    inspector = inspect(db.engine)
    present = set(inspector.get_table_names())
    added = []

    for table in db.metadata.sorted_tables:
        if table.name not in present:
            continue  # create_all will have made it
        have = _existing_columns(inspector, table.name)

        for column in table.columns:
            if column.name in have:
                continue
            # A NOT NULL column with no default cannot be added to a table that
            # already has rows. Skip it loudly rather than crashing on boot.
            if not column.nullable and column.default is None:
                log.error(
                    "Cannot add required column %s.%s automatically - it needs "
                    "a real migration.", table.name, column.name
                )
                continue
            ddl = f"ALTER TABLE {table.name} ADD COLUMN {_column_ddl(column)}"
            db.session.execute(text(ddl))
            added.append(f"{table.name}.{column.name}")

    if added:
        db.session.commit()
        log.info("Schema updated: added %s", ", ".join(added))
    return added
