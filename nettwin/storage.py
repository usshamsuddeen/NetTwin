"""SQLite persistence (stdlib sqlite3, WAL, async via asyncio.to_thread)."""
from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from nettwin.models import Alert, AttackEvent

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    lock INTEGER PRIMARY KEY CHECK (lock = 1),
    version INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO schema_version (lock, version) VALUES (1, 0);

CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY, entity_id TEXT, entity_kind TEXT, alert_type TEXT,
    severity TEXT, message TEXT, score REAL, status TEXT,
    created_at REAL, updated_at REAL, tick INTEGER, hits INTEGER,
    confidence REAL);
CREATE TABLE IF NOT EXISTS attack_events (
    id TEXT PRIMARY KEY, attack_type TEXT, target_id TEXT, source_id TEXT,
    started_at REAL, ended_at REAL, start_tick INTEGER, duration_s REAL, active INTEGER);
CREATE TABLE IF NOT EXISTS metric_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT, tick INTEGER, ts REAL,
    entity_id TEXT, entity_kind TEXT, metrics TEXT);
CREATE INDEX IF NOT EXISTS idx_snap_entity ON metric_snapshots(entity_id, tick);

CREATE TABLE IF NOT EXISTS response_actions (
    id TEXT PRIMARY KEY, action_type TEXT, entity_id TEXT,
    status TEXT, proposed_at REAL, applied_at REAL, reverted_at REAL,
    sandbox_delta REAL, observed_delta REAL, metadata TEXT);
CREATE INDEX IF NOT EXISTS idx_response_status ON response_actions(status);

CREATE TABLE IF NOT EXISTS research_metrics (
    ts REAL, tick INTEGER, metric TEXT, value REAL);
CREATE INDEX IF NOT EXISTS idx_research_ts ON research_metrics(ts);
"""

_ALERT_COLUMNS = [
    "id", "entity_id", "entity_kind", "alert_type", "severity", "message",
    "score", "status", "created_at", "updated_at", "tick", "hits", "confidence",
]


def _ensure_confidence_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(alerts)")}
    if "confidence" not in cols:
        conn.execute("ALTER TABLE alerts ADD COLUMN confidence REAL")


def _migration_1_confidence(conn: sqlite3.Connection) -> None:
    _ensure_confidence_column(conn)


def _migration_2_response_actions(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS response_actions (
        id TEXT PRIMARY KEY, action_type TEXT, entity_id TEXT,
        status TEXT, proposed_at REAL, applied_at REAL, reverted_at REAL,
        sandbox_delta REAL, observed_delta REAL, metadata TEXT);
    CREATE INDEX IF NOT EXISTS idx_response_status ON response_actions(status);
    """)


