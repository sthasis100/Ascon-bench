# INSuRE Team 4 — Supplemental Timing Reliability Experiment (V2)

**Study:** Performance Benchmarking for Ascon Extensions (v1)\
**Date:** November 3, 2026\
**Experiment conducted by:** Leela Pavan Kumar\
**Base framework:** Team 4's existing Ascon benchmarking code (shared by Aashish); this document covers a supplementary experiment, not a replacement for the team's established study.

## 1. Research question

Does adding `LFENCE` instruction ordering around `RDTSC` readings change the measured performance or repeatability of Ascon-Mac on this Windows computer? The purpose is to **evaluate**, not assume, that the fenced method is more reliable.

The original 13-program benchmark, input-selection policy, known-answer tests, and `getcycles` cross-check remain the team's baseline methodology. This supplemental study isolates a timing-method variation for **Ascon-Mac only**.

## 2. Experimental setup and controlled variables

- **System:** Windows 11, Intel Core i5-9300HF (as identified in the earlier full Windows benchmark); requested CPU affinity: core 2. Affinity confirmation was checked for each process.
- **Compiler:** MSYS2 GCC 16.2.0; common flags: `-O3 -march=native -std=c11 -fno-lto`.
- **Crypto implementation:** Ascon-Mac `opt64` from the pinned Ascon-C submodule, commit `446347f21b209f3921c65ece70027c366cbe1693`.
- **Source:** Both executables were compiled from `src/bench_v2.c`, derived from Team 4's `src/bench.c`. The **sole intended functional difference** was compiling the fenced executable with `-DBENCH_V2_FENCED`.
- **Timing variants:** Unfenced uses `__rdtsc()`; fenced uses `_mm_lfence(); __rdtsc(); _mm_lfence()` at each timestamp read. Timing covers the same batch of Ascon calls in both variants.
- **Test cases:** Input lengths of 1, 8, 16, 64, and 1536 bytes; fixed 16-byte key; deterministic input generation; one untimed warm-up batch per size; 30 recorded batches per size and process. The batch size was inherited from V1 (`max(32, floor(262144/input_size))` function calls).
- **Correctness:** Before timing, the two compiled executables returned identical cryptographic outputs for all five tested input sizes. The team's official KAT validation is separate and is not replaced by this equivalence check.
- **Session design:** Four rounds of four independent process sessions, alternating `unfenced, fenced, fenced, unfenced` and `fenced, unfenced, unfenced, fenced`. This produces eight sessions per method, 150 measurements per session, **2,400 raw measurements** overall.
- **Metric:** `RDTSC` counter ticks per function call (`total ticks / batch calls`), **not** independently measured nanoseconds or actual retired core cycles.

The experiment manifest records the Python/Windows versions, order, flags, cryptographic-source hash, executable hashes, and start/end timestamps. No outlier removal or post-hoc data filtering was applied.

## 3. Observed results

Each reported central value is the **median of eight session medians** for that method and input size. The session CV is the sample coefficient of variation **across the eight session medians**, not the CV of all raw batches.

| Input | Unfenced (ticks/call) | Fenced (ticks/call) | Fenced / unfenced | Session CV, unfenced | Session CV, fenced |
|---|---:|---:|---:|---:|---:|
| 1 byte | 228.87 | 227.46 | 0.994 | 1.10% | 1.21% |
| 8 bytes | 216.85 | 217.84 | 1.005 | 12.15% | 2.09% |
| 16 bytes | 218.85 | 219.51 | 1.003 | 1.19% | 3.50% |
| 64 bytes | 441.78 | 447.53 | 1.013 | 1.29% | 1.36% |
| 1536 bytes | 5690.09 | 5755.00 | 1.011 | 1.02% | 2.44% |

**Notable 8-byte observation:** The unfenced session 1 median was **295.15 ticks/call**; the other seven unfenced sessions were **216.35–220.85** ticks/call. The eight fenced session medians were **216.32–228.24** ticks/call. Thus, the large unfenced CV was driven substantially by a single slow session. Do not remove this session or attribute it to a particular cause without additional evidence.

## 4. Interpretation and limitations

