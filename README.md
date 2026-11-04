# Ascon-bench

**Performance Benchmarking for Ascon Extensions (v1)**
INSuRE, Fall 2026 · University at Albany (SUNY) · Team 4

Team: Aashish Shrestha, Leela Pavan Kumar Kunapureddy, Simbarashe Mandizvidza, Lakshika Vaishnav
Problem mentor: NIST · Instructor: Dr. Sanjay Goel

---

## What this project is about

NIST standardized Ascon for lightweight cryptography in **NIST SP 800-232**. The standard has four functions: Ascon-AEAD128, Ascon-Hash256, Ascon-XOF128 and Ascon-CXOF128. None of them takes a secret key for making tags or new keys.

The Ascon designers have proposed three extensions that do: **Ascon-Mac**, **Ascon-Prf** and **Ascon-PrfShort**. Our job is to measure how fast these extensions are on an ordinary Windows laptop (AMD Ryzen 7 PRO 7840U), compared with:

- what you can already do with the standard functions, for example a MAC made by hashing the key and the message with Ascon-XOF128, and
- NIST's planned **AMAC** and **AKDF**, which are built on Ascon-CXOF128. Their definitions are preliminary, not final.

## Where the project stands

| Step | What happens | Status |
|---|---|---|
| 0 | Set up the tools and the project folder | Done |
| 1 | Check that the CPU's cycle counter is safe to time with | Done |
| 2 | Check that the designers' code passes its own tests | Done: 11 of 11 passed |
| 3 | Make the two Ascon versions the designers don't ship, and check them | Done: 1,089 of 1,089 answers match |
| 4 | Build AKDF and check it three separate ways | Done |
| 5 | Midterm presentation of steps 0 to 4 and the plan | Done |
| 6 | Write the benchmarking program and check its answers | Done |
| 7 | Run the benchmark | Done |
| 8 | Analyze the results | Done |
| 9 | Final report and presentation | In progress |

## What we compare

Each new function is only compared with things that do the same job.

| Job | New function | Compared with | Sizes |
|---|---|---|---|
| Make a 16-byte tag (MAC) | Ascon-Mac | MAC from Ascon-XOF128 (the main comparison), MAC from Ascon-Hash256, AMAC | 13 message sizes |
| Make 64 bytes of keyed output (PRF) | Ascon-Prf | PRF from Ascon-XOF128 | 13 message sizes |
| Tag a very short message | Ascon-PrfShort | Ascon-Mac, MAC from Ascon-XOF128, AMAC | 1, 8 and 16 bytes |
| Make a new key from a key | Ascon-Prf | AKDF | New keys of 16, 32 and 64 bytes |

- **"MAC from X"** means: put the 16-byte key in front of the message and hash both with X. The standard functions have no key slot, so this is how you would make a MAC with them today. **"PRF from Ascon-XOF128"** is made the same way and gives 64 bytes.
- **MAC from Ascon-XOF128** is the main comparison because it gives exactly 16 bytes, like Ascon-Mac. Ascon-Hash256 always gives 32 bytes, so it is not an exact match, but it is the most obvious option today.
- **AMAC and AKDF** are timed exactly as NIST plans them (the definition is in Step 4), on our fast Ascon-CXOF128 from Step 3.
- **The 13 message sizes** are 1, 8, 16, 32, 64, 128, 256, 512, 1,024, 1,536, 4,096, 16,384 and 65,536 bytes.
- **Ascon-PrfShort** takes at most 16 bytes. It is timed at 1, 2, 4, 8 and 16 bytes, and compared at 1, 8 and 16 bytes, the short sizes its rivals are also timed at.
- **Not compared:** Ascon-AEAD128, because encryption is a different job.

To keep it fair, every function gets the same 16-byte key and the same message bytes, every function uses the designers' fast 64-bit code (opt64), and every function is timed by the same program in the same way.

---

## Step 0: Set up

**Tools** (everything below runs in Windows Command Prompt):

- Git for Windows
- MSYS2, with its UCRT64 GCC, CMake and Ninja installed (packages `mingw-w64-ucrt-x86_64-gcc`, `mingw-w64-ucrt-x86_64-cmake` and `mingw-w64-ucrt-x86_64-ninja`). Add `C:\msys64\ucrt64\bin` to your PATH so `gcc`, `cmake` and `ninja` work in Command Prompt.
- Python 3, with the pandas and matplotlib packages: `python -m pip install pandas matplotlib`

