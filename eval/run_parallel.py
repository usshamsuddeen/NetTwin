"""NetTwin 3.0 — Parallel Experiment Orchestrator.

Runs all 5 paper experiments concurrently in separate processes.
Each module is expected to expose a ``run_all(quick=False)`` function.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from multiprocessing import Process, Queue
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from eval.design import FIG_DIR, RESULTS_DIR

PAPERS = [
    ("p1_sync", "eval.p1_sync"),
    ("p2_conformal", "eval.p2_conformal"),
    ("p3_response", "eval.p3_response"),
    ("p4_rca", "eval.p4_rca"),
    ("p5_system", "eval.p5_system"),
]


def _run_paper(name: str, module_path: str, quick: bool, q: "Queue[str]") -> None:
    try:
        mod = __import__(module_path, fromlist=["run_all"])
        try:
            mod.run_all(quick=quick)
        except TypeError:
            mod.run_all()
        q.put(name)
    except Exception as exc:
        q.put(f"{name}:ERROR:{exc}\n{traceback.format_exc()}")


def run_all_parallel() -> None:
    is_quick = "--quick" in sys.argv or os.environ.get("QUICK_EVAL", "").lower() in ("1", "true")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     NetTwin 3.0 — Parallel Research Experiment Orchestrator    ║")
    print("║     5 Papers running concurrently                              ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    if is_quick:
        print("  [MODE: FAST RIGOR / --quick enabled]\n")

    t0 = time.time()
    q: Queue[str] = Queue()
    processes: list[Process] = []
    for name, module_path in PAPERS:
        p = Process(target=_run_paper, args=(name, module_path, is_quick, q))
        p.start()
        processes.append(p)
        print(f"  started {name}")

    done: set[str] = set()
    errors: dict[str, str] = {}
    while len(done) + len(errors) < len(PAPERS):
        msg = q.get()
        if msg.startswith("ERROR:") or ":ERROR:" in msg:
            parts = msg.split(":ERROR:", 1)
            errors[parts[0]] = parts[1]
            print(f"\n  ✗ {parts[0]} FAILED:\n{parts[1]}")
        else:
            done.add(msg)
            print(f"  ✓ {msg} completed")

    for p in processes:
        p.join(timeout=5)
        if p.is_alive():
            p.terminate()
            p.join()

    elapsed = time.time() - t0
    fig_count = sum(len(list(d.glob("*.png"))) for d in FIG_DIR.iterdir() if d.is_dir())
    result_count = len(list(RESULTS_DIR.glob("*.json")))

    print("\n" + "=" * 70)
    print("PARALLEL ORCHESTRATION COMPLETE")
    print("=" * 70)
    print(f"  Total time: {elapsed:.0f}s ({elapsed / 60:.1f}m)")
    print(f"  Total figures: {fig_count}")
    print(f"  Total result files: {result_count}")
    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for name, err in errors.items():
            print(f"    {name}: {err.splitlines()[0]}")
    else:
        print("\n  ✓ All papers completed successfully!")
    print(f"\n  Figures: {FIG_DIR}")
    print(f"  Results: {RESULTS_DIR}")


if __name__ == "__main__":
    run_all_parallel()
