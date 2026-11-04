"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
analyze.py  -  turn the raw measurements into statistics and comparisons

THE METRICS
  cycles per call   the main result, counted with RDTSC (the CPU's cycle
                    counter, which ticks at a fixed rate: the nominal GHz)
  ns per call       cycles / nominal GHz - a conversion, not a second clock
  cycles per byte   cycles per call / bytes processed
  MB/s              bytes processed per second
  noise             standard deviation as a % of the mean (under 5% is good)
  speed-up          B's median / A's median (A = the proposed function)
  every run faster  True if EVERY run of A beat EVERY run of B

WHAT IT WRITES (in the results folder)
  summary.csv            per function and size: mean, median, standard
                         deviation, fastest, slowest, noise, ns, MB/s
  comparisons.csv        every comparison, size by size
  raw_runs_detailed.csv  every single measurement: algorithm,
                         implementation, sizes, repetition, cycles, time

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

# ------------------------------------------------ one value per measurement
# The size of a point is the message length - except for the two
# key-derivation programs, where it is the derived key length (the output).
raw["size"] = raw["msg_bytes"]
is_kdf = raw["mode"].isin(["akdf", "prf_kdf"])
raw.loc[is_kdf, "size"] = raw.loc[is_kdf, "out_bytes"]
raw["cycles_per_call"] = raw["cycles"] / raw["reps"]
if ghz:
    raw["ns_per_call"] = raw["cycles_per_call"] / ghz

# Every measurement, one row each, as our project plan asks for.
folders = {}
for name, role, mode, folder, sizes in TARGETS:
    folders[name] = folder
detail = raw.copy()
detail["algorithm"] = detail["target"]
detail["implementation"] = detail["target"].map(folders)
detail["repetition"] = detail["run"]
columns = ["algorithm", "role", "implementation", "key_bytes", "msg_bytes",
           "out_bytes", "repetition", "reps", "cycles", "cycles_per_call"]
if ghz:
    columns.append("ns_per_call")
detail[columns].to_csv(RESULTS + "/raw_runs_detailed.csv", index=False)

# ------------------------------------------------------------------ summary
groups = raw.groupby(["target", "role", "size"])["cycles_per_call"]
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

# -------------------------------------------------------------- comparisons
# name, group, A (the proposed function), B (what it is compared with), note
COMPARISONS = [
    ("Ascon-Mac vs AMAC", "MAC", "ascon_mac", "amac",
     "NIST's planned MAC; both give a 16-byte tag"),
    ("Ascon-Mac vs MAC from XOF128", "MAC", "ascon_mac", "mac_from_xof128",
     "the main comparison: a standard function giving 16 bytes, like Ascon-Mac"),
    ("Ascon-Mac vs MAC from Hash256", "MAC", "ascon_mac", "mac_from_hash256",
     "the most obvious option today; Hash256 always gives 32 bytes"),
    ("Ascon-Prf vs PRF from XOF128", "PRF", "ascon_prf", "prf_from_xof128",
     "both keyed, both give 64 bytes"),
    ("Ascon-PrfShort vs Ascon-Mac", "PrfShort", "ascon_prfshort", "ascon_mac",
     "messages up to 16 bytes; both give 16 bytes"),
    ("Ascon-PrfShort vs MAC from XOF128", "PrfShort", "ascon_prfshort", "mac_from_xof128",
     "messages up to 16 bytes; both give 16 bytes"),
    ("Ascon-PrfShort vs AMAC", "PrfShort", "ascon_prfshort", "amac",
     "messages up to 16 bytes; both give 16 bytes"),
    ("Ascon-Prf vs AKDF", "KDF", "prf_kdf", "akdf",
     "NIST's planned KDF; same key, X, label and key length; size = key length"),
]

rows = []
for name, group, a, b, note in COMPARISONS:
    data_a = raw[raw["target"] == a]
    data_b = raw[raw["target"] == b]
    for size in sorted(set(data_a["size"])):
        if size not in set(data_b["size"]):
            continue                    # only sizes both programs measured
        runs_a = data_a[data_a["size"] == size]["cycles_per_call"]
        runs_b = data_b[data_b["size"] == size]["cycles_per_call"]
        rows.append({"comparison": name, "group": group, "size": size, "A": a, "B": b,
                     "A_cycles": runs_a.median(), "B_cycles": runs_b.median(),
                     "speedup": runs_b.median() / runs_a.median(),
                     "every_A_run_faster": runs_a.max() < runs_b.min(),
                     "note": note})
comp = pd.DataFrame(rows)
comp.to_csv(RESULTS + "/comparisons.csv", index=False)

# ----------------------------------------------------------------- headline
worst = summary.loc[summary["noise_pct"].idxmax()]
print(len(raw), "measurements ->", len(summary), "summary rows ("
      + str(raw["target"].nunique()) + " programs)")
print("clock: RDTSC; nominal frequency", ghz, "GHz, used only to convert cycles to ns and MB/s")
print(f"noise: median {summary['noise_pct'].median():.2f}%, worst {worst['noise_pct']:.2f}% "
      f"({worst['target']} at {int(worst['size'])} bytes)")
print(f"comparisons where EVERY run of the proposed function was faster: "
      f"{int(comp['every_A_run_faster'].sum())} of {len(comp)}")
print("\nspeed-up (median), smallest to largest over the sizes measured:")
for name, group, a, b, note in COMPARISONS:
    part = comp[comp["comparison"] == name]
    print(f"   {name:38} {part['speedup'].min():5.2f}x to {part['speedup'].max():5.2f}x")
print("\nwrote", RESULTS + "/summary.csv, comparisons.csv and raw_runs_detailed.csv")
