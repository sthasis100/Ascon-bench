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
  median cycles per byte at several message sizes.

WHAT IT DOES
  1. Builds getcycles.c with OUR flags for four functions.
  2. Runs it three times and keeps the middle value (one run can be unlucky).
  3. Compares it with our median cycles per byte at the sizes both measured.
  PASS means every difference is within 10%. The two tools call the
  functions in different ways, so small differences are normal.

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

RESULTS = "results"
if len(sys.argv) > 1:
    RESULTS = sys.argv[1]
BUILD = "build/getcycles"
SIZES = [1, 8, 16, 32, 64, 1536]              # sizes getcycles reports

# our program's name, the switch getcycles.c needs, the Ascon folder
FUNCTIONS = [
    ("ascon_mac", "CRYPTO_AUTH", "ascon-c/crypto_auth/asconmacv13/opt64"),
    ("ascon_prf", "CRYPTO_AUTH", "ascon-c/crypto_auth/asconprfv13/opt64"),
    ("hash256_bare", "CRYPTO_HASH", "ascon-c/crypto_hash/asconhash256/opt64"),
    ("xof128_bare", "CRYPTO_HASH", "ascon-c/crypto_hash/asconxof128/opt64"),
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
print("function".ljust(14), "size".rjust(5), "getcycles".rjust(10), "ours".rjust(8),
      "difference".rjust(11))
for name, switch, folder in FUNCTIONS:
    exe = BUILD + "/getcycles_" + name + ".exe"
    c_files = []
    for file_name in sorted(os.listdir(folder)):
        if file_name.endswith(".c"):
            c_files.append(folder + "/" + file_name)
    run(["gcc", "-O3", "-march=native", "-I" + folder] + c_files
        + ["-Iascon-c/tests", "-D" + switch, "ascon-c/tests/getcycles.c", "-o", exe])

    # Run it three times; for each size keep the middle of the three medians.
    first = getcycles_medians(run([exe]))
    second = getcycles_medians(run([exe]))
    third = getcycles_medians(run([exe]))
    mine = ours[ours["target"] == name]
    for size in SIZES:
        match = mine[mine["size"] == size]
        if len(match) == 0:
            continue                      # only sizes both tools measured
        theirs = statistics.median([first[size], second[size], third[size]])
        our_value = match["cycles_per_byte_median"].iloc[0]
        difference = (our_value - theirs) / theirs * 100
        rows.append([name, size, theirs, round(our_value, 2), round(difference, 2)])
        print(name.ljust(14), str(size).rjust(5), f"{theirs:10.2f}", f"{our_value:8.2f}",
              f"{difference:+10.2f}%")

if len(rows) == 0:
    print("Nothing to compare: run run_all.py and analyze.py first.")
    sys.exit(1)
table = pd.DataFrame(rows, columns=["target", "size", "getcycles_cpb", "ours_cpb",
                                    "difference_pct"])
table.to_csv(RESULTS + "/getcycles_validation.csv", index=False)
worst = table["difference_pct"].abs().max()
average = table["difference_pct"].abs().mean()
print(f"\nlargest difference {worst:.2f}%   average {average:.2f}%")
if worst <= 10:
    print("PASS - the two tools agree")
else:
    print("CHECK - a difference over 10%: see the guide, step 6")
