"""Enterprise topology: ~34 nodes, typed links, BFS shortest paths."""
from __future__ import annotations

from collections import deque

import json
from pathlib import Path

from nettwin.models import Link, Node


def _n(id: str, label: str, kind: str, x: float, y: float, role: str = "") -> Node:
    return Node(id=id, label=label, kind=kind, x=x, y=y, role=role)  # type: ignore[arg-type]


class Topology:
    def __init__(
        self,
        nodes: list[Node],
        links: list[Link],
        name: str = "default",
        title: str = "Enterprise Network",
        description: str = "",
        tiers: list[dict] | None = None,
    ) -> None:
        ids = [n.id for n in nodes]
        assert len(ids) == len(set(ids)), "duplicate node ids"
        lids = [l.id for l in links]
        assert len(lids) == len(set(lids)), "duplicate link ids"
        self.name = name
        self.title = title
        self.description = description
        self.tiers = tiers or []
        self.nodes: dict[str, Node] = {n.id: n for n in nodes}
        self.links: dict[str, Link] = {l.id: l for l in links}
        self.adjacency: dict[str, list[str]] = {n.id: [] for n in nodes}
        self.link_between: dict[tuple[str, str], str] = {}
        for link in links:
            assert link.src in self.nodes and link.dst in self.nodes
            self.adjacency[link.src].append(link.dst)
            self.adjacency[link.dst].append(link.src)
            self.link_between[(link.src, link.dst)] = link.id
            self.link_between[(link.dst, link.src)] = link.id
        self.paths: dict[tuple[str, str], list[str]] = {}
        self.recompute_paths()

    def recompute_paths(self, exclude_links: set[str] | None = None,
                        exclude_nodes: set[str] | None = None) -> None:
        exclude_links = exclude_links or set()
        exclude_nodes = exclude_nodes or set()
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes if nid not in exclude_nodes}
        for link in self.links.values():
            if link.id in exclude_links:
                continue
            if link.src in exclude_nodes or link.dst in exclude_nodes:
                continue
            adj[link.src].append(link.dst)
            adj[link.dst].append(link.src)
        self.paths = {}
        for src in adj:
            prev: dict[str, str | None] = {src: None}
            q: deque[str] = deque([src])
            while q:
                cur = q.popleft()
                for nxt in adj[cur]:
                    if nxt not in prev:
                        prev[nxt] = cur
                        q.append(nxt)
            for dst in prev:
                if dst == src:
                    continue
                path = [dst]
                while path[-1] != src:
                    path.append(prev[path[-1]])  # type: ignore[arg-type]
                path.reverse()
                self.paths[(src, dst)] = path

    def path_links(self, path: list[str]) -> list[str]:
        out = []
        for a, b in zip(path, path[1:]):
            lid = self.link_between.get((a, b))
            if lid:
                out.append(lid)
        return out

    def neighbors(self, node_id: str) -> list[str]:
        return list(self.adjacency.get(node_id, []))

    def links_of(self, node_id: str) -> list[str]:
        return [l.id for l in self.links.values()
                if l.src == node_id or l.dst == node_id]

    def is_connected(self) -> bool:
        start = next(iter(self.nodes))
        seen = {start}
        q: deque[str] = deque([start])
        while q:
            cur = q.popleft()
            for nxt in self.adjacency[cur]:
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        return len(seen) == len(self.nodes)

    def snapshot(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "tiers": self.tiers,
            "nodes": [n.model_copy(deep=True) for n in self.nodes.values()],
            "links": [l.model_copy(deep=True) for l in self.links.values()],
            "paths": {k: list(v) for k, v in self.paths.items()},
        }

    @classmethod
    def restore(cls, snap: dict) -> "Topology":
        nodes = snap["nodes"]
        links = snap["links"]
        if nodes and isinstance(nodes[0], dict):
            nodes = [Node(**n) for n in nodes]
        if links and isinstance(links[0], dict):
            links = [Link(**l) for l in links]
        topo = cls(
            nodes=nodes,
            links=links,
            name=snap.get("name", "default"),
            title=snap.get("title", "Enterprise Network"),
            description=snap.get("description", ""),
            tiers=snap.get("tiers", []),
        )
        topo.paths = {k: list(v) for k, v in snap.get("paths", {}).items()}
        return topo

    @classmethod
    def from_dict(cls, data: dict) -> "Topology":
        nodes = [Node(**n) for n in data["nodes"]]
        links = [Link(**l) for l in data["links"]]
        return cls(
            nodes=nodes,
            links=links,
            name=data.get("name", "custom"),
            title=data.get("title", data.get("name", "Custom Topology")),
            description=data.get("description", ""),
            tiers=data.get("tiers", []),
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "Topology":
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)


