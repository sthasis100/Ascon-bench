"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
run_all.py  -  the whole study, in the right order, with one command

WHAT IT DOES
  1. Records the machine, and checks the clock (stops if it is not safe).
  2. Builds every benchmark program with exactly the same compiler flags.
  3. Checks that every program computes the right answer, and stops
     before timing anything if one does not.
  4. Measures code size ("execution size") at -O3 and -Os.
  5. Measures: every program, every size, 30 repetitions, in shuffled
     order. Every single repetition is saved; nothing is averaged here.

WHY ONE SCRIPT
  Dozens of commands, always in the same order with the same flags.
  Typing them by hand every run is where mistakes creep in.

RUN (Command Prompt, in the project folder)
  python run_all.py            the real study       -> results
  python run_all.py --pilot    a quick trial run    -> results_pilot
                               (5 repetitions, 2 or 3 sizes per program;
                                it can never overwrite the real results)

  ONE FUNCTION ONLY: add --only and its name. Every stage then does only
  that function's part, and the results go to their own folder:
  python run_all.py --only ascon_mac            -> results_ascon_mac
  python run_all.py --pilot --only ascon_mac    -> results_pilot_ascon_mac
  The names are ascon_mac, ascon_prf, ascon_prfshort and akdf; several can
  be given with commas, for example --only ascon_mac,akdf
