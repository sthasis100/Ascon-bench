#!/usr/bin/env python3
"""Independent INSuRE Team 4 benchmarking reliability checks (Leela, V2).

Standard-library only. Non-destructive: reads V1 raw CSV files and writes a
separate screening report. It does not clean, replace, or remeasure data.

Usage (from repository root):
  python src/benchmark_reliability_v2.py results/windows_i5_2026-11-03/raw_runs.csv \
    --diagnostic results/windows_i5_2026-11-03/diagnostics/ascon_mac_1byte_recheck_01.csv \
    --output results/windows_i5_2026-11-03/v2_analysis

Flags are screening heuristics, not proof of OS interference or an invalid run.
Repeat batches are not independent CPU/session replications; do not interpret
statistical intervals from these samples as cross-session uncertainty.
"""

from __future__ import annotations

import argparse
import csv
import statistics as stats
from collections import defaultdict
from pathlib import Path


def read_measurements(path: Path):
    if not path.is_file():
        raise FileNotFoundError(f"CSV not found: {path}")
    grouped = defaultdict(list)
    problems = []
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        required = {"target", "msg_bytes", "out_bytes", "run", "reps", "cycles"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} must contain columns: {', '.join(sorted(required))}")
        for line_num, row in enumerate(reader, 2):
            try:
                target = row["target"].strip()
                mode = row.get("mode", "").strip()
                msg_bytes = int(row["msg_bytes"])
                out_bytes = int(row["out_bytes"])
                run = int(row["run"])
                reps = int(row["reps"])
                cycles = int(row["cycles"])
                if not target or reps <= 0 or cycles <= 0 or msg_bytes < 0 or out_bytes < 0 or run < 0:
                    raise ValueError("invalid/nonpositive measurement field")
            except (ValueError, TypeError, AttributeError, KeyError) as exc:
                problems.append(f"{path.name}: line {line_num}: {exc}")
                continue
            key = (target, mode, msg_bytes, out_bytes)
            grouped[key].append((run, cycles / reps))
    return grouped, problems


def format_key(key):
    return f"{key[0]} / msg={key[2]}B / output={key[3]}B"


def summarize(key, samples):
    samples = sorted(samples, key=lambda item: item[0])
    runs = [r for r, _ in samples]
    values = [v for _, v in samples]
    n = len(values)
    median = stats.median(values)
    mean = stats.mean(values)
    stdev = stats.stdev(values) if n >= 2 else 0.0
    mad = stats.median(abs(v - median) for v in values)
    # Relative to the preceding sample: measures an abrupt transition between runs.
    steps = [100 * abs(values[i] - values[i - 1]) / values[i - 1]
             for i in range(1, n) if values[i - 1] > 0]
    max_step = max(steps, default=0.0)
    jump_run = runs[1 + steps.index(max_step)] if steps else ""
    # Large median-to-minimum separation reveals a potentially stable slow
    # state even when the ordinary coefficient of variation is small.
    min_gap = 100 * (median - min(values)) / median
    cv = 100 * stdev / mean if mean else 0.0
    flags = []
    if len(runs) != len(set(runs)):
        flags.append("DUPLICATE_RUN_ID")
    if n < 10:
        flags.append("LOW_SAMPLE_COUNT")
    if cv > 10:
        flags.append("HIGH_CV")
    if n >= 10 and max_step > 20:
        flags.append("TEMPORAL_JUMP")
    if n >= 10 and min_gap > 20:
        flags.append("SLOW_MEDIAN_VS_MIN")
    # Must not silently discard any measurement. No automatic correction.
    return {
        "target": key[0], "mode": key[1], "msg_bytes": key[2],
        "out_bytes": key[3], "samples": n,
        "median_ticks_per_call": round(median, 4),
        "min_ticks_per_call": round(min(values), 4),
        "max_ticks_per_call": round(max(values), 4),
        "cv_pct": round(cv, 2),
        "median_abs_deviation_pct": round(100 * mad / median, 2),
        "median_min_gap_pct": round(min_gap, 2),
        "largest_adjacent_change_pct": round(max_step, 2),
        "change_detected_at_run": jump_run,
        "screening_flags": ";".join(flags) or "NONE",
    }


