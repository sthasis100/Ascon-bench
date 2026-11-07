"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
plots.py  -  draw the report's figures from the analysed results

Each timing figure has four panels, one per function, each with its own
scale: Ascon-Mac, Ascon-Prf, Ascon-PrfShort and AKDF. The x axis is the
message length, except for AKDF, where it is the length of the new key.

THE FIGURES (saved in the results folder, under figures)
  fig1_execution_time   median cycles per call, with the fastest-to-slowest
                        range of the repetitions shaded
  fig2_cycles_per_byte  median cycles per byte
  fig3_throughput       MB per second (converted from cycles)
  fig4_noise            how much the repetitions varied, against 5%
  fig5_code_size        bytes of machine code at -O3 and -Os

RUN (Command Prompt, in the project folder), after analyze.py:
  python plots.py                  the real results
  python plots.py results_pilot    the pilot's results
===========================================================================
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")           # draw straight to files; no window opens
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator, NullFormatter, NullLocator
import pandas as pd

RESULTS = "results"
if len(sys.argv) > 1:
    RESULTS = sys.argv[1]
OUT = RESULTS + "/figures"
os.makedirs(OUT, exist_ok=True)

summary = pd.read_csv(RESULTS + "/summary.csv")

# The four functions: name in the CSV, panel title, x-axis label.
FUNCTIONS = [
    ("ascon_mac",      "Ascon-Mac (16-byte tag)",       "message size (bytes)"),
    ("ascon_prf",      "Ascon-Prf (64-byte output)",    "message size (bytes)"),
    ("ascon_prfshort", "Ascon-PrfShort (16-byte tag)",  "message size (bytes)"),
    ("akdf",           "AKDF (NIST planned)",           "length of the new key (bytes)"),
]

# Colours and ink (light chart surface).
SERIES = "#2a78d6"           # the one series in each panel
SECOND = "#eb6834"           # the second series of the code-size bars
INK = "#0b0b0b"
INK_SOFT = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 9, "text.color": INK, "axes.labelcolor": INK_SOFT,
    "axes.titlesize": 10, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "axes.edgecolor": AXIS, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelcolor": INK_SOFT, "ytick.labelcolor": INK_SOFT,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "legend.frameon": False,
})


def save(fig, name):
    """Write one figure to a PNG file and close it."""
    fig.savefig(OUT + "/" + name + ".png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote", name + ".png")


def size_label(size):
    """65536 -> '65,536'"""
    return f"{int(size):,}"


# Plain numbers on every y axis (1,000 rather than 10^3 or 1000).
PLAIN = FuncFormatter(lambda value, position: f"{value:,.0f}" if value >= 10 else f"{value:g}")


def panels(column, ylabel, title, name, band=None, reference=None, note=None, log_y=True):
    """One panel per function: a summary column against size.
    band       (low column, high column) to shade, or None
    reference  a value to draw as a dashed line (with its label), or None
    note       a line of text under the figure, or None
    log_y      allow a log scale for the y axis (when values span over 10x)"""
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    for ax, (target, label, xlabel) in zip(axes.flat, FUNCTIONS):
        data = summary[summary["target"] == target].sort_values("size")
        ax.set_title(label, loc="left")
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if len(data) == 0:
            ax.text(0.5, 0.5, "no data", transform=ax.transAxes, ha="center", color=MUTED)
            continue
        x = data["size"]
        if band:
            ax.fill_between(x, data[band[0]], data[band[1]], color=SERIES, alpha=0.18,
                            linewidth=0)
        ax.plot(x, data[column], color=SERIES, linewidth=1.5, marker="o", markersize=4)
        # Log scales only where the values span more than 10 times.
        if x.max() / x.min() > 10:
            ax.set_xscale("log", base=2)
        values = data[column]
        if band:
            values = pd.concat([data[band[0]], data[band[1]]])
        if log_y and values.min() > 0 and values.max() / values.min() > 10:
            ax.set_yscale("log")
            # 1, 2, 5, 10, 20, 50 ... when the values span 3 powers of 10 or
            # less; otherwise only 1, 10, 100 ...
            if values.max() / values.min() <= 1000:
                ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1, 2, 5)))
            ax.yaxis.set_minor_formatter(NullFormatter())
        ax.yaxis.set_major_formatter(PLAIN)
        # Label only sizes that were measured, and not too many of them.
        sizes = list(x)
        if len(sizes) > 6:
            sizes = sizes[::3] if sizes[-1] in sizes[::3] else sizes[::3] + [sizes[-1]]
        ax.xaxis.set_major_locator(FixedLocator(sizes))
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_xticklabels([size_label(s) for s in sizes])
        if reference:
            value, text = reference
            ax.axhline(value, color=MUTED, linestyle="--", linewidth=1)
            ax.text(x.max(), value, " " + text, color=INK_SOFT, va="bottom", ha="right",
                    fontsize=8)
            ax.set_ylim(bottom=0, top=max(values.max(), value) * 1.15)
    fig.suptitle(title, x=0.01, ha="left", fontsize=12, fontweight="bold")
    fig.tight_layout()
    if note:
        fig.text(0.01, -0.01, note, color=INK_SOFT, fontsize=8, ha="left", va="top")
    save(fig, name)


