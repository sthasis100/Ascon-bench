# Ascon-bench

**Performance Benchmarking for Ascon Extensions (v1)**
INSuRE, Fall 2026 · University at Albany (SUNY) · Team 4

Team: Aashish Shrestha, Leela Pavan Kumar Kunapureddy, Simbarashe Mandizvidza, Lakshika Vaishnav
Problem mentor: NIST · Instructor: Dr. Sanjay Goel

---

## What this project is about

NIST standardized Ascon for lightweight cryptography in **NIST SP 800-232**. The standard has four functions: Ascon-AEAD128, Ascon-Hash256, Ascon-XOF128 and Ascon-CXOF128. None of them takes a secret key for making tags or new keys.

New keyed functions are under consideration: the Ascon designers' **Ascon-Mac**, **Ascon-Prf** and **Ascon-PrfShort**, and NIST's planned key-derivation function **AKDF**, which is built on Ascon-CXOF128 (its definition is preliminary, not final). Our job is to benchmark these four functions on an ordinary Windows laptop (AMD Ryzen 7 PRO 7840U): to measure how long each one takes, how that changes with the size of the input, and how much the measurements vary, with a method that can be trusted and repeated.

After discussion with our problem mentor, each function is benchmarked on its own. We do not compare them with other algorithms.

## Where the project stands

| Step | What happens | Status |
|---|---|---|
| 0 | Set up the tools and the project folder | Done |
| 1 | Check that the CPU's cycle counter is safe to time with | Done |
| 2 | Check that the designers' code passes its own tests | Done |
| 3 | Make the fast Ascon-CXOF128 the designers don't ship, and check it | Done: 1,089 of 1,089 answers match |
| 4 | Build AKDF and check it three separate ways | Done |
| 5 | Midterm presentation of steps 0 to 4 and the plan | Done |
| 6 | Write the benchmarking program and check its answers | Done |
| 7 | Run the benchmark | Done |
| 8 | Analyze the results | Done |
| 9 | Final report and presentation | In progress |

## What we benchmark

| Function | What it does | Input | Output | Sizes timed |
|---|---|---|---|---|
| Ascon-Mac | Makes a tag that proves a message was not changed | 16-byte key + message | 16 bytes | 13 message sizes |
| Ascon-Prf | Turns a key and data into random-looking output | 16-byte key + message | 64 bytes | 13 message sizes |
| Ascon-PrfShort | Like Ascon-Prf, for very short messages | 16-byte key + message of at most 16 bytes | 16 bytes | 1, 2, 4, 8 and 16 bytes |
| AKDF (NIST planned) | Makes a new key from a key | 16-byte key + 16 bytes of key data + a 14-byte label | the new key | New keys of 16, 32 and 64 bytes |

