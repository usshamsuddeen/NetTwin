"""NetTwin 3.0 — Master Experiment Orchestrator.

Runs all 5 paper experiments in sequence and generates
a comprehensive result summary.
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows consoles default to cp1252 and choke on box-drawing/unicode output.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from eval.design import FIG_DIR, RESULTS_DIR


def run_all():
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║     NetTwin 3.0 — Full Research Experiment Orchestrator        ║")
    print("║     5 Papers × 40+ Figures × 30+ Experiments                   ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    t0 = time.time()
    errors = {}

    papers = [
        ("p1_sync", "eval.p1_sync"),
        ("p2_conformal", "eval.p2_conformal"),
        ("p3_response", "eval.p3_response"),
        ("p4_rca", "eval.p4_rca"),
        ("p5_system", "eval.p5_system"),
    ]

    is_quick = "--quick" in sys.argv or os.environ.get("QUICK_EVAL", "").lower() in ("1", "true")
    if is_quick:
        print("  [MODE: FAST RIGOR / --quick enabled across all modules]\n")

    for name, module_path in papers:
        try:
            mod = __import__(module_path, fromlist=["run_all"])
            try:
                mod.run_all(quick=is_quick)
            except TypeError:
                mod.run_all()
        except Exception as e:
            errors[name] = str(e)
            print(f"\n  ✗ {name} FAILED: {e}")
            traceback.print_exc()
            print()

    elapsed = time.time() - t0

    # Summary
    print("\n" + "="*70)
    print("ORCHESTRATION COMPLETE")
    print("="*70)
    print(f"  Total time: {elapsed:.0f}s ({elapsed/60:.1f}m)")

    # Count figures
    fig_count = 0
    for paper_dir in FIG_DIR.iterdir():
        if paper_dir.is_dir():
            figs = list(paper_dir.glob("*.png"))
            fig_count += len(figs)
            print(f"  {paper_dir.name}: {len(figs)} figures")

    # Count result files
    result_count = len(list(RESULTS_DIR.glob("*.json")))
    print(f"\n  Total figures: {fig_count}")
    print(f"  Total result files: {result_count}")

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for name, err in errors.items():
            print(f"    {name}: {err}")
    else:
        print("\n  ✓ All papers completed successfully!")

    print(f"\n  Figures: {FIG_DIR}")
    print(f"  Results: {RESULTS_DIR}")


if __name__ == "__main__":
    run_all()