===========================================================================
"""
import csv
import json
import os
import platform
import random
import shutil
import subprocess
import sys

# ------------------------------------------------------------------ settings
PILOT = "--pilot" in sys.argv
if PILOT:
    RESULTS = "results_pilot"
    RUNS = 5                                  # timed repetitions per point
else:
    RESULTS = "results"
    RUNS = 30

BUILD = "build"
A = "ascon-c"                                 # the designers' code
CXOF = "variants/asconcxof128_opt64"          # made by make_variants.py (for AKDF)

# The SAME flags for every benchmark build. Never add -flto: it lets the
# compiler see inside the Ascon code and delete or move the work we time.
CFLAGS = ["-O3", "-march=native"]

# Sizes in bytes. For AKDF: the length of the new key (the output).
if PILOT:
    LONG = [1, 16, 1536]
    SHORT = [1, 16]
    KDF = [16, 64]
else:
    LONG = [1, 8, 16, 32, 64, 128, 256, 512, 1024, 1536, 4096, 16384, 65536]
    SHORT = [1, 2, 4, 8, 16]                  # Ascon-PrfShort takes at most 16
    KDF = [16, 32, 64]

# Core 2 if the CPU has more than 2 cores: core 0 does most of Windows' work.
CORE = 2
if os.cpu_count() is None or os.cpu_count() <= 2:
    CORE = 0

# The 4 benchmark programs: name, mode, Ascon folder, sizes.
TARGETS = [
    ("ascon_mac",      "AUTH", A + "/crypto_auth/asconmacv13/opt64",  LONG),
    ("ascon_prf",      "AUTH", A + "/crypto_auth/asconprfv13/opt64",  LONG),
    ("ascon_prfshort", "AUTH", A + "/crypto_auth/asconprfsv13/opt64", SHORT),
    ("akdf",           "AKDF", CXOF,                                  KDF),
]

# Official answer checks: the program it is for, name, Ascon folder, the
# designers' test program, the official answer file, extra compiler flags.
OFFICIAL = [
    ("ascon_mac", "Ascon-Mac", A + "/crypto_auth/asconmacv13/opt64", "genkat_auth.c",
     A + "/crypto_auth/asconmacv13/LWC_MAC_KAT_128_128.txt", []),
    ("ascon_prf", "Ascon-Prf", A + "/crypto_auth/asconprfv13/opt64", "genkat_auth.c",
     A + "/crypto_auth/asconprfv13/LWC_PRF_KAT_128_512.txt", []),
    # PrfShort refuses messages over 16 bytes, so its test program is told
    # to stop at 16 - exactly as the designers' own CMake build does.
    ("ascon_prfshort", "Ascon-PrfShort", A + "/crypto_auth/asconprfsv13/opt64", "genkat_auth.c",
     A + "/crypto_auth/asconprfsv13/LWC_PRFS_KAT_128_128.txt", ["-DMAX_MESSAGE_LENGTH=16"]),
    # Our fast CXOF128 (for AKDF) against CXOF128's official answers.
    ("akdf", "Ascon-CXOF128 (opt64)", CXOF, "genkat_cxof.c",
     A + "/crypto_cxof/asconcxof128/LWC_CXOF_KAT_128_512.txt", []),
]

# AKDF is new, so NIST has no answer file for it yet. These are the answers
# our program must give, for each new key length. We confirmed every one
# independently, against a separate Python version built on the designers'
# own Python Ascon (pyascon).
OUR_ANSWERS = {
    "akdf": {16: "A6317D6160F7D50B83BCBDD2B3DCA01E",
             32: "D84C9BCE206AFB0A106B1DDC68A31FD46EA41731C9ABFA29BD3D887DE934762F",
             64: "14EDD318D0CF9F7D1B78F82CC72B476C045CC75E5516B2A427C28A3E4B2B69C2"
                 "D6735A467D558AAF8E54D18F0ED15AEE60933FDB26989172994364F7F7E3A211"},
}

# Code size is measured for each Ascon implementation we time: the program
# it is for, name, Ascon folder (AKDF runs on our fast CXOF128).
SIZE_TARGETS = [
    ("ascon_mac", "Ascon-Mac", A + "/crypto_auth/asconmacv13/opt64"),
    ("ascon_prf", "Ascon-Prf", A + "/crypto_auth/asconprfv13/opt64"),
    ("ascon_prfshort", "Ascon-PrfShort", A + "/crypto_auth/asconprfsv13/opt64"),
    ("akdf", "Ascon-CXOF128 (opt64)", CXOF),
]

# --only: benchmark only the functions named (for example --only ascon_mac).
# Every stage then does only their part, and the results get their own folder.
SELECTED = []
for name, mode, folder, sizes in TARGETS:
    SELECTED.append(name)
if "--only" in sys.argv:
    position = sys.argv.index("--only")
    if position + 1 >= len(sys.argv):
        print("--only needs a name: ascon_mac, ascon_prf, ascon_prfshort or akdf")
        sys.exit(1)
    wanted = sys.argv[position + 1].split(",")
    for name in wanted:
        if name not in SELECTED:
            print("unknown name:", name, "- use ascon_mac, ascon_prf, ascon_prfshort or akdf")
            sys.exit(1)
    SELECTED = wanted
    RESULTS = RESULTS + "_" + "_".join(SELECTED)
TARGETS = [t for t in TARGETS if t[0] in SELECTED]
OFFICIAL = [c for c in OFFICIAL if c[0] in SELECTED]
OUR_ANSWERS = {name: OUR_ANSWERS[name] for name in OUR_ANSWERS if name in SELECTED}
SIZE_TARGETS = [s for s in SIZE_TARGETS if s[0] in SELECTED]


# ------------------------------------------------------------------- helpers
def run(command, folder=None):
    """Run one command and return what it printed. If it fails, show its
    error message and stop the whole study."""
    result = subprocess.run(command, capture_output=True, text=True, cwd=folder)
    if result.returncode != 0:
        print("\nFAILED:", " ".join(command))
        print(result.stdout)
        print(result.stderr)
        sys.exit(1)
    return result.stdout


def c_files(folder):
    """The .c files of one Ascon folder."""
    files = []
    for name in sorted(os.listdir(folder)):
        if name.endswith(".c"):
            files.append(folder + "/" + name)
    return files


def empty_folder(path):
    """Make an empty folder for one job's files, and return its full path."""
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path)
    return os.path.abspath(path)


def simple_name(text):
    """Turn a name like 'Ascon-CXOF128 (opt64)' into a folder name:
    every character that is not a letter or a digit becomes '_'."""
    name = ""
    for ch in text:
        if ch.isalnum():
            name = name + ch
        else:
            name = name + "_"
    return name


# ------------------------------------------------ stage 1: machine and clock
def nominal_ghz(brand, cpuid_mhz):
    """The CPU's nominal frequency, used ONLY to turn cycles into nanoseconds
    and MB/s. Three sources are tried; the one that worked is recorded."""
    # 1. CPUID question 0x16 (many Intel CPUs report it)
    if cpuid_mhz > 0:
        return cpuid_mhz / 1000, "CPUID leaf 0x16"
    # 2. the CPU's name, for example "Intel(R) Core(TM) i7-8650U CPU @ 1.90GHz"
    if "@" in brand and brand.endswith("GHz"):
        number = brand.split("@")[1].replace("GHz", "").strip()
        return float(number), "CPU name"
    # 3. the Windows registry (this also works for AMD CPUs)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        mhz = winreg.QueryValueEx(key, "~MHz")[0]
        return mhz / 1000, "Windows registry"
    except (ImportError, OSError):
        return None, "unknown - results in cycles only"


