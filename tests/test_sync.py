"""Sync layer tests: normalization, SHADOW/HYBRID transitions, staleness."""
from nettwin.config import Settings
from nettwin.ingestion.normalize import Normalizer, parse_payload
from nettwin.ingestion.sync import SyncEngine
from nettwin.simulator.engine import SimulationEngine


def _settings() -> Settings:
    s = Settings()
    s.sync.sync_map = {"10.0.3.11": "web1", "10.0.4.21": "db1"}
    s.sync.hybrid_after_ticks = 6
    s.sync.drop_after_ticks = 3
    return s


def test_normalize_records():
    s = _settings()
    sync = SyncEngine(s.sync, SimulationEngine(s).topology)
    norm = Normalizer(sync.resolve)
    assert sync.resolve("10.0.3.11") == "web1"
    assert sync.resolve("db1") == "db1"
    assert sync.resolve("192.168.99.99") is None
    batch = norm.normalize([
        {"type": "gauge", "host": "10.0.3.11",
         "metrics": {"cpu_pct": 30.0, "latency_ms": 1.2}},
        {"type": "interface", "host": "web1", "in_bps": 8e6, "out_bps": 4e6},
        {"type": "flow", "src": "10.0.3.11", "dst": "10.0.4.21",
         "proto": "TCP", "bytes": 50000, "packets": 50},
    ])
    assert batch.gauges["web1"]["cpu_pct"] == 30.0
    assert "web1" in batch.tx_bytes or "web1" in batch.rx_bytes
    assert batch.rx_bytes["db1"] >= 50000
    records = parse_payload('{"type":"gauge","host":"web1","metrics":{}}\n'
                            '{"type":"flow","src":"web1","dst":"db1"}')
    assert len(records) == 2


def _feed_matching(sync, norm, tick, entity, now):
    m = tick.nodes[entity]
    batch = norm.normalize([
        {"type": "interface", "host": entity,
         "in_bps": m.rx_mbps * 1e6, "out_bps": m.tx_mbps * 1e6},
        {"type": "gauge", "host": entity,
         "metrics": {"latency_ms": m.latency_ms}},
    ])
    sync.ingest(batch, 1.0, now=now)


def test_shadow_hybrid_staleness_cycle():
    s = _settings()
    eng = SimulationEngine(s)
    sync = SyncEngine(s.sync, eng.topology)
    norm = Normalizer(sync.resolve)
    now = 10_000.0
    # first real datagram -> SHADOW
    tick = eng.step()
    _feed_matching(sync, norm, tick, "web1", now)
    sync.update(tick, now=now)
    assert sync.entities["web1"].mode == "SHADOW"
    # consistent real feed -> HYBRID after hysteresis
    for i in range(1, 12):
        tick = eng.step()
        _feed_matching(sync, norm, tick, "web1", now + i)
        sync.update(tick, now=now + i)
    es = sync.entities["web1"]
    assert es.mode == "HYBRID", f"mode={es.mode} fidelity={es.fidelity}"
    assert 80.0 <= es.fidelity <= 100.0
    # HYBRID: real values drive the twin entity
    tick = eng.step()
    sim_tp = tick.nodes["web1"].throughput_mbps
    batch = norm.normalize([{"type": "interface", "host": "web1",
                             "in_bps": 50e6, "out_bps": 10e6}])
    sync.ingest(batch, 1.0, now=now + 12)
    sync.update(tick, now=now + 12)
    assert tick.nodes["web1"].throughput_mbps == 60.0  # (50+10)Mbps real
    # staleness -> revert to SIMULATED
    tick = eng.step()
    sync.update(tick, now=now + 12 + s.sync.staleness_s + 1.0)
    assert sync.entities["web1"].mode == "SIMULATED"


def test_divergent_feed_stays_shadow_and_flags_drift():
    s = _settings()
    eng = SimulationEngine(s)
    sync = SyncEngine(s.sync, eng.topology)
    norm = Normalizer(sync.resolve)
    now = 20_000.0
    for i in range(16):
        tick = eng.step()
        m = tick.nodes["web1"]
        batch = norm.normalize([
            {"type": "interface", "host": "web1",
             "in_bps": (m.rx_mbps * 20 + 500) * 1e6, "out_bps": 0},
            {"type": "gauge", "host": "web1",
             "metrics": {"latency_ms": m.latency_ms * 30 + 100}},
        ])
        sync.ingest(batch, 1.0, now=now + i)
        sync.update(tick, now=now + i)
    es = sync.entities["web1"]
    assert es.mode == "SHADOW"
    assert es.fidelity < 55.0
    assert "web1" in sync.drift_alerts()
    # forced mode override
    sync.force_mode("web1", "HYBRID")
    tick = eng.step()
    sync.update(tick, now=now + 20)
    assert sync.entities["web1"].mode == "HYBRID"
    sync.force_mode("web1", "auto")
    snap = sync.snapshot()
    assert snap[0]["entity_id"] == "web1"
    assert snap[0]["samples"] > 0
