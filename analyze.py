"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
analyze.py  -  turn the raw measurements into statistics

THE METRICS (how each one is calculated)
  cycles per call   cycles for one timed batch / calls in the batch. The main
                    result, counted with RDTSC (the CPU's cycle counter,
                    which ticks at a fixed rate: the nominal GHz)
  median            the middle value of the repetitions (30 in the real
                    study): the execution time we report
  mean, standard deviation, fastest, slowest
                    of the same repetitions
  noise             standard deviation as a % of the mean (under 5% is good)
  ns per call       cycles per call / nominal GHz - a conversion, not a
                    second clock
  cycles per byte   median cycles per call / size in bytes
  MB/s              size in bytes / median ns per call x 1000
  For AKDF, "size" is the length of the new key it makes (16, 32 or 64
  bytes); for the other three, it is the message length.

WHAT IT WRITES (in the results folder)
  summary.csv            per function and size: runs, mean, median,
                         standard deviation, fastest, slowest, noise,
                         cycles per byte, ns, MB/s
  raw_runs_detailed.csv  every single measurement: algorithm,
                         implementation, sizes, repetition, cycles, time

Only the four functions listed in run_all.py are used, so results from an
older run that timed more programs can still be analysed.

RUN (Command Prompt, in the project folder)
  python analyze.py                  the real results (results)
  python analyze.py results_pilot    the pilot's results
===========================================================================
"""
import json
import sys

import pandas as pd

from run_all import TARGETS    # the one place each program's Ascon folder is listed

RESULTS = "results"
if len(sys.argv) > 1:
    RESULTS = sys.argv[1]

raw = pd.read_csv(RESULTS + "/raw_runs.csv")
with open(RESULTS + "/environment.json") as f:
    ghz = json.load(f)["nominal_ghz"]

# Keep only the four functions we benchmark.
folders = {}
for name, mode, folder, sizes in TARGETS:
    folders[name] = folder
raw = raw[raw["target"].isin(list(folders))].copy()
if len(raw) == 0:
    print("No measurements of the four functions in", RESULTS + "/raw_runs.csv")
    sys.exit(1)

# ------------------------------------------------ one value per measurement
# The size of a point is the message length - except for AKDF, where it is
# the length of the new key (the output).
raw["size"] = raw["msg_bytes"]
is_kdf = raw["mode"] == "akdf"
raw.loc[is_kdf, "size"] = raw.loc[is_kdf, "out_bytes"]
raw["cycles_per_call"] = raw["cycles"] / raw["reps"]
if ghz:
    raw["ns_per_call"] = raw["cycles_per_call"] / ghz

# Every measurement, one row each, as our project plan asks for.
detail = raw.copy()
detail["algorithm"] = detail["target"]
detail["implementation"] = detail["target"].map(folders)
detail["repetition"] = detail["run"]
columns = ["algorithm", "implementation", "key_bytes", "msg_bytes",
           "out_bytes", "repetition", "reps", "cycles", "cycles_per_call"]
if ghz:
    columns.append("ns_per_call")
detail[columns].to_csv(RESULTS + "/raw_runs_detailed.csv", index=False)

# ------------------------------------------------------------------ summary
groups = raw.groupby(["target", "size"])["cycles_per_call"]
summary = groups.agg(["count", "mean", "median", "std", "min", "max"]).reset_index()
summary = summary.rename(columns={"count": "runs", "mean": "cycles_mean",
                                  "median": "cycles_median", "std": "cycles_std",
                                  "min": "cycles_min", "max": "cycles_max"})
summary["noise_pct"] = summary["cycles_std"] / summary["cycles_mean"] * 100
summary["cycles_per_byte_median"] = summary["cycles_median"] / summary["size"]
if ghz:
    summary["ns_median"] = summary["cycles_median"] / ghz
    summary["MBps_median"] = summary["size"] / summary["ns_median"] * 1000
summary.to_csv(RESULTS + "/summary.csv", index=False)

# ----------------------------------------------------------------- headline
worst = summary.loc[summary["noise_pct"].idxmax()]
count = raw["target"].nunique()
print(len(raw), "measurements ->", len(summary), "summary rows ("
      + str(count) + " function" + ("s" if count > 1 else "") + ")")
print("clock: RDTSC; nominal frequency", ghz, "GHz, used only to convert cycles to ns and MB/s")
print(f"noise: median {summary['noise_pct'].median():.2f}%, worst {worst['noise_pct']:.2f}% "
      f"({worst['target']} at {int(worst['size'])} bytes)")
noisy = summary[summary["noise_pct"] > 5]
print(len(noisy), "of", len(summary), "points have noise over 5%"
      + (" - look at these, and consider timing them again:" if len(noisy) > 0 else ""))
for i in range(len(noisy)):
    row = noisy.iloc[i]
    print(f"   {row['target']:15} {int(row['size']):>6} bytes   {row['noise_pct']:6.2f}%")
print("\nmedian cycles per call, smallest and largest size:")
for name in folders:
    part = summary[summary["target"] == name].sort_values("size")
    if len(part) == 0:
        continue
    first = part.iloc[0]
    last = part.iloc[-1]
    print(f"   {name:15} {first['cycles_median']:10.1f} at {int(first['size']):>6} bytes"
          f"   {last['cycles_median']:12.1f} at {int(last['size']):>6} bytes")
print("\nwrote", RESULTS + "/summary.csv and raw_runs_detailed.csv")
