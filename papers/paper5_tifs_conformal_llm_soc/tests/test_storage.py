"""Storage persistence regression tests."""

import os
import sys
from pathlib import Path
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
_REPO_ROOT_PATH = Path(_REPO_ROOT)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import asyncio
import sqlite3

import pytest

from nettwin.alerts import AlertManager
from nettwin.config import Settings
from nettwin.models import Alert
from nettwin.storage import Storage


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def settings():
    return Settings()


def test_alert_confidence_round_trip(tmp_path):
    db = tmp_path / "alerts.db"

    async def main():
        storage = Storage(str(db))
        await storage.init()
        alert = Alert(
            entity_id="web1",
            entity_kind="node",
            alert_type="anomaly:pps",
            severity="critical",
            message="test alert",
            score=0.95,
            tick=7,
            confidence=0.88,
        )
        await storage.upsert_alert(alert)
        rows = await storage.list_alerts("all")
        await storage.close()
        return rows

    rows = run(main())
    assert len(rows) == 1
    assert rows[0]["confidence"] == pytest.approx(0.88)


def test_alert_confidence_survives_manager_reload(tmp_path, settings):
    db = tmp_path / "alerts.db"
    alert_id: str

    async def save():
        nonlocal alert_id
        storage = Storage(str(db))
        await storage.init()
        manager = AlertManager(settings, storage)
        alert = Alert(
            entity_id="web1",
            entity_kind="node",
            alert_type="anomaly:pps",
            severity="critical",
            message="test alert",
            score=0.95,
            tick=7,
            confidence=0.91,
        )
        manager._register(alert)
        await storage.upsert_alert(alert)
        alert_id = alert.id
        await storage.close()

    async def reload():
        storage = Storage(str(db))
        await storage.init()
        manager = AlertManager(settings, storage)
        await manager.load_active()
        await storage.close()
        return manager.alerts.get(alert_id)

    run(save())
    restored = run(reload())
    assert restored is not None
    assert restored.confidence == pytest.approx(0.91)


def test_migrate_adds_confidence_column(tmp_path):
    db = tmp_path / "legacy.db"

    # Simulate a pre-existing database created before the confidence column.
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE alerts ("
        "id TEXT PRIMARY KEY, entity_id TEXT, entity_kind TEXT, alert_type TEXT, "
        "severity TEXT, message TEXT, score REAL, status TEXT, "
        "created_at REAL, updated_at REAL, tick INTEGER, hits INTEGER)"
    )
    conn.execute(
        "INSERT INTO alerts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("a1", "web1", "node", "anomaly:pps", "warning", "legacy", 0.8,
         "active", 1.0, 2.0, 5, 1),
    )
    conn.commit()
    conn.close()

    async def main():
        storage = Storage(str(db))
        await storage.init()
        rows = await storage.list_alerts("all")
        await storage.close()
        return rows

    rows = run(main())
    assert len(rows) == 1
    # Missing confidence should come back as None / NULL.
    assert rows[0]["confidence"] is None