def machine_and_clock():
    print("STAGE 1  the machine and the clock")
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(RESULTS, exist_ok=True)
    tsc = os.path.abspath(BUILD + "/check_tsc.exe")
    run(["gcc", "-O2", "src/check_tsc.c", "-o", tsc])
    # check_tsc.exe exits with 1 when the clock is not safe, so we read its
    # output ourselves instead of using run(), which would stop at once.
    result = subprocess.run([tsc], capture_output=True, text=True)
    info = {}
    for line in result.stdout.splitlines():
        if "=" in line:
            parts = line.split("=", 1)
            info[parts[0]] = parts[1]
    if info.get("invariant_tsc") != "1":
        print("STOP: this CPU's cycle counter is not invariant, so RDTSC - our")
        print("only clock - cannot be trusted. Use another (real) computer.")
        sys.exit(1)
    brand = info.get("brand", "unknown").strip()
    ghz, source = nominal_ghz(brand, int(info.get("cpuid16_base_mhz", "0")))
    env = {
        "cpu": brand,
        "nominal_ghz": ghz,
        "nominal_ghz_source": source,
        "os": platform.system() + " " + platform.release(),
        "compiler": run(["gcc", "--version"]).splitlines()[0],
        "cflags": " ".join(CFLAGS),
        "ascon_commit": run(["git", "-C", A, "rev-parse", "HEAD"]).strip(),
        "functions": ", ".join(SELECTED),
        "runs_per_point": RUNS,
        "pinned_core": CORE,
        "pilot": PILOT,
    }
    with open(RESULTS + "/environment.json", "w") as f:
        json.dump(env, f, indent=2)
    for name in env:
        print("  ", name.ljust(20), env[name])
    print("   the clock is invariant: RDTSC is safe to use")


# ------------------------------------------------- stage 2: build programs
def build_programs():
    print("\nSTAGE 2  building", len(TARGETS), "benchmark program" + ("s" if len(TARGETS) > 1 else "") + ", all with", " ".join(CFLAGS))
    for name, mode, folder, sizes in TARGETS:
        exe = BUILD + "/bench_" + name + ".exe"
        run(["gcc"] + CFLAGS + ["-I" + folder] + c_files(folder)
            + ["-I" + A + "/tests", "-DMODE_" + mode, "src/bench.c", "-o", exe])
        print("   built", name.ljust(15), ("MODE_" + mode).ljust(10), "from", folder)


# ---------------------------------------------------- stage 3: correctness
def same_content(file1, file2):
    """True if two answer files hold the same text. Python reads both as
    text, so the line-ending style does not matter (Windows programs end
    lines with \\r\\n, the official files with \\n)."""
    with open(file1) as f:
        text1 = f.read()
    with open(file2) as f:
        text2 = f.read()
    return text1 == text2


def check_official(name, folder, generator, answers, extra):
    """Build the designers' test program with OUR flags against one Ascon
    folder, run it, and compare its answer file with the official one."""
    work = empty_folder(BUILD + "/kat_" + simple_name(name))
    exe = work + "/genkat.exe"
    run(["gcc"] + CFLAGS + ["-I" + folder] + c_files(folder) + ["-I" + A + "/tests"]
        + extra + [A + "/tests/" + generator, "-o", exe])
    run([exe], folder=work)
    file_name = os.path.basename(answers)
    if same_content(work + "/" + file_name, answers):
        return True, file_name + ": identical"
    return False, file_name + ": DIFFERENT"


def check_our_answers():
    """Run AKDF in verify mode (nothing is timed) and compare every result
    with OUR_ANSWERS above."""
    wrong = []
    count = 0
    for name in OUR_ANSWERS:
        expected = OUR_ANSWERS[name]
        size_list = []
        for size in expected:
            size_list.append(str(size))
        exe = os.path.abspath(BUILD + "/bench_" + name + ".exe")
        output = run([exe, name, "0", ",".join(size_list)])
        got = {}
        for line in output.splitlines()[1:]:           # skip the header line
            parts = line.split(",")
            got[int(parts[2])] = parts[3]
        for size in expected:
            count = count + 1
            if got.get(size) != expected[size]:
                wrong.append(name + " at " + str(size))
    if len(wrong) == 0:
        return True, "all " + str(count) + " answers match"
    return False, "DIFFERENT: " + ", ".join(wrong)


