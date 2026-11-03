"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
plots.py  -  draw the report's figures from the analysed results

THE FIGURES (saved in the results folder, under figures)
  fig1   execution time: cycles per call against message size
  fig2   short messages (1, 8, 16 bytes): the 16-byte MAC job
  fig3   cycles per byte against message size
  fig4   throughput in MB/s
  fig5   heat map: every function at every size, against the fastest
  fig6   noise: how much each measurement varied
  fig7   how many times faster Ascon-Mac is than each MAC
  fig8   how many times faster Ascon-Prf is than the XOF128 PRF
  fig9   key derivation: Ascon-Prf against AKDF
  fig10  CXOF128: Kerry's opt64 build, the reference, and XOF128
  fig11  code size at -O3 and -Os

RUN (Command Prompt, in the project folder)
  python plots.py                  the real results
  python plots.py results_pilot    the pilot's results
===========================================================================
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")           # draw straight to files; no window opens
import matplotlib.pyplot as plt
import pandas as pd

RESULTS = "results"
if len(sys.argv) > 1:
    RESULTS = sys.argv[1]
OUT = RESULTS + "/figures"
os.makedirs(OUT, exist_ok=True)

summary = pd.read_csv(RESULTS + "/summary.csv")
comparisons = pd.read_csv(RESULTS + "/comparisons.csv")
code_size = pd.read_csv(RESULTS + "/code_size.csv")
with open(RESULTS + "/environment.json") as f:
    ghz = json.load(f)["nominal_ghz"]

# The same name and colour for a function in every figure.
# Line style: proposed solid, baselines dashed, lower bounds dotted.
STYLE = {
    "ascon_mac":        ("Ascon-Mac (proposed)", "#c0392b", "-"),
    "ascon_prf":        ("Ascon-Prf (proposed)", "#e67e22", "-"),
    "ascon_prfshort":   ("Ascon-PrfShort (proposed)", "#27ae60", "-"),
    "prf_kdf":          ("Ascon-Prf, AKDF inputs (proposed)", "#e67e22", "-"),
    "amac":             ("AMAC (NIST plan)", "#6c3483", "--"),
    "akdf":             ("AKDF (NIST plan)", "#6c3483", "--"),
    "mac_from_xof128":  ("MAC from XOF128, 16 B", "#2471a3", "--"),
    "mac_from_hash256": ("MAC from Hash256, 32 B", "#117a65", "--"),
    "prf_from_xof128":  ("PRF from XOF128, 64 B", "#5dade2", "--"),
    "cxof128":          ("CXOF128, opt64 (Kerry)", "#7f8c8d", "-."),
    "cxof128_ref":      ("CXOF128, reference", "#b3b6b7", ":"),
    "hash256_bare":     ("Hash256, no key (lower bound)", "#909497", ":"),
    "xof128_bare":      ("XOF128, no key (lower bound)", "#566573", ":"),
}
MAIN = ["ascon_mac", "ascon_prf", "amac", "mac_from_xof128", "mac_from_hash256",
        "prf_from_xof128", "cxof128", "hash256_bare", "xof128_bare"]


def save(fig, name):
    """Write one figure to a PNG file and close it."""
    fig.tight_layout()
    fig.savefig(OUT + "/" + name + ".png", dpi=150)
    plt.close(fig)
    print("wrote", name + ".png")


def lines(targets, column, ylabel, title, name):
    """One line per function: a summary column against message size, on log
    scales (sizes go from 1 byte to 64 KB)."""
    fig, ax = plt.subplots(figsize=(8, 5))
    for target in targets:
        data = summary[summary["target"] == target].sort_values("size")
        if len(data) > 0:
            label, colour, style = STYLE[target]
            ax.plot(data["size"], data[column], style, color=colour, marker="o",
                    markersize=3, label=label)
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xlabel("message size (bytes, log scale)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
    save(fig, name)


def speedups(names, title, name):
    """How many times faster, against message size: one line per comparison."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for comparison in names:
        data = comparisons[comparisons["comparison"] == comparison].sort_values("size")
        ax.plot(data["size"], data["speedup"], marker="o", markersize=3, label=comparison)
    ax.axhline(1, color="black", linewidth=0.8)
    ax.set_xscale("log", base=2)
    ax.set_xlabel("message size (bytes, log scale)")
    ax.set_ylabel("times faster (medians)")
    ax.set_title(title)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    save(fig, name)


def bars(groups, series, ylabel, title, name, tilt=0):
    """Grouped bars: one group per x label, one bar per series. Each series is
    (label, colour, values, texts); the texts are written on top of the bars
    (an empty list for none). tilt turns long x labels so they do not overlap."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    width = 0.8 / len(series)
    for i in range(len(series)):
        label, colour, values, texts = series[i]
        positions = []
        for g in range(len(groups)):
            positions.append(g + i * width - 0.4 + width / 2)
        ax.bar(positions, values, width, color=colour, label=label)
        for j in range(len(texts)):
            ax.text(positions[j], values[j], texts[j], ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(groups)))
    if tilt:
        ax.set_xticklabels(groups, fontsize=8, rotation=tilt, ha="right")
    else:
        ax.set_xticklabels(groups, fontsize=8)
    ax.margins(y=0.12)                     # room for the texts on top
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(fontsize=7)
    save(fig, name)


