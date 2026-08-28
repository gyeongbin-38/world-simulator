"""Small deterministic SQLite migration runner for the I-03 reference store."""

from __future__ import annotations

import sqlite3

from .contracts import FaultInjector, UnsupportedSchemaError


LATEST_SCHEMA_VERSION = 1


def configure_connection(connection: sqlite3.Connection) -> None:
    connection.isolation_level = None
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")
    connection.execute("PRAGMA busy_timeout = 5000")


def migrate(
    connection: sqlite3.Connection,
    *,
    fault_injector: FaultInjector | None = None,
) -> None:
    current = _read_schema_version(connection)
    if current > LATEST_SCHEMA_VERSION:
        raise UnsupportedSchemaError(
            f"database schema {current} is newer than supported {LATEST_SCHEMA_VERSION}"
        )
    if current == LATEST_SCHEMA_VERSION:
        return

    committed = False
    try:
        connection.execute("BEGIN IMMEDIATE")
        if current < 1:
            for statement in _INITIAL_STATEMENTS:
                connection.execute(statement)
            if fault_injector is not None:
                fault_injector.check("MIGRATION_0001")
        connection.commit()
        committed = True
    except Exception:
        if not committed:
            connection.rollback()
        raise


def _read_schema_version(connection: sqlite3.Connection) -> int:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_meta'"
    ).fetchone()
    if exists is None:
        return 0
    row = connection.execute(
        "SELECT schema_version FROM schema_meta WHERE schema_id = 1"
    ).fetchone()
    return 0 if row is None else int(row[0])


_INITIAL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        schema_id INTEGER PRIMARY KEY CHECK (schema_id = 1),
        schema_version INTEGER NOT NULL,
        migration_id TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE runs (
        run_id TEXT PRIMARY KEY,
        lifespan_ticks INTEGER NOT NULL,
        maturity_delay_ticks INTEGER NOT NULL,
        refractory_interval_ticks INTEGER NOT NULL,
        population_capacity INTEGER,
        horizon INTEGER,
        status TEXT NOT NULL,
        current_tick INTEGER NOT NULL,
        current_state_version INTEGER NOT NULL,
        current_state_hash TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE snapshots (
        run_id TEXT NOT NULL,
        state_version INTEGER NOT NULL,
        tick INTEGER NOT NULL,
        state_hash TEXT NOT NULL,
        commit_id TEXT,
        snapshot_json TEXT NOT NULL,
        PRIMARY KEY (run_id, state_version),
        FOREIGN KEY (run_id) REFERENCES runs(run_id)
    )
    """,
    """
    CREATE TABLE agents_current (
        run_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        birth_tick INTEGER NOT NULL,
        first_active_tick INTEGER NOT NULL,
        lifespan_ticks INTEGER NOT NULL,
        maturity_delay_ticks INTEGER NOT NULL,
        state TEXT NOT NULL,
        refractory_until_tick INTEGER,
        PRIMARY KEY (run_id, agent_id),
        FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE messages_current (
        run_id TEXT NOT NULL,
        message_id TEXT NOT NULL,
        sender_id TEXT NOT NULL,
        recipient_id TEXT NOT NULL,
        body TEXT NOT NULL,
        committed_tick INTEGER NOT NULL,
        available_tick INTEGER NOT NULL,
        PRIMARY KEY (run_id, message_id),
        FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE proposals_current (
        run_id TEXT NOT NULL,
        proposal_id TEXT NOT NULL,
        proposer_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        created_tick INTEGER NOT NULL,
        state TEXT NOT NULL,
        expires_at_tick INTEGER,
        PRIMARY KEY (run_id, proposal_id),
        FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE commits (
        commit_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        commit_seq INTEGER NOT NULL,
        tick INTEGER NOT NULL,
        state_version_before INTEGER NOT NULL,
        state_version_after INTEGER NOT NULL,
        previous_state_hash TEXT NOT NULL,
        resulting_state_hash TEXT NOT NULL,
        transition_digest TEXT NOT NULL,
        commit_status TEXT NOT NULL,
        resulting_snapshot_json TEXT NOT NULL,
        UNIQUE (run_id, commit_seq),
        UNIQUE (run_id, state_version_after),
        FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE commit_events (
        commit_id TEXT NOT NULL,
        event_ordinal INTEGER NOT NULL,
        event_id TEXT NOT NULL UNIQUE,
        event_type TEXT NOT NULL,
        commit_tick INTEGER NOT NULL,
        commit_order INTEGER NOT NULL,
        artifact_refs_json TEXT NOT NULL,
        PRIMARY KEY (commit_id, event_ordinal),
        FOREIGN KEY (commit_id) REFERENCES commits(commit_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE commit_artifacts (
        commit_id TEXT NOT NULL,
        artifact_id TEXT NOT NULL,
        digest TEXT NOT NULL,
        PRIMARY KEY (commit_id, artifact_id),
        FOREIGN KEY (commit_id) REFERENCES commits(commit_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE outbox (
        outbox_id TEXT PRIMARY KEY,
        commit_id TEXT NOT NULL,
        commit_seq INTEGER NOT NULL,
        record_type TEXT NOT NULL,
        event_id TEXT,
        status TEXT NOT NULL,
        attempt_count INTEGER NOT NULL,
        payload_artifact_ref_json TEXT,
        FOREIGN KEY (commit_id) REFERENCES commits(commit_id) ON DELETE CASCADE
    )
    """,
    """
    INSERT INTO schema_meta (schema_id, schema_version, migration_id)
    VALUES (1, 1, '0001_initial')
    """,
)