**Get the project**, including the designers' code (ascon-c, pinned to commit 446347f):

```
git clone --recurse-submodules https://github.com/sthasis100/Ascon-bench.git
cd Ascon-bench
mkdir build
```

If you cloned without the designers' code, run `git submodule update --init`.

If you start from the zip file instead, unzip it and get the designers' code yourself:

```
cd Ascon-bench
git clone https://github.com/ascon/ascon-c
git -C ascon-c checkout 446347f
mkdir build
```

**What you get:** the project folder, with the designers' code in `ascon-c`. We never change anything inside `ascon-c`. Run every command below from the `Ascon-bench` folder.

---

## Step 1: Check the CPU's cycle counter

**Why:** We time everything with RDTSC, the CPU's cycle counter. It is only safe to use if the counter is "invariant", meaning it ticks at the same rate all the time, even when the CPU speeds up or slows down. The CPU reports this itself through the CPUID instruction.

**Run:**

```
gcc -O2 -Wall -Wextra src\check_tsc.c -o build\check_tsc.exe
build\check_tsc.exe
```

**What you get:** three lines.

- `brand=` the CPU's name.
- `invariant_tsc=1` means the counter is safe to use. `0` means it is not.
- `cpuid16_base_mhz=` the base speed in MHz, or `0` if the CPU does not report it (AMD CPUs usually don't).

The program also exits with code 0 if the counter is invariant and 1 if it is not. Our test laptop prints `invariant_tsc=1`.

**What happens next:** Cycle counts on this laptop can be trusted, so the rest of the project times with RDTSC.

---

## Step 2: Check the designers' code passes its own tests

**Why:** Before trusting any timing, we make sure every function we use gives the official answers. The designers ship official answer files (known-answer tests, or KATs) and a CMake setup that checks them.

**Run:**

```
cmake -S ascon-c -B build\cmake -G Ninja -DCMAKE_C_COMPILER=gcc -DCMAKE_BUILD_TYPE=Release -DALG_LIST="asconhash256;asconxof128;asconcxof128;asconmacv13;asconprfv13;asconprfsv13" -DIMPL_LIST="ref;opt64" -DTEST_LIST="genkat"
cmake --build build\cmake
ctest --test-dir build\cmake
```

**What you get:** 11 tests, one for each function in each version we use. "ref" is the designers' slow reference code and "opt64" is their fast 64-bit code. Ascon-CXOF128 only comes as ref, which is why there are 11 tests and not 12. All 11 must say `Passed`. Our run is saved in `docs\ctest_results.txt`: 100% of the 11 tests passed.

**What happens next:** We know the designers' code works correctly on our laptop. Any difference we measure later comes from the functions themselves, not from a broken build.

---

## Step 3: Make the two Ascon versions the designers don't ship

**Why:**

1. **A fast Ascon-CXOF128.** CXOF128 only comes as slow reference code, but everything else we time uses the fast opt64 code, so timing it as it is would not be fair. As suggested by our problem mentor, we copy the opt64 Ascon-XOF128 folder and replace its `hash.c` with CXOF128's `hash.c`, plus one added line so the two sets of names match. The speed comes from the permutation files, which both functions share.
2. **Ascon-XOF128 that gives 16 bytes.** For a fair MAC comparison, XOF128 has to give 16 bytes, like Ascon-Mac. We copy XOF128 and change one number, from 64 to 16.

**Run:**

```
python make_variants.py
```

**What you get:** two new folders. Never edit them by hand; the script remakes them each time.

- `variants\asconcxof128_opt64` is CXOF128 on the fast opt64 code.
- `variants\asconxof128_out16` is XOF128 that gives 16 bytes.

The script ends by checking that nothing inside `ascon-c` was changed, and prints `ascon-c is untouched (git status is clean)`.

**Check the fast CXOF128 against the official answers:**

```
set "V=variants\asconcxof128_opt64"
mkdir build\kat_cxof
gcc -O2 -I%V% %V%\hash.c %V%\permutations.c %V%\printstate.c -Iascon-c\tests ascon-c\tests\genkat_cxof.c -o build\kat_cxof\genkat.exe
cd build\kat_cxof
genkat.exe
cd ..\..
fc build\kat_cxof\LWC_CXOF_KAT_128_512.txt ascon-c\crypto_cxof\asconcxof128\LWC_CXOF_KAT_128_512.txt
```

`genkat.exe` writes its answer file into the folder it runs in, which is why the commands step into `build\kat_cxof` first. `fc` should print `FC: no differences encountered`. That means all 1,089 answers match: every message length from 0 to 32 bytes, with every label length from 0 to 32 bytes.

**What happens next:** We now have a fast CXOF128 we can trust. AMAC and AKDF are built on it.

---

## Step 4: Build AKDF and check it three separate ways

**Why:** AKDF is NIST's planned key-derivation function. It has no official answer file yet, so we check it ourselves. NIST's planned definition is:

```
KOUT = CXOF128( bytepad(K, 32) || X || right_encode(L),  L,  "AKDF" || S )
```

K is the key, X is the key data, L is the length of the new key (counted in bits, as in KMAC), and S is a label saying what the new key is for. `bytepad` and `right_encode` come from NIST SP 800-185, the KMAC standard. NIST's planned AMAC uses the same input format, with the label "AMAC" and the message as X.

We compute the same example three ways:

1. our C version (`src\akdf.c`) on the fast CXOF128,
2. the same C file on the designers' slow reference CXOF128, and
3. an independent Python version (`akdf_check.py`) built on the designers' Python Ascon, pyascon.

For the Python version, first download `ascon.py` from https://github.com/meichlseder/pyascon into the project folder. It is not part of this repository.

**Run:**

```
set "V=variants\asconcxof128_opt64"
gcc -O2 -Wall -Wextra -I%V% %V%\hash.c %V%\permutations.c %V%\printstate.c -Iascon-c\tests src\akdf.c -o build\akdf.exe
build\akdf.exe > build\akdf_fast.txt

set "R=ascon-c\crypto_cxof\asconcxof128\ref"
gcc -O2 -Wall -Wextra -I%R% %R%\hash.c %R%\printstate.c -Iascon-c\tests src\akdf.c -o build\akdf_ref.exe
build\akdf_ref.exe > build\akdf_ref.txt

python akdf_check.py > build\akdf_python.txt

fc build\akdf_fast.txt build\akdf_ref.txt
fc build\akdf_fast.txt build\akdf_python.txt
```

**What you get:** three identical files, each holding the same example (K = 00..0F, X = 10..1F, S = "encryption key"):

```
AKDF with K = 00..0F, X = 10..1F, S = "encryption key"
L = 128 bits (16 bytes): F8F72937560F4F9EFFBB7DCE0CEB0155
L = 256 bits (32 bytes): 6CD7036A09031D9AEEFA6A6C0061A0952F7FEE16682C024367D7E43345306306
L = 512 bits (64 bytes): 0FD4BD653A1D257CFF52592801DE332A00F9EBA6F4E03814594E374F418274C4766E1C299C41187AEC8F09F6A625BC8C80DBC9D8F37E4EDD31D4B8666C8F4A97
```

Both `fc` commands should print `FC: no differences encountered`. Three separate routes giving the same answer means our AKDF is built correctly.

**What happens next:** The benchmarking program (Step 6) builds the AKDF and AMAC input in exactly the same way, on the fast CXOF128.

---

## Step 5: Midterm presentation (done)

We presented Steps 0 to 4 and the benchmark plan at the midterm.

---

## Step 6: Write the benchmarking program, and check its answers

**Why:** A comparison is only fair if both sides are timed in exactly the same way, with the same inputs. So one C program, `src\bench.c`, times every function.

**How it works:**

- **One program, built nine times.** `bench.c` is compiled once for each function we time. Two things choose the function: the switch `-DMODE_...` decides how the function is called, and the Ascon folder given with `-I` decides whose code answers the call. Each function needs its own program because the Ascon folders use the same function names (for example `crypto_auth`), so two of them cannot be built into one program.

| Program | What it times | Mode | Ascon folder |
|---|---|---|---|
| ascon_mac | Ascon-Mac (proposed) | AUTH | `ascon-c\crypto_auth\asconmacv13\opt64` |
| ascon_prf | Ascon-Prf (proposed) | AUTH | `ascon-c\crypto_auth\asconprfv13\opt64` |
| ascon_prfshort | Ascon-PrfShort (proposed) | AUTH | `ascon-c\crypto_auth\asconprfsv13\opt64` |
| prf_kdf | Ascon-Prf given AKDF's inputs (proposed) | PRF_KDF | `ascon-c\crypto_auth\asconprfv13\opt64` |
| amac | AMAC (NIST planned) | AMAC | `variants\asconcxof128_opt64` |
| akdf | AKDF (NIST planned) | AKDF | `variants\asconcxof128_opt64` |
| mac_from_xof128 | MAC from Ascon-XOF128, 16 bytes | KEYED_HASH | `variants\asconxof128_out16` |
| mac_from_hash256 | MAC from Ascon-Hash256, 32 bytes | KEYED_HASH | `ascon-c\crypto_hash\asconhash256\opt64` |
| prf_from_xof128 | PRF from Ascon-XOF128, 64 bytes | KEYED_HASH | `ascon-c\crypto_hash\asconxof128\opt64` |

- **The same inputs for everyone.** A fixed 16-byte key and 64 KB of message bytes, made by a small number generator from a fixed starting number, so every function on every computer gets the same bytes. For AKDF, and for Ascon-Prf on AKDF's inputs, X is the first 16 bytes of the message and the label S is "encryption key". AMAC makes a 16-byte tag (L = 128 bits) with an empty S.
- **Only the call is timed.** Work that is not part of the function (putting the key in front of the message, building the AMAC and AKDF input) is done once per size, before timing starts.
- **Timing with RDTSC.** One call is too short to time on its own, so the program times a batch of calls between two readings of the cycle counter, and divides. A batch is 262,144 ÷ size calls (about 256 KB of message), and never fewer than 32 calls. One warm-up batch is thrown away first. The program stays on one CPU core (core 2), at high priority.
- **Every repetition is kept.** The program prints one CSV line per timed batch and never averages anything.
- **A check mode.** With 0 repetitions, nothing is timed: the program prints each result in hex so it can be checked.

**Check one program by hand** (Ascon-Mac):

```
set "F=ascon-c\crypto_auth\asconmacv13\opt64"
gcc -O3 -march=native -I%F% %F%\permutations.c %F%\prf.c %F%\printstate.c -Iascon-c\tests -DMODE_AUTH src\bench.c -o build\bench_ascon_mac.exe
build\bench_ascon_mac.exe ascon_mac 0 1,8,16,64,1024,65536
```

The arguments are: a label, the number of repetitions (0 = check mode), the sizes, and optionally the CPU core.

**What you get:** a header line and one line per size, for example `ascon_mac,auth,16,C1CC87D845DB23B90D92D6C834BE2812`. These must match the lines in `docs\bench_verify_expected.txt`, which holds the 45 answers the nine programs must give. Each of the 45 was confirmed a separate way: Ascon-Mac, Ascon-Prf, Ascon-PrfShort and Ascon-Prf on AKDF's inputs against the designers' reference C code (not the fast code we time), and the MACs and PRF from Ascon-Hash256 and Ascon-XOF128, AMAC and AKDF against the designers' Python Ascon (pyascon). The program also prints `pinned to core 2` on the screen; that line is normal and is not part of the results.

**Check all nine at once**, after Step 7 has built them:

```
del build\verify.txt 2>nul
build\bench_ascon_mac.exe ascon_mac 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_ascon_prf.exe ascon_prf 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_ascon_prfshort.exe ascon_prfshort 0 1,8,16 >> build\verify.txt
build\bench_mac_from_hash256.exe mac_from_hash256 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_mac_from_xof128.exe mac_from_xof128 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_prf_from_xof128.exe prf_from_xof128 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_amac.exe amac 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_akdf.exe akdf 0 16,32,64 >> build\verify.txt
build\bench_prf_kdf.exe prf_kdf 0 16,32,64 >> build\verify.txt
fc build\verify.txt docs\bench_verify_expected.txt
```

`fc` should print `FC: no differences encountered`.

**What happens next:** Every program computes the right answer, so its timings are timings of the right work.

---

## Step 7: Run the benchmark

**Why:** About 100 commands have to run in the same order, with the same flags, every time. `run_all.py` runs them all, so nothing is typed by hand.

**Before you start:** plug the laptop in, close other programs, and make sure Step 3 has made the `variants` folder.

**Run** a quick trial first, then the real study:

```
python run_all.py --pilot
python run_all.py
```

**What it does, in order.** It stops at once if anything fails.

1. Records the machine (CPU, Windows version, compiler, flags, the ascon-c commit) and checks the cycle counter again. It stops if the counter is not invariant.
2. Builds the nine benchmark programs from Step 6, all with `-O3 -march=native`.
3. Checks the answers before anything is timed: the official answer files for Ascon-Mac, Ascon-Prf, Ascon-PrfShort, Ascon-Hash256, Ascon-XOF128 and our fast Ascon-CXOF128 (each built with the designers' own test program and our flags); the 16-byte Ascon-XOF128 (all 1,025 answers must be the first 16 bytes of the official ones); and 9 answers of AMAC, AKDF and Ascon-Prf on AKDF's inputs, which have no official answer file yet. If any check fails, nothing is timed.
4. Measures code size: the bytes of machine code of each Ascon implementation we time, at -O3 (the code we time) and -Os (what a small device would use).
5. Times every program at every size, in a shuffled order (always the same order), so the laptop warming up does not always slow down the same function.

| | Pilot (`--pilot`) | Real study |
|---|---|---|
| Repetitions per point | 5 | 30 |
| Message sizes for Ascon-PrfShort | 1 and 16 bytes | 1, 2, 4, 8 and 16 bytes |
| New key lengths for AKDF and Ascon-Prf on AKDF's inputs | 16 and 64 bytes | 16, 32 and 64 bytes |
| Message sizes for the other six programs | 1, 16 and 1,536 bytes | the 13 message sizes |
| Results folder | `results_pilot` | `results` |

The pilot can never overwrite the real results.

**What you get** (in `results`, or `results_pilot` for the pilot):

- `environment.json`: the machine, compiler, flags and settings.
- `kat_results.csv`: the 8 answer checks, each PASS or FAIL.
- `code_size.csv`: the code size of each implementation at -O3 and -Os.
- `raw_runs.csv`: one row per timed batch: program, mode, key, message and output bytes, repetition, calls in the batch, and cycles.

**What happens next:** the raw cycle counts go to the analysis.

---

## Step 8: Analyze the results

**Run:**

```
python analyze.py
python validate_getcycles.py
python plots.py
```

For the pilot, add `results_pilot` after each one, for example `python analyze.py results_pilot`.

**analyze.py** turns the raw counts into statistics and speed-ups:

- `summary.csv`: for each program and size: the number of runs, mean, median, standard deviation, fastest, slowest, noise (the standard deviation as a % of the mean), cycles per byte, time in ns, and MB/s.
- `comparisons.csv`: **the main results.** For each comparison and each size: both medians; **speedup**, how many times faster the proposed function is (the other function's median divided by the proposed function's median); **every_A_run_faster**, True when every single run of the proposed function beat every single run of the other; and a note.
- `raw_runs_detailed.csv`: every single measurement with its algorithm, implementation folder, sizes, repetition, cycles, cycles per call and ns per call.
- On the screen: the noise, how many comparisons the proposed function won in every run, and the smallest and largest speed-up of each comparison.

Time in ns and MB/s is converted from cycles with the CPU's nominal frequency (3.294 GHz on our laptop, read from Windows). It is a conversion, not a second clock.

The 8 comparisons:

| Comparison | Job |
|---|---|
| Ascon-Mac vs AMAC | MAC |
| Ascon-Mac vs MAC from XOF128 | MAC |
| Ascon-Mac vs MAC from Hash256 | MAC |
| Ascon-Prf vs PRF from XOF128 | PRF |
| Ascon-PrfShort vs Ascon-Mac | very short messages |
| Ascon-PrfShort vs MAC from XOF128 | very short messages |
| Ascon-PrfShort vs AMAC | very short messages |
| Ascon-Prf vs AKDF | new keys (the size is the length of the new key) |

**validate_getcycles.py** checks our timing method against the designers' own timing tool, `getcycles` (in `ascon-c\tests`). It builds getcycles with our flags for Ascon-Mac and Ascon-Prf, runs it five times, and compares its median cycles per byte with ours at 1, 8, 16, 32, 64 and 1,536 bytes. It writes `getcycles_validation.csv` and prints PASS or CHECK.

How to read it: both tools count with RDTSC, which ticks at a fixed rate, while turbo boost changes the CPU's real speed. Our program times each size for a long time, after a warm-up batch; getcycles runs for only a few milliseconds, with no warm-up. So the CPU can run at a different speed in the two programs, and that moves every size of a function by the same factor: the **level**. That is not a fault in either method. What must agree is the **shape**: how the cost changes from 1 byte to 1,536 bytes. PASS means that, after the level, every size is within 10%.

**plots.py** draws the figures into `results\figures`:

| Figure | What it shows |
|---|---|
| fig1_execution_time | cycles per call against message size |
| fig2_short_messages | 1, 8 and 16 bytes: Ascon-PrfShort, Ascon-Mac and the MAC rivals |
| fig3_cycles_per_byte | cycles per byte against message size |
| fig4_throughput | MB/s against message size |
| fig5_heatmap | the six functions timed at all 13 sizes, as times the fastest at each size |
| fig6_noise | how much each measurement varied |
| fig7_mac_speedup | how many times faster Ascon-Mac is than each MAC rival |
| fig8_prf_speedup | how many times faster Ascon-Prf is than the PRF from XOF128 |
| fig9_kdf | new keys: Ascon-Prf against AKDF |
| fig10_code_size | code size at -O3 and -Os |

**Where to look for "how much faster":** `results\comparisons.csv` (the speedup and every_A_run_faster columns), the speed-up lines that `analyze.py` prints, and figures 2, 7, 8 and 9.

**What happens next:** these tables and figures go into the final report.

---

## Step 9: Final report and presentation (in progress)

The final report will present what we measured, how we kept the comparisons fair, and what the results mean for adding Ascon-Mac, Ascon-Prf and Ascon-PrfShort to the standard.

---

## What we expected before timing

Most of the time in Ascon goes into its 12-round permutation. Counting permutation calls in the designers' code gave a first idea of what to expect:

- On long messages, the rivals should need about **4 times** as many permutation calls as Ascon-Mac and Ascon-Prf. The standard functions read 8 bytes of message per call; Ascon-Mac and Ascon-Prf read 32.
- On short messages, the gap should be bigger, because reading the key, padding and labels are fixed costs. For a 16-byte message: Ascon-PrfShort makes 1 call, Ascon-Mac 2, MAC from XOF128 6, MAC from Hash256 8, and AMAC 11.

These are counts, not timings. The measured speed-ups are in `results\comparisons.csv`.

---

## Folder layout

```
Ascon-bench/
├─ ascon-c/                    the designers' code (git submodule, pinned to 446347f, never edited)
├─ src/
│  ├─ check_tsc.c              Step 1: is the cycle counter safe to use?
│  ├─ akdf.c                   Step 4: AKDF on our fast CXOF128
│  └─ bench.c                  Step 6: the benchmarking program
├─ make_variants.py            Step 3: makes the two Ascon versions the designers don't ship
├─ akdf_check.py               Step 4: independent Python version of AKDF
├─ run_all.py                  Step 7: the whole study with one command
├─ analyze.py                  Step 8: statistics and speed-ups
├─ validate_getcycles.py       Step 8: cross-check with the designers' timing tool
├─ plots.py                    Step 8: the figures
├─ docs/
│  ├─ ctest_results.txt        Step 2: our run of the designers' tests (11 of 11 passed)
│  └─ bench_verify_expected.txt  Step 6: the 45 answers the benchmark programs must give
├─ .gitignore
└─ .gitmodules
```

The steps also make these: `build\`, `variants\`, `results_pilot\` and `ascon.py`, which are never committed (they are listed in `.gitignore`), and `results\`, which holds the real results.

---

## Notes and open questions

- **AMAC and AKDF are preliminary.** We follow NIST's planned definitions, which may change.
- **Bits or bytes for L.** In AKDF and AMAC, we count L in bits, as KMAC does. This is still an open question with our problem mentor.
- **One extra permutation for AMAC and AKDF.** Our fast CXOF128 runs its start-up permutation on every call. The designers' Hash256 and XOF128 code stores the result of that step instead. This costs AMAC and AKDF one extra permutation per call, and we will mention it in the final report.
- **What "cycles" means here.** RDTSC ticks at a fixed rate (3.294 GHz on our laptop), while turbo boost changes the core's real speed. So our cycle counts measure time at that fixed rate, not the core's own clock ticks. Every function is timed the same way (same program, same warm-up, same core, shuffled order), so the speed-ups compare like with like.

## Credits

- Ascon was designed by Christoph Dobraunig, Maria Eichlseder, Florian Mendel and Martin Schläffer.
- C code: https://github.com/ascon/ascon-c
- Python code: https://github.com/meichlseder/pyascon
- Standards: NIST SP 800-232 (Ascon-based lightweight cryptography) and NIST SP 800-185 (bytepad and right_encode, from KMAC).