def _migration_3_research_metrics(conn: sqlite3.Connection) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS research_metrics (
        ts REAL, tick INTEGER, metric TEXT, value REAL);
    CREATE INDEX IF NOT EXISTS idx_research_ts ON research_metrics(ts);
    """)


_MIGRATIONS = [
    _migration_1_confidence,
    _migration_2_response_actions,
    _migration_3_research_metrics,
]


def _run_migrations(conn: sqlite3.Connection) -> None:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
    if not cur.fetchone():
        conn.execute(
            "CREATE TABLE schema_version ("
            "lock INTEGER PRIMARY KEY CHECK (lock = 1), version INTEGER NOT NULL DEFAULT 0)")
        conn.execute("INSERT INTO schema_version (lock, version) VALUES (1, 0)")
    version = conn.execute("SELECT version FROM schema_version WHERE lock=1").fetchone()[0] or 0
    for idx, mig in enumerate(_MIGRATIONS, start=1):
        if version < idx:
            mig(conn)
            conn.execute("UPDATE schema_version SET version=? WHERE lock=1", (idx,))
            conn.commit()


def _open_db(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    _run_migrations(conn)
    conn.commit()
    return conn


class Storage:
    """Thread-safe async SQLite storage using one connection per operation."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._init_lock = asyncio.Lock()
        self._initialized = False

    async def init(self) -> None:
        async with self._init_lock:
            if not self._initialized:
                await asyncio.to_thread(self._init_sync)
                self._initialized = True

    def _init_sync(self) -> None:
        conn = _open_db(self.path)
        conn.close()

    async def close(self) -> None:
        # Each operation opens and closes its own connection; nothing to flush.
        self._initialized = False

    def _with_conn(self, fn):
        """Synchronous helper used inside asyncio.to_thread."""
        conn = _open_db(self.path)
        try:
            return fn(conn)
        finally:
            conn.close()

    # ---- alerts ---------------------------------------------------------
    async def upsert_alert(self, a: Alert) -> None:
        def _fn(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO alerts ("
                "id, entity_id, entity_kind, alert_type, severity, message, score, status, "
                "created_at, updated_at, tick, hits, confidence) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (a.id, a.entity_id, a.entity_kind, a.alert_type, a.severity, a.message,
                 a.score, a.status, a.created_at, a.updated_at, a.tick, a.hits, a.confidence))
            conn.commit()
        await asyncio.to_thread(self._with_conn, _fn)

    async def list_alerts(self, status: str | None = "all") -> list[dict[str, Any]]:
        def _fn(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            cols = ", ".join(_ALERT_COLUMNS)
            if status and status != "all":
                rows = conn.execute(
                    f"SELECT {cols} FROM alerts WHERE status=? ORDER BY updated_at DESC", (status,))
            else:
                rows = conn.execute(f"SELECT {cols} FROM alerts ORDER BY updated_at DESC")
            return [dict(r) for r in rows.fetchall()]
        return await asyncio.to_thread(self._with_conn, _fn)

    # ---- attack events ----------------------------------------------------
    async def save_attack(self, e: AttackEvent) -> None:
        def _fn(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO attack_events VALUES (?,?,?,?,?,?,?,?,?)",
                (e.id, e.attack_type, e.target_id, e.source_id, e.started_at, e.ended_at,
                 e.start_tick, e.duration_s, 1 if e.active else 0))
            conn.commit()
        await asyncio.to_thread(self._with_conn, _fn)

    # ---- metric snapshots -------------------------------------------------
    async def snapshot(self, tick: int, entity_id: str, kind: str,
                       metrics: dict[str, Any]) -> None:
        def _fn(conn: sqlite3.Connection) -> None:
            conn.execute("INSERT INTO metric_snapshots(tick, ts, entity_id, entity_kind, metrics)"
                         " VALUES (?,?,?,?,?)",
                         (tick, time.time(), entity_id, kind, json.dumps(metrics)))
            conn.commit()
        await asyncio.to_thread(self._with_conn, _fn)

    async def prune_snapshots(self, older_than_days: int) -> int:
        def _fn(conn: sqlite3.Connection) -> int:
            cutoff = time.time() - (older_than_days * 86400)
            cur = conn.execute("DELETE FROM metric_snapshots WHERE ts < ?", (cutoff,))
            conn.commit()
            return cur.rowcount
        return await asyncio.to_thread(self._with_conn, _fn)

    # ---- response actions -------------------------------------------------
    async def save_response_action(self, action: dict[str, Any]) -> None:
        def _fn(conn: sqlite3.Connection) -> None:
            conn.execute(
                "INSERT OR REPLACE INTO response_actions ("
                "id, action_type, entity_id, status, proposed_at, applied_at, reverted_at, "
                "sandbox_delta, observed_delta, metadata) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (action["id"], action.get("action_type"), action.get("entity_id"),
                 action.get("status"), action.get("proposed_at"), action.get("applied_at"),
                 action.get("reverted_at"), action.get("sandbox_delta"),
                 action.get("observed_delta"), json.dumps(action.get("metadata") or {})))
            conn.commit()
        await asyncio.to_thread(self._with_conn, _fn)

    async def load_response_actions(self, status: str | None = None) -> list[dict[str, Any]]:
        def _fn(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            sql = "SELECT * FROM response_actions"
            params: tuple[Any, ...] = ()
            if status:
                sql += " WHERE status=?"
                params = (status,)
            sql += " ORDER BY proposed_at DESC"
            rows = conn.execute(sql, params)
            out = []
            for r in rows.fetchall():
                d = dict(r)
                d["metadata"] = json.loads(d.get("metadata") or "{}")
                out.append(d)
            return out
        return await asyncio.to_thread(self._with_conn, _fn)

    # ---- research metrics -------------------------------------------------
    async def save_research(self, tick: int, metrics: dict[str, float]) -> None:
        def _fn(conn: sqlite3.Connection) -> None:
            ts = time.time()
            rows = [(ts, tick, k, float(v)) for k, v in metrics.items() if v is not None]
            if rows:
                conn.executemany("INSERT INTO research_metrics(ts, tick, metric, value) "
                                 "VALUES (?,?,?,?)", rows)
                conn.commit()
        await asyncio.to_thread(self._with_conn, _fn)

    async def load_research_window(self, metric: str, window_days: int) -> list[dict[str, Any]]:
        def _fn(conn: sqlite3.Connection) -> list[dict[str, Any]]:
            cutoff = time.time() - (window_days * 86400)
            rows = conn.execute(
                "SELECT ts, tick, value FROM research_metrics "
                "WHERE metric=? AND ts >= ? ORDER BY ts",
                (metric, cutoff))
            return [dict(r) for r in rows.fetchall()]
        return await asyncio.to_thread(self._with_conn, _fn)

    async def prune_research(self, older_than_days: int) -> int:
        def _fn(conn: sqlite3.Connection) -> int:
            cutoff = time.time() - (older_than_days * 86400)
            cur = conn.execute("DELETE FROM research_metrics WHERE ts < ?", (cutoff,))
            conn.commit()
            return cur.rowcount
        return await asyncio.to_thread(self._with_conn, _fn)
