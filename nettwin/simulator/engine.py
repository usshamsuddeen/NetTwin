"""SimulationEngine: tick loop, flow routing, congestion model, metrics."""
from __future__ import annotations

import asyncio
import copy
import os
from pathlib import Path
import time
from typing import Any, Awaitable, Callable

import numpy as np

from nettwin.config import Settings
from nettwin.models import (AttackEvent, Flow, Link, LinkMetrics, Node,
                            NodeMetrics, TelemetryTick)
from nettwin.simulator.attacks import ATTACK_TYPES, Attack, make_attack
from nettwin.simulator.topology import Topology, build_topology
from nettwin.simulator.traffic import RawFlow, TrafficGenerator

TickCallback = Callable[[TelemetryTick], Awaitable[None]]

_KIND_PROFILE = {
    "internet_gateway": (8.0, 22.0), "firewall": (18.0, 40.0),
    "core_router": (22.0, 45.0), "distribution_switch": (14.0, 32.0),
    "edge_switch": (9.0, 26.0), "server": (28.0, 46.0),
    "workstation": (7.0, 38.0), "iot": (3.0, 15.0), "attacker": (12.0, 30.0),
}


class SimulationEngine:
    def __init__(self, settings: Settings, topology: Topology | None = None,
                 seed: int | None = None) -> None:
        self.settings = settings
        if topology is not None:
            self.topology = topology
        else:
            topo_path = os.environ.get("TOPOLOGY") or getattr(settings, "topology_path", None)
            if topo_path and Path(topo_path).exists():
                self.topology = Topology.from_json_file(topo_path)
            else:
                self.topology = build_topology()
        self.rng = np.random.default_rng(settings.seed if seed is None else seed)
        self.traffic = TrafficGenerator(self.topology, seed=settings.seed)
        self.attacks: dict[str, Attack] = {}
        self.attack_history: list[AttackEvent] = []
        self.tick = 0
        self.tick_s = settings.tick_s
        self.running = False
        self.paused = False
        self.started_at = time.time()
        self.failed_links: set[str] = set()
        self.failed_nodes: set[str] = set()
        self.isolated_nodes: set[str] = set()   # response-policy isolation (reversible)
        self.policy_links: set[str] = set()     # response-policy reroutes (reversible)
        self.policies: dict[str, dict] = {}
        self._policy_seq = 0
        self._subs: list[TickCallback] = []
        self._task: asyncio.Task[None] | None = None
        self._attack_seq = 0
        self._auto_task: asyncio.Task[None] | None = None

    def switch_topology(self, new_topo: Topology) -> None:
        self.topology = new_topo
        self.traffic = TrafficGenerator(self.topology, seed=self.settings.seed)
        self.failed_links.clear()
        self.failed_nodes.clear()
        self.isolated_nodes.clear()
        self.policy_links.clear()
        self.policies.clear()
        self.attacks.clear()

    # ---- subscription / lifecycle -------------------------------------
    def subscribe(self, cb: TickCallback) -> None:
        self._subs.append(cb)

    async def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._loop())
        if self.settings.auto_attacks:
            self._auto_task = asyncio.create_task(self._auto_attack_loop())

    async def stop(self) -> None:
        self.running = False
        for task in (self._task, self._auto_task):
            if task:
                task.cancel()
        for task in (self._task, self._auto_task):
            if task:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
        self._task = self._auto_task = None

    async def _loop(self) -> None:
        while self.running:
            started = time.perf_counter()
            if not self.paused:
                tick = self.step()
                for cb in self._subs:
                    try:
                        await cb(tick)
                    except Exception:
                        import traceback
                        traceback.print_exc()
            elapsed = time.perf_counter() - started
            await asyncio.sleep(max(0.01, self.tick_s - elapsed))

    async def _auto_attack_loop(self) -> None:
        kinds = [k for k in ATTACK_TYPES if k != "lateral"]
        while self.running:
            await asyncio.sleep(float(self.rng.integers(90, 180)))
            if self.paused or self.attacks:
                continue
            kind = kinds[int(self.rng.integers(0, len(kinds)))]
            target = str(self.rng.choice(["web1", "web2", "db1", "app1"]))
            self.start_attack(kind, target, duration_s=45.0)

    # ---- snapshot / clone ------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        return {
            "settings": copy.deepcopy(self.settings),
            "topology": self.topology.snapshot(),
            "rng_state": copy.deepcopy(self.rng.bit_generator.state),
            "traffic": self.traffic.snapshot(),
            "attacks": {aid: atk.snapshot() for aid, atk in self.attacks.items()},
            "attack_history": [e.model_copy(deep=True) for e in self.attack_history],
            "tick": self.tick,
            "tick_s": self.tick_s,
            "paused": self.paused,
            "started_at": self.started_at,
            "failed_links": set(self.failed_links),
            "failed_nodes": set(self.failed_nodes),
            "isolated_nodes": set(self.isolated_nodes),
            "policy_links": set(self.policy_links),
            "policies": copy.deepcopy(self.policies),
            "_policy_seq": self._policy_seq,
            "_attack_seq": self._attack_seq,
        }

    @classmethod
    def restore(cls, snap: dict[str, Any]) -> "SimulationEngine":
        eng = cls.__new__(cls)
        eng.settings = snap["settings"]
        eng.topology = Topology.restore(snap["topology"])
        eng.rng = np.random.default_rng(0)
        eng.rng.bit_generator.state = copy.deepcopy(snap["rng_state"])
        eng.traffic = TrafficGenerator.restore(snap["traffic"], eng.topology)
        eng.attacks = {aid: Attack.restore(s) for aid, s in snap["attacks"].items()}
        eng.attack_history = list(snap["attack_history"])
        eng.tick = snap["tick"]
        eng.tick_s = snap["tick_s"]
        eng.running = False
        eng.paused = snap["paused"]
        eng.started_at = snap["started_at"]
        eng.failed_links = set(snap["failed_links"])
        eng.failed_nodes = set(snap["failed_nodes"])
        eng.isolated_nodes = set(snap["isolated_nodes"])
        eng.policy_links = set(snap["policy_links"])
        eng.policies = copy.deepcopy(snap["policies"])
        eng._policy_seq = snap["_policy_seq"]
        eng._subs: list[TickCallback] = []
        eng._task = None
        eng._auto_task = None
        eng._attack_seq = snap["_attack_seq"]
        return eng

    def clone(self) -> "SimulationEngine":
        return self.restore(self.snapshot())

    # ---- attacks --------------------------------------------------------
    def start_attack(self, attack_type: str, target_id: str | None = None,
                     duration_s: float | None = None) -> AttackEvent:
        if attack_type not in ATTACK_TYPES:
            raise ValueError(f"unknown attack type: {attack_type}")
        if target_id and target_id not in self.topology.nodes:
            raise ValueError(f"unknown target node: {target_id}")
        self._attack_seq += 1
        event = AttackEvent(attack_type=attack_type, target_id=target_id,
                            source_id="attacker" if attack_type != "lateral" else "ws2",
                            start_tick=self.tick, duration_s=duration_s)
        self.attacks[event.id] = make_attack(attack_type, event, seed=self._attack_seq * 7 + 1)
        self.attack_history.append(event)
        return event

    def stop_attack(self, attack_id: str | None = None) -> int:
        stopped = 0
        for aid, atk in list(self.attacks.items()):
            if attack_id is None or aid == attack_id:
                atk.stop()
                del self.attacks[aid]
                stopped += 1
        return stopped

    # ---- failure scenarios (used by what-if) ----------------------------
    def fail_link(self, link_id: str) -> None:
        self.failed_links.add(link_id)
        self._refresh_paths()

    def fail_node(self, node_id: str) -> None:
        self.failed_nodes.add(node_id)
        self.traffic.excluded.add(node_id)
        self._refresh_paths()

    def set_surge(self, factor: float) -> None:
        self.traffic.surge = factor

    def _refresh_paths(self) -> None:
        excluded_nodes = self.failed_nodes | self.isolated_nodes
        self.traffic.excluded = set(excluded_nodes)
        self.topology.recompute_paths(
            exclude_links=set(self.failed_links) | set(self.policy_links),
            exclude_nodes=set(excluded_nodes))

    # ---- response policies (rate_limit / block_flow / reroute / isolate) --
    def apply_policy(self, kind: str, **params) -> dict:
        self._policy_seq += 1
        pid = f"pol-{self._policy_seq}"
        policy = {"id": pid, "kind": kind, **params}
        if kind == "isolate":
            node = params.get("node")
            if node not in self.topology.nodes:
                raise ValueError(f"unknown node: {node}")
            self.isolated_nodes.add(node)
            self._refresh_paths()
        elif kind == "reroute":
            link = params.get("link")
            if link not in self.topology.links:
                raise ValueError(f"unknown link: {link}")
            self.policy_links.add(link)
            self._refresh_paths()
        elif kind in ("block_flow", "rate_limit"):
            for key in ("src",):
                if params.get(key) and params[key] not in self.topology.nodes:
                    raise ValueError(f"unknown node: {params[key]}")
            if params.get("dst") and params["dst"] not in self.topology.nodes:
                raise ValueError(f"unknown node: {params['dst']}")
        else:
            self._policy_seq -= 1
            raise ValueError(f"unknown policy kind: {kind}")
        self.policies[pid] = policy
        return policy

    def revert_policy(self, pid: str) -> bool:
        policy = self.policies.pop(pid, None)
        if not policy:
            return False
        if policy["kind"] == "isolate":
            self.isolated_nodes.discard(policy["node"])
            self._refresh_paths()
        elif policy["kind"] == "reroute":
            self.policy_links.discard(policy["link"])
            self._refresh_paths()
        return True

    def _policy_filter(self, raw: list[RawFlow], tick_s: float) -> list[RawFlow]:
        if not self.policies:
            return raw
        budgets: dict[str, float] = {}
        out: list[RawFlow] = []
        for f in raw:
            drop = False
            for p in self.policies.values():
                if p["kind"] == "block_flow":
                    if f.src != p.get("src"):
                        continue
                    if p.get("dst") and f.dst != p["dst"]:
                        continue
                    if p.get("proto") and p["proto"].upper() not in f.protocol.upper():
                        continue
                    drop = True
                    break
            if drop:
                continue
            out.append(f)
        for p in self.policies.values():
            if p["kind"] == "rate_limit":
                budgets[p["id"]] = float(p.get("bps", 1e7)) / 8.0 * tick_s
        if budgets:
            kept: list[RawFlow] = []
            for f in out:
                limited = False
                for p in self.policies.values():
                    if p["kind"] != "rate_limit" or f.src != p.get("src"):
                        continue
                    if p.get("dst") and f.dst != p["dst"]:
                        continue
                    limited = True
                    pid = p["id"]
                    if budgets[pid] >= f.bytes:
                        budgets[pid] -= f.bytes
                        kept.append(f)
                    break
                if not limited:
                    kept.append(f)
            out = kept
        return out

    # ---- core step ------------------------------------------------------
    def step(self) -> TelemetryTick:
        self.tick += 1
        rng = self.rng
        tick_s = self.tick_s

        raw: list[RawFlow] = self.traffic.generate(self.tick)
        for aid, atk in list(self.attacks.items()):
            if atk.expired(self.tick, tick_s):
                atk.stop()
                del self.attacks[aid]
                continue
            raw.extend(atk.flows(self.tick))

        raw = self._policy_filter(raw, tick_s)

        link_bytes = {lid: 0 for lid in self.topology.links}
        link_pkts = {lid: 0 for lid in self.topology.links}
        node_tx = {nid: 0 for nid in self.topology.nodes}
        node_rx = {nid: 0 for nid in self.topology.nodes}
        node_pkts = {nid: 0 for nid in self.topology.nodes}
        node_dsts: dict[str, set[str]] = {nid: set() for nid in self.topology.nodes}
        offered_total = 0
        routed_total = 0
        flow_records: list[Flow] = []

        for f in raw:
            excluded = self.failed_nodes | self.isolated_nodes
            if f.src in excluded or f.dst in excluded:
                offered_total += f.bytes
                continue
            path = self.topology.paths.get((f.src, f.dst))
            if not path:
                offered_total += f.bytes
                continue
            offered_total += f.bytes
            routed_total += f.bytes
            for lid in self.topology.path_links(path):
                link_bytes[lid] += f.bytes
                link_pkts[lid] += f.packets
            node_tx[f.src] += f.bytes
            node_rx[f.dst] += f.bytes
            node_pkts[f.src] += f.packets
            node_pkts[f.dst] += f.packets
            node_dsts[f.src].add(f.dst)
            if len(flow_records) < 48:
                flow_records.append(Flow(src=f.src, dst=f.dst, protocol=f.protocol,
                                         bytes=f.bytes, packets=f.packets, path=path))

        # link metrics with congestion
        link_metrics: dict[str, LinkMetrics] = {}
        node_link_util: dict[str, float] = {nid: 0.0 for nid in self.topology.nodes}
        node_link_loss: dict[str, float] = {nid: 0.0 for nid in self.topology.nodes}
        node_link_lat: dict[str, float] = {nid: 0.0 for nid in self.topology.nodes}
        for lid, link in self.topology.links.items():
            if lid in self.failed_links:
                link_metrics[lid] = LinkMetrics(utilization_pct=0.0, packet_loss_pct=100.0,
                                                latency_ms=999.0)
                continue
            offered_mbps = link_bytes[lid] * 8.0 / tick_s / 1e6
            util = offered_mbps / link.bandwidth_mbps if link.bandwidth_mbps > 0 else 0.0
            capped_mbps = min(offered_mbps, link.bandwidth_mbps * 1.02)
            dropped = max(0.0, offered_mbps - capped_mbps)
            lat = link.base_latency_ms
            loss = 0.0
            if util > 0.85:
                lat += link.base_latency_ms * 6.0 * (util - 0.85) * 10.0
                loss += (util - 0.85) * 3.0
            if util > 1.0:
                loss += (util - 1.0) * 25.0
                lat += (util - 1.0) * 15.0
            lat += abs(float(rng.normal(0, 0.15)))
            loss = min(100.0, loss + abs(float(rng.normal(0, 0.02))))
            link_metrics[lid] = LinkMetrics(
                throughput_mbps=round(capped_mbps, 3),
                pps=round(link_pkts[lid] / tick_s, 1),
                utilization_pct=round(util * 100.0, 2),
                latency_ms=round(lat, 3),
                packet_loss_pct=round(loss, 3),
                dropped_mbps=round(dropped, 3))
            for nid in (link.src, link.dst):
                if util > node_link_util[nid]:
                    node_link_util[nid] = util
                if loss > node_link_loss[nid]:
                    node_link_loss[nid] = loss
                if lat > node_link_lat[nid]:
                    node_link_lat[nid] = lat

        dropped_flows_pct = (100.0 * (offered_total - routed_total) / offered_total
                             if offered_total else 0.0)

        node_metrics: dict[str, NodeMetrics] = {}
        for nid, node in self.topology.nodes.items():
            tx = node_tx[nid] * 8.0 / tick_s / 1e6
            rx = node_rx[nid] * 8.0 / tick_s / 1e6
            pps = node_pkts[nid] / tick_s
            base_cpu, base_mem = _KIND_PROFILE.get(node.kind, (10.0, 30.0))
            load = min(1.0, (tx + rx) / 900.0)
            cpu = base_cpu + 55.0 * load + pps / 4000.0 + float(rng.normal(0, 1.2))
            mem = base_mem + 12.0 * load + float(rng.normal(0, 0.8))
            util = node_link_util[nid]
            lat = 0.3 + node_link_lat[nid] + float(rng.normal(0, 0.1))
            jitter = 0.2 + max(0.0, util - 0.8) * 8.0 + abs(float(rng.normal(0, 0.15)))
            loss = min(100.0, node_link_loss[nid] + dropped_flows_pct * 0.1
                       + abs(float(rng.normal(0, 0.02))))
            total = tx + rx
            node_metrics[nid] = NodeMetrics(
                throughput_mbps=round(tx + rx, 3), tx_mbps=round(tx, 3),
                rx_mbps=round(rx, 3), pps=round(pps, 1),
                latency_ms=round(max(0.05, lat), 3),
                jitter_ms=round(max(0.01, jitter), 3),
                packet_loss_pct=round(loss, 3),
                cpu_pct=round(float(np.clip(cpu, 1.0, 100.0)), 2),
                mem_pct=round(float(np.clip(mem, 5.0, 99.0)), 2),
                fanout=len(node_dsts[nid]),
                bytes_ratio=round(tx / total, 4) if total > 0 else 0.5)

        hour = (self.tick / 60.0) % 24.0
        return TelemetryTick(
            tick=self.tick, sim_time_s=self.tick * tick_s, hour_of_day=round(hour, 2),
            nodes=node_metrics, links=link_metrics, flows=flow_records,
            active_attacks=[a.event for a in self.attacks.values()])
