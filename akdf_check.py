"""
===========================================================================
OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
for the project "Performance Benchmarking for Ascon Extensions (v1)".
---------------------------------------------------------------------------
akdf_check.py  -  an independent second version of AKDF, to check akdf.c

WHY
  AKDF has no official answer file yet. So we compute it a second, separate
  way: in Python, on top of the designers' own Python Ascon (pyascon, the
  file ascon.py), with bytepad and right_encode written again from NIST
  SP 800-185. It prints the same example as akdf.c, in the same format.
  If the two print identical keys, our C version is correct.

RUN (Command Prompt, in the project folder), after downloading ascon.py:
  python akdf_check.py
===========================================================================
"""
import ascon     # the designers' Python Ascon (pyascon), pinned version


def left_encode(x):
    """SP 800-185: the number of bytes of x, then x (highest byte first)."""
    n = max(1, (x.bit_length() + 7) // 8)
    return bytes([n]) + x.to_bytes(n, "big")


def right_encode(x):
    """SP 800-185: x (highest byte first), then the number of its bytes."""
    n = max(1, (x.bit_length() + 7) // 8)
    return x.to_bytes(n, "big") + bytes([n])


def bytepad(data, w):
    """SP 800-185: left_encode(w), then data, then zeros up to a multiple of w."""
    z = left_encode(w) + data
    while len(z) % w != 0:
        z = z + b"\x00"
    return z


def akdf(K, X, out_len, S):
    """Kerry's AKDF: CXOF128(bytepad(K, 32) || X || right_encode(L), L, "AKDF" || S).
    L is counted in bits, as in KMAC."""
    message = bytepad(K, 32) + X + right_encode(out_len * 8)
    return ascon.ascon_hash(message, variant="Ascon-CXOF128", hashlength=out_len,
                            customization=b"AKDF" + S)


K = bytes(range(0x00, 0x10))     # 00 01 ... 0F
X = bytes(range(0x10, 0x20))     # 10 11 ... 1F
S = b"encryption key"
print('AKDF with K = 00..0F, X = 10..1F, S = "encryption key"')
for out_len in [16, 32, 64]:
    print(f"L = {out_len * 8:3} bits ({out_len:2} bytes): {akdf(K, X, out_len, S).hex().upper()}")