# fig1: execution time
panels("cycles_median", "CPU cycles per call",
       "Execution time against size", "fig1_execution_time",
       band=("cycles_min", "cycles_max"),
       note="Line: median of the repetitions. Shaded: from the fastest to the slowest "
            "repetition. Cycles are RDTSC ticks.")

# fig2: cycles per byte
panels("cycles_per_byte_median", "CPU cycles per byte (median)",
       "Cycles per byte against size", "fig2_cycles_per_byte",
       note="For AKDF, the bytes are the bytes of the new key it makes.")

# fig3: throughput (only if the nominal frequency was known)
if "MBps_median" in summary.columns:
    panels("MBps_median", "MB per second (median)",
           "Throughput against size", "fig3_throughput",
           note="Converted from cycles with the CPU's nominal frequency.")

# fig4: noise
panels("noise_pct", "noise (% of the mean)",
       "How much the repetitions varied", "fig4_noise", reference=(5, "5%"), log_y=False,
       note="Noise = standard deviation of the repetitions as a % of their mean. "
            "Under 5% is good.")

# fig5: code size (execution size)
code_size = pd.read_csv(RESULTS + "/code_size.csv")
NAMES = {"Ascon-Mac": "Ascon-Mac", "Ascon-Prf": "Ascon-Prf", "Ascon-PrfShort": "Ascon-PrfShort",
         "Ascon-CXOF128 (opt64)": "Ascon-CXOF128 opt64\n(used by AKDF)"}
# (older results files may add a note after "opt64"; the label shown is ours)
code_size["function"] = code_size["function"].where(
    ~code_size["function"].str.startswith("Ascon-CXOF128 (opt64"), "Ascon-CXOF128 (opt64)")
code_size = code_size[code_size["function"].isin(list(NAMES))]
fig, ax = plt.subplots(figsize=(8, 4.5))
width = 0.38
for i, (column, label, colour) in enumerate([("text_bytes_O3", "-O3 (the code we time)", SERIES),
                                              ("text_bytes_Os", "-Os (small devices)", SECOND)]):
    positions = [g + (i - 0.5) * (width + 0.02) for g in range(len(code_size))]
    bars = ax.bar(positions, code_size[column], width, color=colour, label=label, zorder=2)
    for bar, value in zip(bars, code_size[column]):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{int(value):,}",
                ha="center", va="bottom", fontsize=8, color=INK_SOFT)
ax.set_xticks(range(len(code_size)))
ax.set_xticklabels([NAMES[f] for f in code_size["function"]])
ax.grid(axis="x", visible=False)
ax.margins(y=0.12)
ax.yaxis.set_major_formatter(PLAIN)
ax.set_ylabel("bytes of machine code")
ax.set_title("Code size (execution size)", loc="left", fontsize=12)
ax.legend(loc="upper left")
fig.tight_layout()
save(fig, "fig5_code_size")
