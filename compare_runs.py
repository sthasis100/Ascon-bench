"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
compare_runs.py  -  check that a second run agrees with the first

WHY
  If the measurements are clean, timing the same function again gives the
  same median time per call: at another time, with different message
  bytes, with the sizes in a different order, or with a different number
  of calls per batch. This script lines up two runs, point by point.

WHAT IT DOES
  Reads summary.csv from two results folders (each made by analyze.py).
  For every function and size that both runs measured, it prints the two
  medians, the difference, and the noise of each run:
    difference % = (second median / first median - 1) x 100
  A point is "same" when the difference is within the limit (2% unless
  you give another), and "CHECK" otherwise.

WHAT IT WRITES
  run_check.csv in the second folder.

RUN (Command Prompt, in the project folder), after analyze.py on both:
  python compare_runs.py results results_retime
  python compare_runs.py results results_seed 3       (a limit of 3%)
===========================================================================
"""
import sys

import pandas as pd

if len(sys.argv) < 3:
    print("usage: python compare_runs.py <first results folder> <second results folder> [limit %]")
    sys.exit(1)
FIRST = sys.argv[1]
SECOND = sys.argv[2]
LIMIT = 2.0
if len(sys.argv) > 3:
    LIMIT = float(sys.argv[3])

first = pd.read_csv(FIRST + "/summary.csv")
second = pd.read_csv(SECOND + "/summary.csv")
keys = ["target", "size"]
both = first.merge(second, on=keys, suffixes=("_first", "_second")).sort_values(keys)
if len(both) == 0:
    print("The two runs have no function and size in common.")
    sys.exit(1)
both["difference_pct"] = (both["cycles_median_second"] / both["cycles_median_first"] - 1) * 100
both["result"] = "same"
both.loc[both["difference_pct"].abs() > LIMIT, "result"] = "CHECK"

print("first: ", FIRST)
print("second:", SECOND)
print()
print(f"{'function':15}{'size':>7}{'first median':>14}{'second median':>15}"
      f"{'difference':>12}{'noise first':>13}{'noise second':>14}  result")
for i in range(len(both)):
    row = both.iloc[i]
    print(f"{row['target']:15}{int(row['size']):>7}{row['cycles_median_first']:>14.1f}"
          f"{row['cycles_median_second']:>15.1f}{row['difference_pct']:>+11.2f}%"
          f"{row['noise_pct_first']:>12.2f}%{row['noise_pct_second']:>13.2f}%  {row['result']}")

same = int((both["result"] == "same").sum())
print(f"\n{same} of {len(both)} points have the same median within {LIMIT:g}%")
only = len(first) + len(second) - 2 * len(both)
if only > 0:
    print(only, "points were measured in only one of the two runs and are not compared")

columns = keys + ["cycles_median_first", "cycles_median_second", "difference_pct",
                  "noise_pct_first", "noise_pct_second", "result"]
both[columns].to_csv(SECOND + "/run_check.csv", index=False)
print("wrote", SECOND + "/run_check.csv")