# fig1: execution time against message size
lines(MAIN, "cycles_median", "CPU cycles per call (median, log scale)",
      "Execution time against message size", "fig1_execution_time")

# fig2: short messages - bars at 1, 8 and 16 bytes (the sizes that were measured)
short_sizes = []
for size in [1, 8, 16]:
    if size in list(summary["size"]):
        short_sizes.append(size)
series = []
for target in ["ascon_prfshort", "ascon_mac", "amac", "mac_from_xof128", "mac_from_hash256"]:
    data = summary[summary["target"] == target]
    values = []
    for size in short_sizes:
        match = data[data["size"] == size]
        if len(match) > 0:
            values.append(match["cycles_median"].iloc[0])
        else:
            values.append(0)
    series.append((STYLE[target][0], STYLE[target][1], values, []))
group_names = []
for size in short_sizes:
    group_names.append(str(size) + " B")
bars(group_names, series, "CPU cycles per call (median)", "Short messages: a 16-byte tag",
     "fig2_short_messages")

# fig3 and fig4: cycles per byte, and throughput (needs the nominal frequency)
lines(MAIN, "cycles_per_byte_median", "CPU cycles per byte (median, log scale)",
      "Cycles per byte against message size", "fig3_cycles_per_byte")
if ghz:
    lines(MAIN, "MBps_median", "MB per second (median, log scale)",
          f"Throughput (converted from cycles at {ghz} GHz)", "fig4_throughput")

# fig5: heat map - each function's cycles per byte, divided by the fastest
table = summary[summary["target"].isin(MAIN + ["cxof128_ref"])].pivot_table(
    index="target", columns="size", values="cycles_per_byte_median")
relative = table / table.min()
fig, ax = plt.subplots(figsize=(10, 5))
image = ax.imshow(relative.values, cmap="RdYlGn_r", aspect="auto")
ax.set_xticks(range(len(relative.columns)))
ax.set_xticklabels(relative.columns, rotation=45)
ax.set_yticks(range(len(relative.index)))
names = []
for target in relative.index:
    names.append(STYLE[target][0])
ax.set_yticklabels(names, fontsize=8)
for i in range(relative.shape[0]):
    for j in range(relative.shape[1]):
        value = relative.values[i, j]
        if pd.notna(value):
            ax.text(j, i, f"{value:.1f}", ha="center", va="center", fontsize=7)
fig.colorbar(image, label="times the fastest at that size")
ax.set_xlabel("message size (bytes)")
ax.set_title("Cost against the fastest function at each size")
save(fig, "fig5_heatmap")

# fig6: noise - one dot per size, for each function
fig, ax = plt.subplots(figsize=(8, 4.5))
present = []
for target in STYLE:
    if target in list(summary["target"]):
        present.append(target)
for i in range(len(present)):
    data = summary[summary["target"] == present[i]]
    ax.scatter([i] * len(data), data["noise_pct"], color=STYLE[present[i]][1], s=12)
ax.axhline(5, color="red", linestyle="--", linewidth=1, label="5%: look at it")
ax.set_xticks(range(len(present)))
labels = []
for target in present:
    labels.append(STYLE[target][0])
ax.set_xticklabels(labels, rotation=60, ha="right", fontsize=7)
ax.set_ylabel("noise (% of the mean)")
ax.set_title("How much each measurement varied (one dot per size)")
ax.legend(fontsize=8)
save(fig, "fig6_noise")

# fig7 and fig8: speed-ups
speedups(["Ascon-Mac vs AMAC", "Ascon-Mac vs MAC from XOF128", "Ascon-Mac vs MAC from Hash256"],
         "How many times faster Ascon-Mac is", "fig7_mac_speedup")
speedups(["Ascon-Prf vs PRF from XOF128"], "How many times faster Ascon-Prf is", "fig8_prf_speedup")

# fig9: key derivation, with the speed-up written on each AKDF bar
kdf = comparisons[comparisons["comparison"] == "Ascon-Prf vs AKDF"].sort_values("size")
group_names = []
texts = []
for size in kdf["size"]:
    group_names.append(str(int(size)) + "-byte key")
for speedup in kdf["speedup"]:
    texts.append(f"{speedup:.2f}x")
bars(group_names,
     [(STYLE["prf_kdf"][0], STYLE["prf_kdf"][1], list(kdf["A_cycles"]), []),
      (STYLE["akdf"][0], STYLE["akdf"][1], list(kdf["B_cycles"]), texts)],
     "CPU cycles per call (median)", "Key derivation: same key, data, label and key length",
     "fig9_kdf")

# fig10: CXOF128 - Kerry's opt64 build, the reference, and XOF128
lines(["cxof128", "cxof128_ref", "xof128_bare"], "cycles_per_byte_median",
      "CPU cycles per byte (median, log scale)",
      "CXOF128: opt64 (Kerry's recipe), reference, and XOF128", "fig10_cxof")

# fig11: code size
bars(list(code_size["function"]),
     [("-O3 (the code we time)", "#2471a3", list(code_size["text_bytes_O3"]), []),
      ("-Os (small devices)", "#b3b6b7", list(code_size["text_bytes_Os"]), [])],
     "bytes of machine code", "Code size (execution size)", "fig11_code_size", tilt=25)
