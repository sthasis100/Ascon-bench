/* =========================================================================
 * OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
 * for the project "Performance Benchmarking for Ascon Extensions (v1)".
 * This file is NOT part of the Ascon designers' repository (ascon-c).
 * -------------------------------------------------------------------------
 * akdf.c  -  AKDF, NIST's planned key-derivation function, built on CXOF128
 *
 * WHAT IT IS
 *   Kerry McKay's slides define AKDF as
 *       KOUT = CXOF128( bytepad(K, 32) || X || right_encode(L),  L,  "AKDF" || S )
 *     K   the key
 *     X   secret key data
 *     L   the length of the key to derive (counted in bits, as in KMAC)
 *     S   a label: what the derived key is for
 *   bytepad and right_encode come from NIST SP 800-185 (the KMAC standard).
 *   CXOF128 itself is the designers' code. We build AKDF on our fast (opt64)
 *   CXOF128, which make_variants.py made in variants\asconcxof128_opt64.
 *
 * WHAT IT PRINTS
 *   AKDF for one example (K = 00 01 .. 0F, X = 10 11 .. 1F,
 *   S = "encryption key"), for 16-, 32- and 64-byte derived keys, in hex.
 *   Nothing is timed.
 *
 * BUILD AND RUN (Command Prompt, in the project folder)
 *   set "V=variants\asconcxof128_opt64"
 *   gcc -O2 -Wall -Wextra -I%V% %V%\hash.c %V%\permutations.c %V%\printstate.c -Iascon-c\tests src\akdf.c -o build\akdf.exe
 *   build\akdf.exe
 * ========================================================================= */
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "crypto_cxof.h"   /* the designers' CXOF128: crypto_cxof() */

#define MAX_KEY 32         /* the slides allow keys of up to 256 bits */
#define MAX_X 64           /* enough key data for our examples        */
#define MAX_S 64           /* enough label for our examples           */

/* How many bytes does it take to write x? (always at least 1) */
static int byte_count(uint64_t x) {
  int n = 1;
  while (n < 8 && (x >> (8 * n)) != 0) {
    n++;
  }
  return n;
}

/* left_encode (SP 800-185): the byte count, then x, highest byte first.
   Returns how many bytes it wrote. Example: left_encode(32) = 01 20 */
static int left_encode(uint8_t* dest, uint64_t x) {
  int n = byte_count(x);
  int i;
  dest[0] = (uint8_t)n;
  for (i = 0; i < n; i++) {
    dest[1 + i] = (uint8_t)(x >> (8 * (n - 1 - i)));
  }
  return n + 1;
}

/* right_encode (SP 800-185): x, highest byte first, then the byte count.
   Returns how many bytes it wrote. Example: right_encode(128) = 80 01 */
static int right_encode(uint8_t* dest, uint64_t x) {
  int n = byte_count(x);
  int i;
  for (i = 0; i < n; i++) {
    dest[i] = (uint8_t)(x >> (8 * (n - 1 - i)));
  }
  dest[n] = (uint8_t)n;
  return n + 1;
}

/* AKDF: derive out_len bytes into out. Returns 0 on success. */
static int akdf(uint8_t* out, unsigned long long out_len,
                const uint8_t* K, int K_len,
                const uint8_t* X, int X_len,
                const char* S) {
  uint8_t input[32 + MAX_KEY + MAX_X + 9];   /* bytepad(K, 32) || X || right_encode(L) */
  uint8_t custom[4 + MAX_S];                 /* "AKDF" || S                         */
  unsigned long long n = 0;
  int S_len = (int)strlen(S);

  if (K_len > MAX_KEY || X_len > MAX_X || S_len > MAX_S) {
    return -1;
  }

  /* 1. bytepad(K, 32): left_encode(32), then K, then zeros up to 32 bytes */
  n += left_encode(input, 32);
  memcpy(input + n, K, K_len);
  n += K_len;
  while (n % 32 != 0) {
    input[n] = 0;
    n++;
  }

  /* 2. X, the key data */
  memcpy(input + n, X, X_len);
  n += X_len;

  /* 3. right_encode(L), with L counted in bits */
  n += right_encode(input + n, out_len * 8);

  /* 4. the customization string: "AKDF" followed by the label S */
  memcpy(custom, "AKDF", 4);
  memcpy(custom + 4, S, S_len);

  /* 5. CXOF128 does the rest: the designers' code, in the fast build made by
      make_variants.py (or the reference build, if the gcc command says so) */
  return crypto_cxof(out, out_len, input, n, custom, 4 + S_len);
}

int main(void) {
  uint8_t K[16], X[16], out[64];
  const char* S = "encryption key";
  unsigned long long lengths[3] = {16, 32, 64};
  int i, j;

  /* The example: K = 00 01 .. 0F and X = 10 11 .. 1F */
  for (i = 0; i < 16; i++) {
    K[i] = (uint8_t)i;
    X[i] = (uint8_t)(0x10 + i);
  }

  printf("AKDF with K = 00..0F, X = 10..1F, S = \"%s\"\n", S);
  for (i = 0; i < 3; i++) {
    if (akdf(out, lengths[i], K, 16, X, 16, S) != 0) {
      printf("ERROR: AKDF failed\n");
      return 1;
    }
    printf("L = %3llu bits (%2llu bytes): ", lengths[i] * 8, lengths[i]);
    for (j = 0; j < (int)lengths[i]; j++) printf("%02X", out[j]);
    printf("\n");
  }
  return 0;
}