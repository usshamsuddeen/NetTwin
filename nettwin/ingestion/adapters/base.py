"""Base adapter interface and registry for external data sources.

Every adapter converts external telemetry (Mininet sFlow, CybORG observations,
pcap packets, AWS flow logs, etc.) into ``NormalizedBatch`` objects that feed
through the existing ``SyncEngine.ingest()`` pipeline with zero changes to the
twin engine, detector, or any downstream component.
"""
from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from nettwin.ingestion.normalize import NormalizedBatch

log = logging.getLogger("nettwin.adapters")


class AdapterState(Enum):
    """Lifecycle states for an adapter."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    DEGRADED = "degraded"
    ERROR = "error"


@dataclass
class AdapterStats:
    """Observable telemetry counters for monitoring adapter health."""
    name: str = ""
    state: str = "stopped"
    polls: int = 0
    records_ingested: int = 0
    batches_produced: int = 0
    errors: int = 0
    last_poll_ts: float = 0.0
    last_batch_ts: float = 0.0
    started_at: float = 0.0
    avg_latency_ms: float = 0.0
    _latency_sum: float = field(default=0.0, repr=False)

    def record_poll(self, records: int, latency_s: float) -> None:
        self.polls += 1
        self.records_ingested += records
        self.last_poll_ts = time.time()
        self._latency_sum += latency_s * 1000
        self.avg_latency_ms = round(self._latency_sum / self.polls, 2)

    def record_batch(self) -> None:
        self.batches_produced += 1
        self.last_batch_ts = time.time()

    def record_error(self) -> None:
        self.errors += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "state": self.state,
            "polls": self.polls, "records_ingested": self.records_ingested,
            "batches_produced": self.batches_produced, "errors": self.errors,
            "last_poll_ts": self.last_poll_ts,
            "avg_latency_ms": self.avg_latency_ms,
            "uptime_s": round(time.time() - self.started_at, 1) if self.started_at else 0,
        }


class BaseAdapter(ABC):
    """Abstract adapter that produces ``NormalizedBatch`` objects.

    Subclasses must implement:
      - ``start()`` — connect to the data source and begin polling
      - ``stop()``  — gracefully disconnect
      - ``poll()``  — produce one ``NormalizedBatch`` from the latest data

    The adapter loop calls ``poll()`` at ``poll_interval_s`` intervals and
    feeds each batch into the configured callback.
    """

    def __init__(self, name: str, poll_interval_s: float = 1.0) -> None:
        self.name = name
        self.poll_interval_s = poll_interval_s
        self.stats = AdapterStats(name=name)
        self._state = AdapterState.STOPPED
        self._task: asyncio.Task[None] | None = None
        self._on_batch: Any = None  # Callable[[NormalizedBatch], Awaitable[None]]

    @property
    def state(self) -> AdapterState:
        return self._state

    def set_callback(self, cb) -> None:
        """Set the async callback that receives each NormalizedBatch."""
        self._on_batch = cb

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the data source. Called once on start."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the data source."""
        ...

    @abstractmethod
    async def poll(self) -> NormalizedBatch | None:
        """Produce one NormalizedBatch from the latest available data.

        Return ``None`` if no new data is available this cycle.
        """
        ...

    async def start(self) -> None:
        """Start the adapter polling loop."""
        if self._state == AdapterState.RUNNING:
            return
        self._state = AdapterState.STARTING
        self.stats.started_at = time.time()
        self.stats.state = "starting"
        try:
            await self.connect()
            self._state = AdapterState.RUNNING
            self.stats.state = "running"
            self._task = asyncio.create_task(self._loop())
            log.info("adapter %s started", self.name)
        except Exception:
            self._state = AdapterState.ERROR
            self.stats.state = "error"
            log.exception("adapter %s failed to start", self.name)
            raise

    async def stop(self) -> None:
        """Stop the adapter and disconnect."""
        self._state = AdapterState.STOPPED
        self.stats.state = "stopped"
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        try:
            await self.disconnect()
        except Exception:
            log.exception("adapter %s disconnect error", self.name)
        log.info("adapter %s stopped", self.name)

    async def _loop(self) -> None:
        """Main polling loop — calls poll() and dispatches batches."""
        while self._state == AdapterState.RUNNING:
            t0 = time.perf_counter()
            try:
                batch = await self.poll()
                elapsed = time.perf_counter() - t0
                if batch is not None:
                    n_records = len(batch.entities())
                    self.stats.record_poll(n_records, elapsed)
                    self.stats.record_batch()
                    if self._on_batch:
                        await self._on_batch(batch)
            except asyncio.CancelledError:
                break
            except Exception:
                self.stats.record_error()
                log.exception("adapter %s poll error", self.name)
                if self.stats.errors > 100:
                    self._state = AdapterState.ERROR
                    self.stats.state = "error"
                    log.error("adapter %s: too many errors, stopping", self.name)
                    break
            await asyncio.sleep(self.poll_interval_s)