def build_topology() -> Topology:
    nodes = [
        _n("igw", "Internet GW", "internet_gateway", 640, 70),
        _n("attacker", "External Attacker", "attacker", 1060, 70),
        _n("fw1", "Perimeter FW", "firewall", 640, 160),
        _n("core1", "Core R1", "core_router", 470, 250),
        _n("core2", "Core R2", "core_router", 810, 250),
        _n("dist1", "Dist SW1", "distribution_switch", 180, 350),
        _n("dist2", "Dist SW2", "distribution_switch", 470, 350),
        _n("dist3", "Dist SW3", "distribution_switch", 810, 350),
        _n("dist4", "Dist SW4", "distribution_switch", 1080, 350),
        _n("edge1", "Edge SW1", "edge_switch", 100, 460),
        _n("edge2", "Edge SW2", "edge_switch", 290, 460),
        _n("edge3", "Edge SW3", "edge_switch", 450, 460),
        _n("edge4", "Edge SW4", "edge_switch", 610, 460),
        _n("edge5", "Edge SW5", "edge_switch", 770, 460),
        _n("edge6", "Edge SW6", "edge_switch", 900, 460),
        _n("edge7", "Edge SW7", "edge_switch", 1020, 460),
        _n("edge8", "Edge SW8", "edge_switch", 1170, 460),
        _n("ws1", "WS-01", "workstation", 45, 580),
        _n("ws2", "WS-02", "workstation", 140, 580),
        _n("ws3", "WS-03", "workstation", 250, 580),
        _n("ws4", "WS-04", "workstation", 335, 580),
        _n("web1", "Web Srv 1", "server", 385, 580, "web"),
        _n("web2", "Web Srv 2", "server", 460, 580, "web"),
        _n("dns1", "DNS Srv", "server", 530, 580, "dns"),
        _n("app1", "App Srv 1", "server", 580, 580, "app"),
        _n("db1", "DB Srv 1", "server", 580, 672, "db"),
        _n("app2", "App Srv 2", "server", 660, 580, "app"),
        _n("db2", "DB Srv 2", "server", 660, 672, "db"),
        _n("iot1", "IoT-01", "iot", 735, 580),
        _n("iot2", "IoT-02", "iot", 800, 580),
        _n("iot3", "IoT-03", "iot", 865, 580),
        _n("iot4", "IoT-04", "iot", 930, 580),
        _n("ws5", "WS-05", "workstation", 990, 580),
        _n("ws6", "WS-06", "workstation", 1060, 580),
        _n("iot5", "IoT-05", "iot", 1140, 580),
    ]
    L = []

    def link(lid: str, a: str, b: str, bw: float, lat: float = 0.5, kind: str = "ethernet") -> None:
        L.append(Link(id=lid, src=a, dst=b, bandwidth_mbps=bw, base_latency_ms=lat, kind=kind))

    link("igw-fw1", "igw", "fw1", 1000, 1.0, "wan")
    link("attacker-igw", "attacker", "igw", 1000, 2.0, "internet")
    link("fw1-core1", "fw1", "core1", 1000, 0.4)
    link("fw1-core2", "fw1", "core2", 1000, 0.4)
    link("core1-core2", "core1", "core2", 2000, 0.3)
    link("core1-dist1", "core1", "dist1", 1000, 0.4)
    link("core1-dist2", "core1", "dist2", 1000, 0.4)
    link("core2-dist3", "core2", "dist3", 1000, 0.4)
    link("core2-dist4", "core2", "dist4", 1000, 0.4)
    link("core2-dist2", "core2", "dist2", 400, 0.6, "backup")
    link("core1-dist3", "core1", "dist3", 400, 0.6, "backup")
    pairs = [("dist1", ["edge1", "edge2"]), ("dist2", ["edge3", "edge4"]),
             ("dist3", ["edge5", "edge6"]), ("dist4", ["edge7", "edge8"])]
    for dist, edges in pairs:
        for e in edges:
            link(f"{dist}-{e}", dist, e, 1000, 0.3)
    leaves = [
        ("edge1", [("ws1", 100), ("ws2", 100)]),
        ("edge2", [("ws3", 100), ("ws4", 100)]),
        ("edge3", [("web1", 500), ("web2", 500), ("dns1", 500)]),
        ("edge4", [("app1", 500), ("db1", 500), ("app2", 500), ("db2", 500)]),
        ("edge5", [("iot1", 100), ("iot2", 100)]),
        ("edge6", [("iot3", 100), ("iot4", 100)]),
        ("edge7", [("ws5", 100), ("ws6", 100)]),
        ("edge8", [("iot5", 100)]),
    ]
    for edge, children in leaves:
        for child, bw in children:
            link(f"{edge}-{child}", edge, child, bw, 0.2)
    return Topology(
        nodes,
        L,
        name="default",
        title="Enterprise Campus (35 Nodes)",
        description="Generic Enterprise Campus topology with 35 nodes across core, distribution, edge switches and endpoints.",
    )
