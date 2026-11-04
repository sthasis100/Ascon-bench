#!/usr/bin/env python3
"""Independent RDTSC vs LFENCE+RDTSC repeatability experiment.

INSuRE Team 4 supplemental validation experiment. The base benchmark programs
(src/bench.c and src/bench_v2.c) are derived from Team 4's V1 framework.
This script evaluates the timing modification; it does not replace the
framework's correctness checks or its main benchmarking study.

Requires two previously compiled executables, both from src/bench_v2.c:
  build/mac_v2_unfenced.exe
  build/mac_v2_fenced.exe
They must differ only by -DBENCH_V2_FENCED.

No third-party Python packages are required. Run from repository root.
"""

import csv
import hashlib
import json
import platform
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILDS = {
    "unfenced": ROOT / "build" / "mac_v2_unfenced.exe",
    "fenced": ROOT / "build" / "mac_v2_fenced.exe",
}
OUTPUT = ROOT / "results" / "v2_timing_comparison"
SIZES = (1, 8, 16, 64, 1536)
REPETITIONS = 30
CORE = 2
ROUNDS = 4
# A/B/B/A then B/A/A/B balances which method goes first/last.
ORDERS = (
    ("unfenced", "fenced", "fenced", "unfenced"),
    ("fenced", "unfenced", "unfenced", "fenced"),
    ("unfenced", "fenced", "fenced", "unfenced"),
    ("fenced", "unfenced", "unfenced", "fenced"),
)
FIELDS = ["round", "order_position", "session", "method", "target", "mode",
          "key_bytes", "msg_bytes", "out_bytes", "run", "reps", "cycles",
          "tsc_ticks_per_call"]


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(method, runs):
    cmd = [str(BUILDS[method]), "ascon_mac", str(runs),
           ",".join(map(str, SIZES)), str(CORE)]
    completed = subprocess.run(cmd, cwd=str(ROOT), text=True,
                               capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"{method}: nonzero return code {completed.returncode}:\n"
                           + completed.stderr[-1200:])
    if f"pinned to core {CORE}" not in completed.stderr:
        raise RuntimeError(f"{method}: CPU core affinity not confirmed:\n"
                           + completed.stderr[-1200:])
    return completed.stdout


