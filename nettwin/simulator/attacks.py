"""Composable attack scenarios that inject malicious flows while active."""
from __future__ import annotations

import numpy as np

from nettwin.models import AttackEvent
from nettwin.simulator.traffic import DB_SERVERS, WEB_SERVERS, WORKSTATIONS, RawFlow

ATTACK_TYPES = ["ddos", "portscan", "exfiltration", "lateral", "bruteforce"]


class Attack:
    attack_type = "base"

    def __init__(self, event: AttackEvent, seed: int = 0) -> None:
        self.event = event
        self.rng = np.random.default_rng(seed)

    def expired(self, tick: int, tick_s: float) -> bool:
        if self.event.duration_s is None:
            return False
        return (tick - self.event.start_tick) * tick_s >= self.event.duration_s

    def flows(self, tick: int) -> list[RawFlow]:
        return []

    def stop(self) -> None:
        self.event.active = False
        import time
        self.event.ended_at = time.time()

    def snapshot(self) -> dict:
        return {
            "type": self.attack_type,
            "event": self.event.model_copy(deep=True),
            "rng_state": self.rng.bit_generator.state,
        }

    @classmethod
    def restore(cls, snap: dict) -> "Attack":
        attack_cls = _ATTACK_CLASSES[snap["type"]]
        atk = attack_cls.__new__(attack_cls)
        atk.event = snap["event"]
        atk.rng = np.random.default_rng(0)
        atk.rng.bit_generator.state = snap["rng_state"]
        atk._restore_extra(snap)
        return atk

    def _restore_extra(self, snap: dict) -> None:
        pass


class DDoSFlood(Attack):
    """High-volume UDP flood from the external attacker toward one target."""
    attack_type = "ddos"

    def __init__(self, event: AttackEvent, seed: int = 0, rate_mbps: float = 900.0) -> None:
        super().__init__(event, seed)
        self.rate_mbps = rate_mbps

    def snapshot(self) -> dict:
        s = super().snapshot()
        s["rate_mbps"] = self.rate_mbps
        return s

    def _restore_extra(self, snap: dict) -> None:
        self.rate_mbps = snap.get("rate_mbps", 900.0)

    def flows(self, tick: int) -> list[RawFlow]:
        target = self.event.target_id or WEB_SERVERS[0]
        n = 24
        per = int(self.rate_mbps * 1e6 / 8.0 / n)
        out = []
        for _ in range(n):
            b = int(per * (0.8 + 0.4 * self.rng.random()))
            out.append(RawFlow("attacker", target, "UDP", b, max(1, b // 512)))
        return out


class PortScan(Attack):
    """High fanout of tiny TCP probes across internal hosts."""
    attack_type = "portscan"

    def flows(self, tick: int) -> list[RawFlow]:
        targets = WORKSTATIONS + WEB_SERVERS + DB_SERVERS + ["app1", "app2", "dns1"]
        out = []
        for dst in targets:
            for _ in range(8):
                out.append(RawFlow("attacker", dst, "TCP-SYN", 60, 1))
        return out


class DataExfiltration(Attack):
    """Sustained large egress from a server out to the attacker."""
    attack_type = "exfiltration"

    def flows(self, tick: int) -> list[RawFlow]:
        src = self.event.target_id or DB_SERVERS[0]
        out = []
        for _ in range(6):
            b = int(6_500_000 * (0.85 + 0.3 * self.rng.random()))
            out.append(RawFlow(src, "attacker", "HTTPS", b, b // 1400))
        return out


class LateralMovement(Attack):
    """Sequential internal host-to-host compromise pattern."""
    attack_type = "lateral"

    CHAIN = ["ws2", "ws3", "app1", "db1"]

    def flows(self, tick: int) -> list[RawFlow]:
        stage = min((tick - self.event.start_tick) // 12, len(self.CHAIN) - 2)
        stage = max(stage, 0)
        src, dst = self.CHAIN[stage], self.CHAIN[stage + 1]
        out = []
        for _ in range(6):
            b = int(2_200_000 * (0.8 + 0.4 * self.rng.random()))
            proto = "SMB" if dst.startswith("ws") else "SSH"
            out.append(RawFlow(src, dst, proto, b, b // 1200))
        b = 900
        out.append(RawFlow(src, "attacker", "TLS-C2", b, 2))  # beacon
        return out


class BruteForce(Attack):
    """Repeated small SSH auth attempts against one server."""
    attack_type = "bruteforce"

    def flows(self, tick: int) -> list[RawFlow]:
        target = self.event.target_id or "app1"
        out = []
        for _ in range(55):
            b = int(400 + 150 * self.rng.random())
            out.append(RawFlow("attacker", target, "SSH", b, 2))
        return out


_ATTACK_CLASSES = {
    "ddos": DDoSFlood,
    "portscan": PortScan,
    "exfiltration": DataExfiltration,
    "lateral": LateralMovement,
    "bruteforce": BruteForce,
}


def make_attack(attack_type: str, event: AttackEvent, seed: int = 0) -> Attack:
    cls = _ATTACK_CLASSES[attack_type]
    return cls(event, seed=seed)


create_attack = make_attack
