"""Replay generator: emits realistic 'real network' telemetry over UDP.

Usage:
  python scripts/simulate_real_feed.py [--port 5514] [--rate 1.0]
      [--noise 0.1] [--drift 0.0] [--outage-at 0 --outage-len 10]
      [--duration 0]  (0 = forever)

Record schema matches nettwin/ingestion/normalize.py.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import socket
import sys
import time
import urllib.request


def twin_hosts(api: str) -> dict[str, tuple[float, float]]:
    """Current simulated throughput per node (match-twin mode)."""
    try:
        with urllib.request.urlopen(api + "/api/topology", timeout=2) as r:
            nodes = json.load(r)["nodes"]
        out = {}
        for node in nodes:
            eid = node["id"] if isinstance(node, dict) and "id" in node else node
            if not isinstance(eid, str):
                continue
            try:
                with urllib.request.urlopen(
                        api + f"/api/metrics?entity={eid}&window=1",
                        timeout=2) as r:
                    ser = json.load(r)["series"]
                if ser:
                    out[eid] = (float(ser[-1]["throughput_mbps"]),
                                float(ser[-1].get("cpu_pct", 30.0)))
            except Exception:
                continue
        return out
    except Exception:
        return {}

HOSTS = {
    # host key (sync_map ip or node id) -> base throughput mbps, cpu base
    # base_tp values are tuned to the simulator's steady-state means so a
    # matched feed reaches HYBRID fidelity (core1 is a pure transit router:
    # the sim models no endpoint traffic for it, so it is not fed).
    "10.0.3.11": (1.5, 30.0),   # web1
    "10.0.3.12": (1.4, 28.0),   # web2
    "10.0.3.13": (0.005, 15.0), # dns1
    "10.0.4.11": (0.35, 35.0),  # app1
    "10.0.4.21": (0.4, 40.0),   # db1
    "10.0.4.22": (0.35, 38.0),  # db2
    "10.0.1.5": (0.4, 12.0),    # ws1
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5514)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--rate", type=float, default=1.0, help="messages per second")
    ap.add_argument("--noise", type=float, default=0.1)
    ap.add_argument("--drift", type=float, default=0.0,
                    help="fractional throughput drift per minute (e.g. 0.2)")
    ap.add_argument("--outage-at", type=float, default=0.0,
                    help="seconds after start to stop sending (0 = never)")
    ap.add_argument("--outage-len", type=float, default=15.0)
    ap.add_argument("--duration", type=float, default=0.0, help="0 = run forever")
    ap.add_argument("--match-twin", action="store_true",
                    help="mirror the twin's live metrics (high-fidelity demo)")
    ap.add_argument("--api", default="http://127.0.0.1:8000")
    args = ap.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    started = time.time()
    sent = 0
    print(f"feeding udp://{args.host}:{args.port} rate={args.rate}/s "
          f"noise={args.noise} drift={args.drift}/min")
    while True:
        now = time.time()
        elapsed = now - started
        if args.duration and elapsed > args.duration:
            break
        if args.outage_at and args.outage_at <= elapsed < args.outage_at + args.outage_len:
            time.sleep(1.0 / max(args.rate, 0.1))
            continue
        hour = (elapsed / 60.0) % 24.0
        diur = 0.55 + 0.45 * (0.5 + 0.5 * math.sin((hour - 7.0) / 24.0 * 2 * math.pi))
        drift_mult = 1.0 + args.drift * (elapsed / 60.0)
        records = []
        hosts = HOSTS
        if args.match_twin:
            live = twin_hosts(args.api)
            if live:
                hosts = live
        for host, (base_tp, base_cpu) in hosts.items():
            jitter = 1.0 + random.gauss(0, args.noise)
            if args.match_twin:
                tp = max(0.001, base_tp * jitter)
            else:
                tp = max(0.001, base_tp * diur * drift_mult * jitter)
            in_bps = tp * 0.6 * 1e6
            out_bps = tp * 0.4 * 1e6
            pps = tp * 1e6 / 8.0 / 900.0
            records.append({"type": "interface", "host": host,
                            "in_bps": in_bps, "out_bps": out_bps,
                            "in_pps": pps * 0.6, "out_pps": pps * 0.4})
            records.append({"type": "gauge", "host": host, "ts": now, "metrics": {
                "cpu_pct": min(95.0, base_cpu * diur * jitter + random.gauss(0, 2)),
                "mem_pct": min(95.0, 40.0 + random.gauss(0, 3)),
                "latency_ms": max(0.1, 0.65 + random.gauss(0, 0.15)),
                "packet_loss_pct": max(0.0, abs(random.gauss(0, 0.05))),
            }})
        # one sampled netflow record per batch (ws1 -> web1)
        records.append({"type": "flow", "src": "10.0.1.5", "dst": "10.0.3.11",
                        "proto": "TCP", "bytes": 8000, "packets": 9})
        payload = "\n".join(json.dumps(r) for r in records)
        sock.sendto(payload.encode(), (args.host, args.port))
        sent += 1
        if sent % 10 == 0:
            print(f"  sent {sent} batches ({len(records)} records each, t={elapsed:.0f}s)")
        time.sleep(1.0 / max(args.rate, 0.1))
    print(f"done, sent {sent} batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
