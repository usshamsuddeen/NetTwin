"""
Runs the full NetTwin pytest suite (143 tests), formats an itemized report,
and writes both plaintext and JSON reviewer audit files.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    results_dir = root / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    report_txt = results_dir / "test_execution_report.txt"
    report_json = results_dir / "tests_itemized_report.json"

    print("Executing full NetTwin test suite (143 test cases across 28 modules)...")
    start_t = time.time()

    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short"]
    res = subprocess.run(
        cmd,
        cwd=str(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.time() - start_t

    full_output = res.stdout + ("\n" + res.stderr if res.stderr else "")
    report_txt.write_text(full_output, encoding="utf-8")

    # Parse individual tests and module counts
    test_lines = [l.strip() for l in res.stdout.splitlines() if "::" in l and ("PASSED" in l or "SKIPPED" in l or "FAILED" in l)]
    
    modules = {}
    passed_count = 0
    failed_count = 0
    skipped_count = 0

    for line in test_lines:
        parts = line.split()
        test_id = parts[0]
        status = parts[1] if len(parts) > 1 else "UNKNOWN"
        mod_name = test_id.split("::")[0]
        
        if status == "PASSED":
            passed_count += 1
        elif status == "FAILED":
            failed_count += 1
        elif status == "SKIPPED":
            skipped_count += 1

        if mod_name not in modules:
            modules[mod_name] = {"passed": 0, "failed": 0, "skipped": 0, "tests": []}
        modules[mod_name]["tests"].append({"id": test_id, "status": status})
        if status == "PASSED":
            modules[mod_name]["passed"] += 1
        elif status == "FAILED":
            modules[mod_name]["failed"] += 1
        elif status == "SKIPPED":
            modules[mod_name]["skipped"] += 1

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "total_collected": len(test_lines),
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "duration_seconds": round(elapsed, 2),
        "exit_code": res.returncode,
        "modules_count": len(modules),
        "modules": modules,
    }

    report_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Tests execution completed in {elapsed:.2f}s: {passed_count} Passed, {failed_count} Failed, {skipped_count} Skipped (Total: {len(test_lines)})")
    print(f"Report saved to {report_txt} and {report_json}")

if __name__ == "__main__":
    main()
