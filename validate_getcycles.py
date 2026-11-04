"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
validate_getcycles.py  -  check our timing against the designers' own tool

WHY
  If two timing programs written by different people agree, the method is
  sound. The designers ship one: ascon-c/tests/getcycles.c. It reports the
  median cycles per byte at several message sizes. We use it on Ascon-Mac
  and Ascon-Prf, which it times exactly as we do, over the same sizes we
  use (1 to 1,536 bytes). (Ascon-PrfShort takes at most 16 bytes, and our
  baselines put the key in front of the message, which getcycles cannot do.)

WHAT IT DOES
  1. Builds getcycles.c with OUR flags for Ascon-Mac and Ascon-Prf.
  2. Runs it five times and keeps the middle value (one run can be unlucky).
  3. Compares it with our median cycles per byte at the sizes both measured.

HOW TO READ THE RESULT
  Both tools count with RDTSC, which ticks at a fixed rate (the nominal GHz),
  while the CPU's real speed changes with turbo boost. Our benchmark times
  each size for a long time, after a warm-up batch. getcycles runs for only
  a few milliseconds, with no warm-up. So the CPU can run at a different
  speed in the two programs, and then every size of a function moves by the
  same factor. That is not a fault in either method. A fault in a timing
  method shows up differently: it changes short messages much more than
  long ones. So the check has two parts, for each function:
    level   the middle (median) of its ratios ours / getcycles
    shape   each ratio divided by that level. PASS means every one is within
            10%: the two tools agree on how the cost changes from 1 byte
            to 1,536 bytes.

RUN (Command Prompt, in the project folder)
  python validate_getcycles.py                  against results
  python validate_getcycles.py results_pilot    against the pilot
===========================================================================
"""
import os
import statistics
import subprocess
import sys

import pandas as pd

from run_all import CFLAGS     # exactly the flags our benchmark programs use

RESULTS = "results"
if len(sys.argv) > 1:
    RESULTS = sys.argv[1]
BUILD = "build/getcycles"
SIZES = [1, 8, 16, 32, 64, 1536]              # sizes getcycles reports that we measure too
LIMIT = 10                                    # % allowed for the shape

# our program's name and its Ascon folder. getcycles calls both through
# crypto_auth(), so both are built with the switch -DCRYPTO_AUTH.
FUNCTIONS = [
    ("ascon_mac", "ascon-c/crypto_auth/asconmacv13/opt64"),
    ("ascon_prf", "ascon-c/crypto_auth/asconprfv13/opt64"),
]


def run(command):
    """Run one command and return what it printed; stop if it fails."""
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print("FAILED:", " ".join(command))
        print(result.stderr)
        sys.exit(1)
    return result.stdout


def getcycles_medians(text):
    """getcycles prints a table under the line 'cycles per byte (min,median):',
    with lines like '   16:   15.5   15.6' (size, fastest, median).
    Return the medians as {size: median}."""
    medians = {}
    table = text.split("cycles per byte (min,median):")[1]
    for line in table.splitlines():
        parts = line.replace(":", " ").split()
        if len(parts) == 3 and parts[0].isdigit():
            medians[int(parts[0])] = float(parts[2])
    return medians


ours = pd.read_csv(RESULTS + "/summary.csv")
os.makedirs(BUILD, exist_ok=True)
rows = []
for name, folder in FUNCTIONS:
    exe = BUILD + "/getcycles_" + name + ".exe"
    c_files = []
    for file_name in sorted(os.listdir(folder)):
        if file_name.endswith(".c"):
            c_files.append(folder + "/" + file_name)
    run(["gcc"] + CFLAGS + ["-I" + folder] + c_files
        + ["-Iascon-c/tests", "-DCRYPTO_AUTH", "ascon-c/tests/getcycles.c", "-o", exe])

    # Run it five times; for each size keep the middle of the five medians.
    five_runs = []
    for i in range(5):
        five_runs.append(getcycles_medians(run([exe])))
    mine = ours[ours["target"] == name]
    for size in SIZES:
        match = mine[mine["size"] == size]
        if len(match) == 0:
            continue                      # only sizes both tools measured
        values = []
        for one_run in five_runs:
            values.append(one_run[size])
        theirs = statistics.median(values)
        rows.append([name, size, theirs, match["cycles_per_byte_median"].iloc[0]])

if len(rows) == 0:
    print("Nothing to compare: run run_all.py and analyze.py first.")
    sys.exit(1)

table = pd.DataFrame(rows, columns=["target", "size", "getcycles_cpb", "ours_cpb"])
table["ratio"] = table["ours_cpb"] / table["getcycles_cpb"]
table["level"] = table.groupby("target")["ratio"].transform("median")
table["difference_pct"] = (table["ratio"] - 1) * 100                # before the level
table["shape_pct"] = (table["ratio"] / table["level"] - 1) * 100    # after the level
table.round(3).to_csv(RESULTS + "/getcycles_validation.csv", index=False)

print("function".ljust(15), "size".rjust(5), "getcycles".rjust(10), "ours".rjust(8),
      "difference".rjust(11), "after level".rjust(12))
for i in range(len(table)):
    row = table.iloc[i]
    print(row["target"].ljust(15), str(row["size"]).rjust(5), f"{row['getcycles_cpb']:10.2f}",
          f"{row['ours_cpb']:8.2f}", f"{row['difference_pct']:+10.2f}%",
          f"{row['shape_pct']:+11.2f}%")

worst = table["shape_pct"].abs().max()
average = table["shape_pct"].abs().mean()
levels = table.groupby("target")["level"].first()
print("\nlevel (ours / getcycles, middle value):", end="")
for name in levels.index:
    print(f"   {name} {levels[name]:.2f}", end="")
print(f"\nshape: largest difference after the level {worst:.2f}%   average {average:.2f}%")
if ((levels - 1).abs() * 100 > LIMIT).any():
    print("note: a level differs from 1 by more than 10%. That is the same factor at")
    print("      every size, so it comes from the CPU's speed (turbo boost) during the")
    print("      two programs, not from the timing method: see the top of this file.")
if worst <= LIMIT:
    print("PASS - the two tools agree (every size within 10% after the level)")
else:
    print("CHECK - after the level, a size differs by more than 10%: look at the rows above")
