"""Scalable topology generator for scalability experiments.

Generates enterprise topologies of 35/70/140/280/500 nodes following the same
core→distribution→edge→endpoints pattern as the original 35-node topology.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nettwin.simulator.topology import Topology, build_topology
from nettwin.models import Node, Link


def build_scaled_topology(n_nodes: int = 35) -> Topology:
    """Generate a hierarchical enterprise topology with approximately n_nodes nodes.

    Structure per block (≈35 nodes):
      1 internet_gateway, 1 firewall, 1 core_router,
      2 distribution_switches, 4 edge_switches,
      ~24 endpoints (servers, workstations, IoT), 1 attacker
    """
    if n_nodes <= 35:
        return build_topology()

    # number of blocks
    n_blocks = max(1, round(n_nodes / 35))
    nodes: list[Node] = []
    links: list[Link] = []
    node_ids: set[str] = set()
    link_id = 0

    def add_node(nid: str, label: str, kind: str, x: float, y: float,
                 role: str = "") -> str:
        if nid not in node_ids:
            nodes.append(Node(id=nid, label=label, kind=kind, x=x, y=y, role=role))
            node_ids.add(nid)
        return nid

    def add_link(src: str, dst: str, bw: float = 1000.0,
                 lat: float = 0.5) -> str:
        nonlocal link_id
        link_id += 1
        lid = f"l{link_id}"
        links.append(Link(id=lid, src=src, dst=dst,
                          bandwidth_mbps=bw, base_latency_ms=lat))
        return lid

    # Shared infrastructure
    igw = add_node("igw", "Internet GW", "internet_gateway", 400, 50)
    fw = add_node("fw", "Firewall", "firewall", 400, 120)
    add_link(igw, fw, 10000, 0.2)
    attacker = add_node("attacker", "Attacker", "attacker", 100, 50)
    add_link(attacker, igw, 1000, 5.0)

    for block in range(n_blocks):
        bx = block * 500
        prefix = f"b{block}_"

        core = add_node(f"{prefix}core", f"Core-{block}", "core_router",
                        bx + 400, 200)
        add_link(fw, core, 10000, 0.3)

        for d in range(2):
            dist = add_node(f"{prefix}dist{d}", f"Dist-{block}-{d}",
                            "distribution_switch", bx + 250 + d * 300, 300)
            add_link(core, dist, 5000, 0.4)

            for e in range(2):
                edge = add_node(f"{prefix}e{d}s{e}", f"Edge-{block}-{d}-{e}",
                                "edge_switch", bx + 200 + d * 300 + e * 100, 400)
                add_link(dist, edge, 2000, 0.5)

                # endpoints
                roles = ["web", "app", "db", "workstation", "iot", "server"]
                for ep in range(6):
                    role = roles[ep % len(roles)]
                    kind = ("server" if role in ("web", "app", "db", "server")
                            else "workstation" if role == "workstation" else "iot")
                    eid = f"{prefix}n{d}{e}{ep}"
                    add_node(eid, f"{role}-{block}-{d}-{e}-{ep}", kind,
                             bx + 150 + d * 300 + e * 100 + ep * 15, 500,
                             role=role)
                    bw = 1000 if kind == "server" else 500 if kind == "workstation" else 100
                    add_link(edge, eid, bw, 0.5)

    # Use the proper Topology constructor which handles adjacency, link_between, and paths
    return Topology(nodes, links)


def topology_sizes() -> dict[int, int]:
    """Return map of target_size -> actual_node_count for the scaling experiments."""
    sizes = {}
    for target in [35, 70, 140, 280, 500]:
        topo = build_scaled_topology(target)
        sizes[target] = len(topo.nodes)
    return sizes