def write_csv(path: Path, rows, fields):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path, help="V1 raw_runs.csv")
    parser.add_argument("--diagnostic", type=Path, help="Optional targeted repeat-run CSV")
    parser.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    if args.output.resolve() == args.raw.parent.resolve():
        parser.error("Choose a separate output subdirectory; don't place reports over V1 data")
    raw_groups, errors = read_measurements(args.raw)
    if not raw_groups:
        raise ValueError("No valid raw measurements")
    rows = [summarize(k, v) for k, v in sorted(raw_groups.items())]
    comparisons = []
    if args.diagnostic:
        diag_groups, diag_errors = read_measurements(args.diagnostic)
        errors.extend(diag_errors)
        for key, samples in sorted(diag_groups.items()):
            if key not in raw_groups:
                errors.append(f"Diagnostic not matched to original: {format_key(key)}")
                continue
            a = stats.median(v for _, v in raw_groups[key])
            b = stats.median(v for _, v in samples)
            comparisons.append({
                "target": key[0], "msg_bytes": key[2], "out_bytes": key[3],
                "original_samples": len(raw_groups[key]), "diagnostic_samples": len(samples),
                "original_median_ticks": round(a, 4),
                "diagnostic_median_ticks": round(b, 4),
                "diagnostic_change_pct": round(100 * (b / a - 1), 2),
            })
    # Don't overwrite a previous analysis; unique output directory is intentional.
    args.output.mkdir(parents=True, exist_ok=True)
    if any(args.output.iterdir()):
        raise FileExistsError(f"Output directory is not empty, no reports overwritten: {args.output}")
    write_csv(args.output / "reliability_by_configuration.csv", rows, list(rows[0]))
    if comparisons:
        write_csv(args.output / "targeted_recheck_comparison.csv", comparisons, list(comparisons[0]))
    flagged = [r for r in rows if r["screening_flags"] not in ("NONE", "LOW_SAMPLE_COUNT")]
    lines = [
        "# Benchmarking V2 — preliminary reliability screening", "",
        f"Raw source: `{args.raw}`", f"Configurations: {len(rows)}",
        f"Measurements: {sum(r['samples'] for r in rows)}",
        f"Configurations with substantive screening flags: {len(flagged)}", "",
        "## Screening rules (exploratory; not acceptance/rejection criteria)",
        "", "- `HIGH_CV`: sample standard deviation / mean > 10%",
        "- `TEMPORAL_JUMP`: consecutive values change by > 20% (>= 10 samples)",
        "- `SLOW_MEDIAN_VS_MIN`: median > minimum by 20% of median (>= 10 samples)",
        "- `LOW_SAMPLE_COUNT`: fewer than 10 readings; pilot data is not conclusive",
        "- All original readings are retained. No trimming or replacement.", "",
        "## Flagged configurations", "",
    ]
    if flagged:
        for r in flagged:
            lines.append(f"- {r['target']} msg={r['msg_bytes']}B out={r['out_bytes']}B: "
                         f"median={r['median_ticks_per_call']} ticks, CV={r['cv_pct']}%, "
                         f"jump={r['largest_adjacent_change_pct']}% at run "
                         f"{r['change_detected_at_run']}; {r['screening_flags']}")
    else:
        lines.append("No substantial flags at selected heuristic thresholds.")
    if comparisons:
        lines.extend(["", "## Targeted repeat-run comparisons", ""])
        for r in comparisons:
            lines.append(f"- {r['target']} msg={r['msg_bytes']}B: original median "
                         f"{r['original_median_ticks']} vs repeat {r['diagnostic_median_ticks']} "
                         f"ticks/call ({r['diagnostic_change_pct']:+.2f}% change)")
    lines.extend(["", "## Interpretation limits", "",
                  "These are diagnostics, not proof of a CPU-frequency cause, a compiler bug, "
                  "or incorrect cryptographic output.",
                  "Repetitions within one run are not independent experimental sessions. "
                  "This report does not claim confidence intervals or cross-platform significance.",
                  "Measurement units are TSC ticks/call, not direct elapsed nanoseconds.",
                  "Investigate flags with separately recorded repeat sessions and environment logs."])
    if errors:
        lines.extend(["", "## Data warnings", ""] + [f"- {e}" for e in errors])
    (args.output / "reliability_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"V2 analyzed {sum(r['samples'] for r in rows)} measurements across {len(rows)} configurations")
    print(f"Configurations needing investigation: {len(flagged)}")
    for row in sorted(flagged, key=lambda r: r["largest_adjacent_change_pct"], reverse=True)[:8]:
        print(f"  {row['target']} msg={row['msg_bytes']} out={row['out_bytes']}: "
              f"{row['screening_flags']} (max adjacent change {row['largest_adjacent_change_pct']}%)")
    for comp in comparisons:
        print(f"  RECHECK {comp['target']} msg={comp['msg_bytes']}B: "
              f"{comp['original_median_ticks']} -> {comp['diagnostic_median_ticks']} "
              f"ticks/call ({comp['diagnostic_change_pct']:+.2f}%)")
    print(f"Reports written to {args.output}")
    if errors:
        print(f"NOTE: {len(errors)} data warning(s), documented in the report")


if __name__ == "__main__":
    main()