def correctness():
    print("\nSTAGE 3  correctness - nothing is timed unless every check passes")
    checks = []
    for target, name, folder, generator, answers, extra in OFFICIAL:
        ok, detail = check_official(name, folder, generator, answers, extra)
        checks.append((name, ok, detail))
    if len(OUR_ANSWERS) > 0:
        ok, detail = check_our_answers()
        checks.append(("AKDF", ok, detail))

    all_passed = True
    with open(RESULTS + "/kat_results.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["check", "result", "detail"])
        for name, ok, detail in checks:
            if ok:
                word = "PASS"
            else:
                word = "FAIL"
                all_passed = False
            print("  ", word, "", name.ljust(32), detail)
            writer.writerow([name, word, detail])
    if not all_passed:
        print("\nSTOP: a correctness check failed. Nothing has been timed.")
        sys.exit(1)


# ------------------------------------------------------ stage 4: code size
def code_size():
    """Bytes of machine code ("execution size") for each implementation,
    read with 'size', the way the designers' own benchmark script does.
    -O3 is the code we time; -Os is what a small device would use."""
    print("\nSTAGE 4  code size (bytes of machine code)")
    rows = []
    for target, name, folder in SIZE_TARGETS:
        sizes = []
        for option in ["-O3", "-Os"]:
            work = empty_folder(BUILD + "/size_" + simple_name(name) + option)
            objects = []
            for source in c_files(folder):
                obj = work + "/" + os.path.basename(source).replace(".c", ".o")
                run(["gcc", option, "-march=native", "-I" + folder, "-I" + A + "/tests",
                     "-c", source, "-o", obj])
                objects.append(obj)
            run(["ar", "rcs", work + "/lib.a"] + objects)
            output = run(["size", "-t", work + "/lib.a"])
            for line in output.splitlines():
                if "TOTALS" in line:
                    sizes.append(int(line.split()[0]))    # the "text" column
        rows.append([name, sizes[0], sizes[1]])
        print("  ", name.ljust(30), "-O3", str(sizes[0]).rjust(6), "bytes   -Os",
              str(sizes[1]).rjust(6), "bytes")
    with open(RESULTS + "/code_size.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["function", "text_bytes_O3", "text_bytes_Os"])
        writer.writerows(rows)


# -------------------------------------------------------- stage 5: measure
def measure():
    # Shuffled order: a laptop warms up and slows down during a run. In a
    # fixed order the last program would always get the slowest machine.
    # The seed (7) makes the shuffled order the same every time.
    jobs = list(TARGETS)
    random.seed(7)
    random.shuffle(jobs)
    print("\nSTAGE 5  measuring:", RUNS, "repetitions per point, pinned to core", CORE)
    header = None
    rows = []
    for name, mode, folder, sizes in jobs:
        size_list = []
        for size in sizes:
            size_list.append(str(size))
        exe = os.path.abspath(BUILD + "/bench_" + name + ".exe")
        result = subprocess.run([exe, name, str(RUNS), ",".join(size_list), str(CORE)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            print("\nFAILED:", name)
            print(result.stderr)
            sys.exit(1)
        lines = result.stdout.strip().splitlines()
        header = lines[0].split(",")
        for line in lines[1:]:
            rows.append(line.split(","))
        print("  ", name.ljust(15), str(len(lines) - 1).rjust(4), "rows  ", result.stderr.strip())
    with open(RESULTS + "/raw_runs.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print("\nwrote", len(rows), "measurements to", RESULTS + "/raw_runs.csv")


if __name__ == "__main__":
    if "akdf" in SELECTED and not os.path.isdir(CXOF):
        print(CXOF, "is missing. Run  python make_variants.py  first.")
        sys.exit(1)
    if PILOT:
        print("*** PILOT RUN: 5 repetitions, 2 or 3 sizes per program, saved in " + RESULTS + " ***\n")
    if len(SELECTED) < 4:
        print("*** ONLY:", ", ".join(SELECTED), "- saved in " + RESULTS + " ***\n")
    machine_and_clock()
    build_programs()
    correctness()
    code_size()
    measure()
