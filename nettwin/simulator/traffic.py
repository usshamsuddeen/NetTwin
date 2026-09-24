"""Benign traffic generation with diurnal pattern and protocol mix."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from nettwin.simulator.topology import Topology

WORKSTATIONS = ["ws1", "ws2", "ws3", "ws4", "ws5", "ws6"]
WEB_SERVERS = ["web1", "web2"]
APP_SERVERS = ["app1", "app2"]
DB_SERVERS = ["db1", "db2"]
IOT_DEVICES = ["iot1", "iot2", "iot3", "iot4", "iot5"]
DNS_SERVER = "dns1"


@dataclass
class RawFlow:
    src: str
    dst: str
    protocol: str
    bytes: int
    packets: int


def _pkts(nbytes: int, avg_size: float = 900.0) -> int:
    return max(1, int(nbytes / avg_size))


class TrafficGenerator:
    """Generates per-tick benign flows. 1 tick ~= 1 simulated minute of mix
    compressed into the tick, scaled by a diurnal cycle (period 1440 ticks)."""

    def __init__(self, topo: Topology, seed: int = 42, surge: float = 1.0) -> None:
        self.topo = topo
        self.rng = np.random.default_rng(seed)
        self.surge = surge
        self.excluded: set[str] = set()  # failed nodes generate no traffic

    def diurnal(self, tick: int) -> float:
        hour = (tick / 60.0) % 24.0
        base = 0.45 + 0.55 * (0.5 + 0.5 * math.sin((hour - 7.0) / 24.0 * 2.0 * math.pi))
        return base * self.surge

    def _size(self, mean_kb: float, spread: float = 0.6) -> int:
        kb = float(self.rng.lognormal(math.log(max(mean_kb, 0.1)), spread))
        return max(60, int(min(kb, 500.0) * 1024))

    def snapshot(self) -> dict:
        return {
            "rng_state": self.rng.bit_generator.state,
            "surge": self.surge,
            "excluded": set(self.excluded),
        }

    @classmethod
    def restore(cls, snap: dict, topo: Topology) -> "TrafficGenerator":
        tg = cls.__new__(cls)
        tg.topo = topo
        tg.rng = np.random.default_rng(0)
        tg.rng.bit_generator.state = snap["rng_state"]
        tg.surge = snap["surge"]
        tg.excluded = set(snap["excluded"])
        return tg

    def generate(self, tick: int) -> list[RawFlow]:
        rng = self.rng
        flows: list[RawFlow] = []
        diur = self.diurnal(tick)
        live = lambda nid: nid not in self.excluded

        for ws in WORKSTATIONS:
            if not live(ws):
                continue
            if rng.random() < 0.85 * diur:
                for _ in range(int(rng.integers(1, 4))):
                    dst = WEB_SERVERS[int(rng.integers(0, len(WEB_SERVERS)))]
                    if live(dst):
                        b = self._size(60 * diur + 15)
                        flows.append(RawFlow(ws, dst, "HTTPS", b, _pkts(b)))
            if rng.random() < 0.5 * diur and live(DNS_SERVER):
                flows.append(RawFlow(ws, DNS_SERVER, "DNS", 256, 1))
            if rng.random() < 0.06 * diur:
                dst = WEB_SERVERS[int(rng.integers(0, 2))]
                if live(dst):
                    b = self._size(400)
                    flows.append(RawFlow(ws, dst, "HTTP", b, _pkts(b)))

        for app in APP_SERVERS:
            if not live(app):
                continue
            for db in DB_SERVERS:
                if live(db) and rng.random() < 0.9 * diur:
                    b = self._size(60 * diur + 10, 0.6)
                    flows.append(RawFlow(app, db, "SQL", b, _pkts(b, 700)))
            if live(DNS_SERVER) and rng.random() < 0.3:
                flows.append(RawFlow(app, DNS_SERVER, "DNS", 200, 1))

        for dev in IOT_DEVICES:
            if live(dev) and live(APP_SERVERS[0]):
                b = int(180 + rng.normal(0, 30))
                flows.append(RawFlow(dev, APP_SERVERS[0], "MQTT", max(80, b), 1))

        if tick % 90 == 45:  # periodic backup window
            if live(DB_SERVERS[0]) and live(DB_SERVERS[1]):
                b = self._size(9000, 0.2)
                flows.append(RawFlow(DB_SERVERS[0], DB_SERVERS[1], "SMB", b, _pkts(b, 1400)))

        if rng.random() < 0.25 * diur:  # admin SSH sessions
            ws = WORKSTATIONS[int(rng.integers(0, len(WORKSTATIONS)))]
            dst = APP_SERVERS[int(rng.integers(0, 2))]
            if live(ws) and live(dst):
                flows.append(RawFlow(ws, dst, "SSH", int(800 + rng.normal(0, 200)), 4))

        return flows