1. **No universal improvement established.** The median times were broadly similar. Fencing coincided with lower *between-session* variability for the 8-byte case, but higher variability for 1, 16, and 1536 bytes; the 64-byte session CV was similar. The observed 8-byte improvement therefore cannot support a blanket claim that `LFENCE` eliminates timing noise.
2. **Causal mechanism unknown.** Windows scheduling, processor power/thermal behavior, background work, initial process state, and measurement ordering are plausible contributors. None was instrumented directly. A non-randomized ABBA/BAAB ordering reduces simple ordering bias but does not eliminate time-dependent confounding.
3. **Clock semantics matter.** An invariant TSC helps with clock stability, but these are TSC ticks, not necessarily executed CPU cycles. The nominal 2.4 GHz CPU label does not independently calibrate the TSC-to-time conversion.
4. **Single device and function.** These results concern Ascon-Mac `opt64` on one Windows laptop. They do not establish reliability for every Ascon extension, input size, compiler, or operating system.
5. **No inferential claim yet.** Eight process sessions per method are useful descriptive evidence but insufficient to claim statistically proven superiority. Any confidence intervals or formal tests should treat **process sessions**, rather than 30 within-session measurements, as the primary independent experimental units.
6. **Earlier anomaly remains documented.** In the separate full 13-program Windows run, the 1-byte Ascon-Mac median was 389.83 ticks/call, while a targeted recheck measured 230.42 ticks/call. The initial full-run `getcycles` cross-check flagged a **68.39%** discrepancy at that point. Those original measurements are retained, not silently replaced by this supplemental experiment.

## 5. Reproduction and evidence

From the repository root on an x86 Windows computer with MSYS2 UCRT64 GCC and the pinned Ascon-C submodule:

```bash
gcc -O3 -march=native -std=c11 -fno-lto \
  -Iascon-c/tests -Iascon-c/src \
  -Iascon-c/crypto_auth/asconmacv13/opt64 \
  -DMODE_AUTH src/bench_v2.c \
  ascon-c/crypto_auth/asconmacv13/opt64/prf.c \
  -o build/mac_v2_unfenced.exe

gcc -O3 -march=native -std=c11 -fno-lto \
  -Iascon-c/tests -Iascon-c/src \
  -Iascon-c/crypto_auth/asconmacv13/opt64 \
  -DMODE_AUTH -DBENCH_V2_FENCED src/bench_v2.c \
  ascon-c/crypto_auth/asconmacv13/opt64/prf.c \
  -o build/mac_v2_fenced.exe

python src/run_timing_comparison_v2.py
```

The runner intentionally refuses to overwrite `results/v2_timing_comparison/`; move or rename that directory **without deleting the original data** before a new run. Record the new session as a distinct experiment.

**Source and artifacts:**

- `src/bench.c` — original Team 4 timing framework; unchanged by this experiment.
- `src/bench_v2.c` — derived source with a compile-time switch for fenced timing.
- `src/run_timing_comparison_v2.py` — alternated-session runner and descriptive summary.
- `results/v2_timing_comparison/raw_timing_comparison.csv` — all 2,400 measurements.
- `results/v2_timing_comparison/session_summary.csv` — 10 method/size summary rows.
- `results/v2_timing_comparison/experiment_manifest.json` — protocol metadata and SHA-256 identifiers.
- `results/windows_i5_2026-11-03/` — separate full V1 Windows dataset and its validation/diagnostics.

## 6. Next research actions

- Repeat the ABBA/BAAB experiment in another **separately preserved** run, recording power mode, background workload, and any available CPU telemetry; inspect whether the 8-byte session effect recurs.
- Audit machine-code and timestamp ordering to confirm the fenced/unfenced binaries differ only in the intended code path, accounting for compiler-generated differences.
- If extending statistical inference, compute paired-by-round contrasts and uncertainty at the **session/round level**, while keeping raw within-session values available.
- Report V1 performance findings and supplemental V2 timing-reliability findings as **separate** results to Team 4 and Kerry McKay.

**Current conclusion:** On this machine, adding LFENCE did not consistently reduce observed session-level timing variation. The 8-byte unfenced instability merits follow-up, but its cause is not established. The primary deliverable of this study is a reproducible investigation with preserved raw data and documented limitations.
