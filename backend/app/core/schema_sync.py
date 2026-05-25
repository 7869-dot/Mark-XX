"""Idempotent schema sync — adds new columns and indexes that postdate the
original `Base.metadata.create_all` on a live DB.

The project deliberately doesn't use Alembic — instead, every release that
adds columns/indexes appends a check here. The lifespan startup runs this
once per process; in cold prod it's the only place that converts model
changes into real DDL.

All ALTERs are guarded: read information_schema (PG) / pragma_table_info
(SQLite) first, only run when missing. Safe to invoke on every boot.
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.core.logging import get_logger, log_event

logger = get_logger("axolot.schema_sync")


def _dialect(engine: Engine) -> str:
    return engine.dialect.name


def _column_exists(engine: Engine, table: str, column: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def _index_exists(engine: Engine, table: str, index: str) -> bool:
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return False
    return any(i["name"] == index for i in insp.get_indexes(table))


def _add_column(engine: Engine, table: str, column: str, ddl_type: str, default_sql: str | None = None) -> None:
    if _column_exists(engine, table, column):
        return
    extra = f" DEFAULT {default_sql}" if default_sql else ""
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}{extra}"
    with engine.begin() as conn:
        conn.execute(text(sql))
    log_event(logger, "schema_added_column", table=table, column=column)


def _add_index(engine: Engine, name: str, table: str, cols: str, unique: bool = False) -> None:
    if _index_exists(engine, table, name):
        return
    uniq = "UNIQUE " if unique else ""
    sql = f"CREATE {uniq}INDEX IF NOT EXISTS {name} ON {table} ({cols})"
    with engine.begin() as conn:
        conn.execute(text(sql))
    log_event(logger, "schema_added_index", index=name, table=table)


def run_schema_sync(engine: Engine) -> None:
    """Apply all known post-create_all additions. Idempotent."""
    try:
        # --- Agent.availability (Section 8) ---
        # Stored as plain text so the enum can evolve without an ALTER TYPE.
        _add_column(engine, "agents", "availability", "VARCHAR(32)", default_sql="'always_on'")

        # --- UserPersonality structured speech fields (Phase 3) ---
        _add_column(engine, "user_personalities", "avg_sentence_length", "VARCHAR(16)")
        _add_column(engine, "user_personalities", "formality", "VARCHAR(16)")
        _add_column(engine, "user_personalities", "emoji_usage", "VARCHAR(16)")
        _add_column(engine, "user_personalities", "punctuation_style", "VARCHAR(16)")
        _add_column(engine, "user_personalities", "signature_word", "VARCHAR(64)")
        # JSON column type differs between PG and SQLite — `TEXT` works on
        # both (SQLAlchemy will adapt reads/writes via the model definition).
        _add_column(engine, "user_personalities", "sample_phrases", "TEXT")

        # --- Indexes for scale (Phase 8 — backend recommendation) ---
        _add_index(
            engine, "ix_agent_messages_recipient_processed",
            "agent_messages", "recipient_agent_id, processed",
        )
        _add_index(
            engine, "ix_classified_emails_user_category",
            "classified_emails", "user_id, category",
        )
        _add_index(
            engine, "ix_activity_agent_created",
            "agent_activity_log", "agent_id, created_at",
        )
    except Exception as exc:  # noqa: BLE001
        # Never fail startup over schema sync — log loudly and continue. The
        # next deploy can investigate; the app keeps running on the old shape.
        log_event(logger, "schema_sync_failed", error=str(exc))