- **The 13 message sizes** are 1, 8, 16, 32, 64, 128, 256, 512, 1,024, 1,536, 4,096, 16,384 and 65,536 bytes.
- **For AKDF, the size is the length of the new key** it makes; its input is always the same 30 bytes plus the key.
- Every function gets the same 16-byte key and the same message bytes, every function runs on the designers' fast 64-bit code (opt64), and every function is timed by the same program in the same way.

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
cmake -S ascon-c -B build\cmake -G Ninja -DCMAKE_C_COMPILER=gcc -DCMAKE_BUILD_TYPE=Release -DALG_LIST="asconcxof128;asconmacv13;asconprfv13;asconprfsv13" -DIMPL_LIST="ref;opt64" -DTEST_LIST="genkat"
cmake --build build\cmake
ctest --test-dir build\cmake
```

**What you get:** 7 tests: Ascon-Mac, Ascon-Prf and Ascon-PrfShort, each in two versions, and Ascon-CXOF128 (which AKDF is built on). "ref" is the designers' slow reference code and "opt64" is their fast 64-bit code. Ascon-CXOF128 only comes as ref, which is why there are 7 tests and not 8. All 7 must say `Passed`. Our recorded run, `docs\ctest_results.txt`, was made when the project also used Ascon-Hash256 and Ascon-XOF128, so it lists 11 tests; the 7 above are among them, and all 11 passed.

**What happens next:** We know the designers' code works correctly on our laptop, so the timings are timings of the right work.

---

## Step 3: Make the fast Ascon-CXOF128 the designers don't ship

**Why:** AKDF is built on Ascon-CXOF128, which only comes as slow reference code. Ascon-Mac, Ascon-Prf and Ascon-PrfShort run on the fast opt64 code, so AKDF should too. As suggested by our problem mentor, we copy the opt64 Ascon-XOF128 folder and replace its `hash.c` with CXOF128's `hash.c`, plus one added line so the two sets of names match. The speed comes from the permutation files, which both functions share.

**Run:**

```
python make_variants.py
```

**What you get:** one new folder, `variants\asconcxof128_opt64`: CXOF128 on the fast opt64 code. Never edit it by hand; the script remakes it each time. The script ends by checking that nothing inside `ascon-c` was changed, and prints `ascon-c is untouched (git status is clean)`.

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

**What happens next:** We now have a fast CXOF128 we can trust. AKDF is built on it.

---

## Step 4: Build AKDF and check it three separate ways

**Why:** AKDF is NIST's planned key-derivation function. It has no official answer file yet, so we check it ourselves. NIST's planned definition is:

```
KOUT = CXOF128( bytepad(K, 32) || X || right_encode(L),  L,  "AKDF" || S )
```

K is the key, X is the key data, L is the length of the new key (counted in bits, as in KMAC), and S is a label saying what the new key is for. `bytepad` and `right_encode` come from NIST SP 800-185, the KMAC standard.

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

**What happens next:** The benchmarking program (Step 6) builds the AKDF input in exactly the same way, on the fast CXOF128.

---

## Step 5: Midterm presentation (done)

We presented Steps 0 to 4 and the benchmark plan at the midterm.

---

## Step 6: Write the benchmarking program, and check its answers

**Why:** Every function must be timed in exactly the same way, with the same inputs, so the measurements can be trusted and repeated. So one C program, `src\bench.c`, times all four.

**How it works:**

- **One program, built four times.** `bench.c` is compiled once for each function. Two things choose the function: the switch `-DMODE_...` decides how the function is called, and the Ascon folder given with `-I` decides whose code answers the call. Each function needs its own program because the Ascon folders use the same function names (for example `crypto_auth`), so two of them cannot be built into one program.

| Program | What it times | Mode | Ascon folder |
|---|---|---|---|
| ascon_mac | Ascon-Mac | AUTH | `ascon-c\crypto_auth\asconmacv13\opt64` |
| ascon_prf | Ascon-Prf | AUTH | `ascon-c\crypto_auth\asconprfv13\opt64` |
| ascon_prfshort | Ascon-PrfShort | AUTH | `ascon-c\crypto_auth\asconprfsv13\opt64` |
| akdf | AKDF (NIST planned) | AKDF | `variants\asconcxof128_opt64` |

- **The same inputs every time.** A fixed 16-byte key and 64 KB of message bytes, made by a small number generator from a fixed starting number, so every function on every computer gets the same bytes. For AKDF, X is the first 16 bytes of the message and the label S is "encryption key".
- **Only the call is timed.** Work that is not part of the function (making the test data, building the AKDF input) is done before timing starts.
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

**What you get:** a header line and one line per size, for example `ascon_mac,auth,16,C1CC87D845DB23B90D92D6C834BE2812`. These must match the lines in `docs\bench_verify_expected.txt`, which holds the 18 answers the four programs must give. Each was confirmed a separate way: Ascon-Mac, Ascon-Prf and Ascon-PrfShort against the designers' reference C code (not the fast code we time), and AKDF against the designers' Python Ascon (pyascon). The program also prints `pinned to core 2` on the screen; that line is normal and is not part of the results.

**Check all four at once**, after Step 7 has built them:

```
del build\verify.txt 2>nul
build\bench_ascon_mac.exe ascon_mac 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_ascon_prf.exe ascon_prf 0 1,8,16,64,1024,65536 >> build\verify.txt
build\bench_ascon_prfshort.exe ascon_prfshort 0 1,8,16 >> build\verify.txt
build\bench_akdf.exe akdf 0 16,32,64 >> build\verify.txt
fc build\verify.txt docs\bench_verify_expected.txt
```

`fc` should print `FC: no differences encountered`.

**What happens next:** Every program computes the right answer, so its timings are timings of the right work.

---

## Step 7: Run the benchmark

**Why:** Dozens of commands have to run in the same order, with the same flags, every time. `run_all.py` runs them all, so nothing is typed by hand.

**Before you start:** plug the laptop in, close other programs, wait a few minutes after start-up, and make sure Step 3 has made the `variants` folder.

**Run** a quick trial first, then the real study:

```
python run_all.py --pilot
python run_all.py
```

**What it does, in order.** It stops at once if anything fails.

1. Records the machine (CPU, Windows version, compiler, flags, the ascon-c commit) and checks the cycle counter again. It stops if the counter is not invariant.
2. Builds the four benchmark programs from Step 6, all with `-O3 -march=native`.
3. Checks the answers before anything is timed: the official answer files for Ascon-Mac, Ascon-Prf, Ascon-PrfShort and our fast Ascon-CXOF128 (each built with the designers' own test program and our flags), and 3 answers of AKDF, which has no official answer file yet. If any check fails, nothing is timed.
4. Measures code size: the bytes of machine code of each Ascon implementation we time, at -O3 (the code we time) and -Os (what a small device would use).
5. Times every program at every size, in a shuffled order (always the same order), so the laptop warming up does not always slow down the same function.

| | Pilot (`--pilot`) | Real study |
|---|---|---|
| Repetitions per point | 5 | 30 |
| Message sizes for Ascon-Mac and Ascon-Prf | 1, 16 and 1,536 bytes | the 13 message sizes |
| Message sizes for Ascon-PrfShort | 1 and 16 bytes | 1, 2, 4, 8 and 16 bytes |
| New key lengths for AKDF | 16 and 64 bytes | 16, 32 and 64 bytes |
| Results folder | `results_pilot` | `results` |

The pilot can never overwrite the real results.

**What you get** (in `results`, or `results_pilot` for the pilot):

- `environment.json`: the machine, compiler, flags and settings.
- `kat_results.csv`: the 5 answer checks, each PASS or FAIL.
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

**analyze.py** turns the raw counts into statistics:

- `summary.csv`: for each function and size: the number of runs, mean, median, standard deviation, fastest, slowest, noise (the standard deviation as a % of the mean), cycles per byte, time in ns, and MB/s. The **median cycles per call** (`cycles_median`) is the execution time we report.
- `raw_runs_detailed.csv`: every single measurement with its algorithm, implementation folder, sizes, repetition, cycles, cycles per call and ns per call.
- On the screen: the noise, every point with noise over 5% (worth timing again), and each function's time at its smallest and largest size.

How each metric is calculated:

| Metric | Calculation |
|---|---|
| Cycles per call | cycles for one batch ÷ calls in the batch |
| Execution time | the median of the repetitions' cycles per call |
| Noise | standard deviation ÷ mean × 100 |
| Cycles per byte | execution time ÷ size |
| Time in ns | cycles ÷ the CPU's nominal frequency in GHz |
| MB/s | size ÷ time in ns × 1,000 |

Time in ns and MB/s is converted from cycles with the CPU's nominal frequency (3.294 GHz on our laptop, read from Windows). It is a conversion, not a second clock. `analyze.py` uses only the four functions, so it also works on results from an older run that timed more programs.

**validate_getcycles.py** checks our timing method against the designers' own timing tool, `getcycles` (in `ascon-c\tests`). It builds getcycles with our flags for Ascon-Mac and Ascon-Prf, runs it five times, and compares its median cycles per byte with ours at 1, 8, 16, 32, 64 and 1,536 bytes. It writes `getcycles_validation.csv` and prints PASS or CHECK.

How to read it: both tools count with RDTSC, which ticks at a fixed rate, while turbo boost changes the CPU's real speed. Our program times each size for a long time, after a warm-up batch; getcycles runs for only a few milliseconds, with no warm-up. So the CPU can run at a different speed in the two programs, and that moves every size of a function by the same factor: the **level**. That is not a fault in either method. What must agree is the **shape**: how the cost changes from 1 byte to 1,536 bytes. PASS means that, after the level, every size is within 10%.

**plots.py** draws the figures into `results\figures`. Each timing figure has one panel per function, each with its own scale:

| Figure | What it shows |
|---|---|
| fig1_execution_time | median cycles per call against size, with the fastest-to-slowest range of the repetitions shaded |
| fig2_cycles_per_byte | median cycles per byte against size |
| fig3_throughput | MB/s against size |
| fig4_noise | how much the repetitions varied at each size, against the 5% line |
| fig5_code_size | code size at -O3 and -Os |

**What happens next:** these tables and figures go into the final report.

---

## Step 9: Final report and presentation (in progress)

The final report will present what we measured, how we made sure the measurements can be trusted, and how the cost of each function changes with the size of its input.

---

## What we expected before timing

Most of the time in Ascon goes into its 12-round permutation. Counting permutation calls in the designers' code gave a first idea of what to expect:

- On long messages, Ascon-Mac and Ascon-Prf read 32 bytes of message per permutation call, so their time should grow steadily with the message length, and their cycles per byte should level off.
- On short messages, fixed costs (reading the key, padding, making the output) dominate. For a 16-byte message, Ascon-PrfShort makes 1 permutation call and Ascon-Mac makes 2.

These are counts, not timings. The measured times are in `results\summary.csv`.

---

## Folder layout

```
Ascon-bench/
├─ ascon-c/                    the designers' code (git submodule, pinned to 446347f, never edited)
├─ src/
│  ├─ check_tsc.c              Step 1: is the cycle counter safe to use?
│  ├─ akdf.c                   Step 4: AKDF on our fast CXOF128
│  └─ bench.c                  Step 6: the benchmarking program
├─ make_variants.py            Step 3: makes the fast CXOF128 the designers don't ship
├─ akdf_check.py               Step 4: independent Python version of AKDF
├─ run_all.py                  Step 7: the whole study with one command
├─ analyze.py                  Step 8: statistics
├─ validate_getcycles.py       Step 8: cross-check with the designers' timing tool
├─ plots.py                    Step 8: the figures
├─ docs/
│  ├─ ctest_results.txt        Step 2: our run of the designers' tests
│  └─ bench_verify_expected.txt  Step 6: the 18 answers the benchmark programs must give
├─ .gitignore
└─ .gitmodules
```

The steps also make these: `build\`, `variants\`, `results_pilot\` and `ascon.py`, which are never committed (they are listed in `.gitignore`), and `results\`, which holds the real results.

---

## Notes and open questions

- **AKDF is preliminary.** We follow NIST's planned definition, which may change.
- **Bits or bytes for L.** In AKDF, we count L in bits, as KMAC does. This is still an open question with our problem mentor.
- **One extra permutation for AKDF.** Our fast CXOF128 runs its start-up permutation on every call, where the designers' fast Hash256 and XOF128 code stores the result of that step instead. This costs AKDF one extra permutation per call, and we will mention it in the final report.
- **What "cycles" means here.** RDTSC ticks at a fixed rate (3.294 GHz on our laptop), while turbo boost changes the core's real speed. So our cycle counts measure time at that fixed rate, not the core's own clock ticks. Every function is timed the same way (same program, same warm-up, same core, shuffled order).

## Credits

- Ascon was designed by Christoph Dobraunig, Maria Eichlseder, Florian Mendel and Martin Schläffer.
- C code: https://github.com/ascon/ascon-c
- Python code: https://github.com/meichlseder/pyascon
- Standards: NIST SP 800-232 (Ascon-based lightweight cryptography) and NIST SP 800-185 (bytepad and right_encode, from KMAC).