def main():
    if len(sys.argv) != 1:
        raise SystemExit("Usage: python src/run_timing_comparison_v2.py")
    for method, exe in BUILDS.items():
        if not exe.is_file():
            raise SystemExit(f"Missing {method} executable: {exe}\nCompile both first.")
    if OUTPUT.exists():
        raise SystemExit(f"STOP: output folder already exists; refusing overwrite: {OUTPUT}")

    # Test equivalence in verify mode before timing; KAT validation is separate.
    verified = {method: execute(method, 0) for method in BUILDS}
    if verified["unfenced"] != verified["fenced"]:
        raise SystemExit("FAIL: output mismatch between timing methods")
    verify_lines = verified["unfenced"].splitlines()
    if len(verify_lines) != len(SIZES) + 1:
        raise SystemExit("FAIL: unexpected number of verification rows")
    print(f"PASS: both methods produce identical outputs for {list(SIZES)} bytes", flush=True)

    OUTPUT.mkdir(parents=True, exist_ok=False)
    meta = {
        "purpose": "Supplemental V1-unfenced vs V2-LFENCE timing reliability experiment",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "cpu_core_requested": CORE, "runs_per_size_per_session": REPETITIONS,
        "sizes_bytes": list(SIZES), "rounds": ROUNDS,
        "method_order_per_round": [list(order) for order in ORDERS],
        "number_of_process_sessions": 4 * ROUNDS,
        "expected_measurements": 4 * ROUNDS * len(SIZES) * REPETITIONS,
        "compiler_flags_common": "-O3 -march=native -std=c11 -fno-lto",
        "timing_difference": "-DBENCH_V2_FENCED added only for fenced build",
        "tick_definition": "RDTSC counter ticks per call; not measured nanoseconds or actual core cycles",
        "source_sha256": sha256(ROOT / "src" / "bench_v2.c"),
        "executables_sha256": {method: sha256(path) for method, path in BUILDS.items()},
        "comment": "No data cleaning or outlier removal; raw session data preserved.",
    }
    (OUTPUT / "experiment_manifest.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    collected = []
    raw_file = OUTPUT / "raw_timing_comparison.csv"
    with raw_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        session = 0
        for round_number, order in enumerate(ORDERS, start=1):
            for position, method in enumerate(order, start=1):
                session += 1
                text = execute(method, REPETITIONS)
                records = list(csv.DictReader(text.splitlines()))
                expected = len(SIZES) * REPETITIONS
                if len(records) != expected:
                    raise RuntimeError(f"Session {session}: expected {expected} rows, got {len(records)}")
                seen = set()
                for record in records:
                    size = int(record["msg_bytes"])
                    run_index = int(record["run"])
                    if (size not in SIZES or run_index not in range(REPETITIONS)
                            or record["target"] != "ascon_mac"):
                        raise RuntimeError(f"Session {session}: invalid row: {record}")
                    identifier = (size, run_index)
                    if identifier in seen:
                        raise RuntimeError(f"Session {session}: duplicate row {identifier}")
                    seen.add(identifier)
                    cycles, reps = int(record["cycles"]), int(record["reps"])
                    if cycles <= 0 or reps <= 0:
                        raise RuntimeError(f"Session {session}: nonpositive cycles/reps")
                    row = {
                        "round": round_number, "order_position": position,
                        "session": session, "method": method,
                        "target": record["target"], "mode": record["mode"],
                        "key_bytes": record["key_bytes"], "msg_bytes": size,
                        "out_bytes": record["out_bytes"], "run": run_index,
                        "reps": reps, "cycles": cycles,
                        "tsc_ticks_per_call": f"{cycles / reps:.6f}",
                    }
                    writer.writerow(row)
                    collected.append(row)
                handle.flush()
                print(f"Round {round_number}/{ROUNDS}, session {session}/16: "
                      f"{method}, {len(records)} measurements", flush=True)

    # Descriptive statistics. Comparing medians of session medians prevents a
    # single long or unstable session from being implicitly weighted more.
    group_summaries = []
    for size in SIZES:
        for method in BUILDS:
            per_session_medians = []
            for sess in range(1, 4 * ROUNDS + 1):
                vals = [float(r["tsc_ticks_per_call"]) for r in collected
                        if r["method"] == method and r["msg_bytes"] == size
                        and r["session"] == sess]
                if vals:
                    per_session_medians.append(statistics.median(vals))
            if len(per_session_medians) != 2 * ROUNDS:
                raise RuntimeError(f"Wrong number of {method} sessions at {size}B")
            mean_session = statistics.mean(per_session_medians)
            cv = (100 * statistics.stdev(per_session_medians) / mean_session
                  if mean_session > 0 else float('nan'))
            group_summaries.append({
                "msg_bytes": size, "method": method, "sessions": len(per_session_medians),
                "median_of_session_medians": round(statistics.median(per_session_medians), 4),
                "min_session_median": round(min(per_session_medians), 4),
                "max_session_median": round(max(per_session_medians), 4),
                "session_median_cv_percent": round(cv, 3),
            })
    summary_file = OUTPUT / "session_summary.csv"
    with summary_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(group_summaries[0]))
        writer.writeheader()
        writer.writerows(group_summaries)
    meta["finished_utc"] = datetime.now(timezone.utc).isoformat()
    meta["actual_measurements"] = len(collected)
    (OUTPUT / "experiment_manifest.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(f"\nDONE: {len(collected)} raw measurements; 16 separate processes", flush=True)
    print("Summary (median of session medians; TSC ticks/call):", flush=True)
    for size in SIZES:
        u, f = [r for r in group_summaries if r["msg_bytes"] == size]
        ratio = f["median_of_session_medians"] / u["median_of_session_medians"]
        print(f"  {size:>4}B: unfenced {u['median_of_session_medians']:.2f}, "
              f"fenced {f['median_of_session_medians']:.2f}; "
              f"fenced/unfenced {ratio:.3f}x; "
              f"session CV {u['session_median_cv_percent']:.2f}% / "
              f"{f['session_median_cv_percent']:.2f}%", flush=True)
    print(f"Saved to {OUTPUT.relative_to(ROOT)}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
