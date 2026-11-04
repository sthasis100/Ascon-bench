"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
This file is NOT part of the Ascon designers' repository (ascon-c).
---------------------------------------------------------------------------
make_variants.py  -  make the two Ascon folders the designers do not ship

WHY
  1. Ascon-CXOF128 only comes as slow reference code ("ref"). Everything
     else we time is the fast "opt64" code, so timing CXOF128 as it is would
     not be fair. Our NIST mentor, Kerry McKay, showed the fix: copy the
     opt64 XOF128 folder and replace its hash.c with CXOF128's hash.c. The
     speed comes from the permutation files, which both functions share;
     hash.c only decides the order in which the data goes in.
  2. For a fair MAC baseline we need XOF128 to give 16 bytes, like
     Ascon-Mac. XOF128 may give any length, so we change one number.

WHAT IT MAKES (outside ascon-c, which is never changed)
  variants/asconcxof128_opt64   CXOF128 on the opt64 code
  variants/asconxof128_out16    XOF128 that gives 16 bytes
  (Python accepts / in Windows paths, so this file uses / everywhere.)

RUN (Command Prompt, in the project folder)
  python make_variants.py
===========================================================================
"""
import shutil
import subprocess
import sys

XOF_FOLDER = "ascon-c/crypto_hash/asconxof128/opt64"
CXOF_HASH_C = "ascon-c/crypto_cxof/asconcxof128/ref/hash.c"
CXOF_OUT = "variants/asconcxof128_opt64"
XOF16_OUT = "variants/asconxof128_out16"


def copy_folder(source, target):
    """Copy a folder of the designers' code. Any older copy is deleted
    first, so a copy is never half old and half new."""
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target)


def change_text(path, old, new):
    """Replace one exact piece of text in a COPIED file. Stop if the text is
    not there, so a change in the designers' code is noticed at once."""
    with open(path) as f:
        text = f.read()
    if old not in text:
        print("STOP:", path, "does not contain:", old)
        sys.exit(1)
    text = text.replace(old, new, 1)
    with open(path, "w") as f:
        f.write(text)


# 1. CXOF128 on the opt64 code: Kerry's recipe.
copy_folder(XOF_FOLDER, CXOF_OUT)
shutil.copy(CXOF_HASH_C, CXOF_OUT + "/hash.c")
# The one small fix: CXOF128's hash.c calls the 12-round permutation
# P12(s), but the opt64 files call it P(s, 12). One added line joins them.
change_text(CXOF_OUT + "/hash.c", '#include "word.h"\n',
            '#include "word.h"\n#define P12(s) P(s, 12) /* added: the opt64 name */\n')
print("made", CXOF_OUT, "  (opt64 XOF128 files + CXOF128's hash.c + 1 line)")

# 2. XOF128 that gives 16 bytes instead of 64.
copy_folder(XOF_FOLDER, XOF16_OUT)
change_text(XOF16_OUT + "/api.h", "#define CRYPTO_BYTES 64", "#define CRYPTO_BYTES 16")
print("made", XOF16_OUT, "   (CRYPTO_BYTES 64 -> 16)")

# 3. Prove that the designers' folder was not changed: git lists every
#    changed file, so the list must be empty.
result = subprocess.run(["git", "-C", "ascon-c", "status", "--short"],
                        capture_output=True, text=True)
if result.stdout.strip() != "":
    print("STOP: ascon-c has been changed:")
    print(result.stdout)
    sys.exit(1)
print("ascon-c is untouched (git status is clean)")
