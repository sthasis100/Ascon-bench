/* =========================================================================
 * OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
 * for the project "Performance Benchmarking for Ascon Extensions (v1)".
 * This file is NOT part of the Ascon designers' repository (ascon-c).
 * -------------------------------------------------------------------------
 * bench.c  -  the measurement program
 *
 * WHAT IT DOES
 *   Calls one Ascon function many times, reads the CPU's cycle counter
 *   before and after, and prints one CSV line for every repetition. It
 *   never averages anything: the analysis script does that later.
 *
 * WHY ONE PROGRAM FOR EVERY FUNCTION
 *   A comparison is only fair if both sides are timed in exactly the same
 *   way, with the same input bytes. So this one program times every
 *   function. You choose the function when you compile it:
 *     -I<folder>   which Ascon code is used
 *     -DMODE_...   how it is called (one of the five modes below)
 *
 * THE FIVE MODES
 *   MODE_AUTH        Ascon-Mac, Ascon-Prf or Ascon-PrfShort (proposed)
 *   MODE_KEYED_HASH  Hash256 or XOF128 of key || message (a MAC or PRF)
 *   MODE_AMAC        AMAC, NIST's planned MAC, built on CXOF128
 *   MODE_AKDF        AKDF, NIST's planned KDF, built on CXOF128
 *   MODE_PRF_KDF     Ascon-Prf given exactly the same inputs as AKDF
 *
 * HOW TO RUN IT (Command Prompt)
 *   build\bench_<name>.exe <label> <runs> <sizes> [core]
 *     label  a name for the CSV lines, for example ascon_mac
 *     runs   timed repetitions per size, for example 30.
 *            0 = VERIFY MODE: nothing is timed, and each result is
 *            printed in hex so that it can be checked.
 *     sizes  comma-separated, for example 1,16,64: the message length in
 *            bytes (for MODE_AKDF and MODE_PRF_KDF: the output length)
 *     core   the CPU core to run on (default 2)
 *
 * OUTPUT, one line per repetition:
 *   target,mode,key_bytes,msg_bytes,out_bytes,run,reps,cycles
 * ========================================================================= */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>    /* to keep the program on one CPU core     */
#include <x86intrin.h>  /* __rdtsc(): read the CPU's cycle counter */

/* ---- SIZES, INPUTS AND BUFFERS -------------------------------------------
   Our names start with BENCH_ or are unusual on purpose: windows.h defines
   many short names (KDF_LABEL there is the number 13), and a clash would
   silently change this program. */
#define KEY_LEN 16                    /* every keyed function: a 16-byte key */
#define MAX_MSG 65536                 /* the longest message: 64 KB          */
#define MAX_OUT 64                    /* the longest output: 64 bytes        */
#define X_LEN 16                      /* AKDF's key data X: 16 bytes         */
#define BENCH_LABEL "encryption key"  /* the label S: 14 bytes               */
#define BENCH_LABEL_LEN 14

static uint8_t key[KEY_LEN];          /* the key                              */
static uint8_t msg[MAX_MSG];          /* the message (its first 16 bytes = X) */
static uint8_t out[MAX_OUT];          /* the result                           */

/* Each mode's prepare() fills in these two, for the CSV line. */
static unsigned long long in_len;     /* input bytes  */
static int out_len;                   /* output bytes */

#if defined(MODE_AMAC) || defined(MODE_AKDF)
/* ---- THE INPUT FORMAT OF AMAC AND AKDF -----------------------------------
   NIST's planned AMAC and AKDF are both defined as
       CXOF128( bytepad(K, 32) || X || right_encode(L),  L,  label )
   using two encodings from NIST SP 800-185 (the KMAC standard):
     left_encode(x)   the number of bytes in x, then x (highest byte first)
     right_encode(x)  x (highest byte first), then the number of bytes in x
     bytepad(K, 32)   left_encode(32), then K, then zero bytes until the
                      length is a multiple of 32
   L is counted in bits, as in KMAC.
   Examples: left_encode(32) = 01 20, and right_encode(128) = 80 01. */
#include "crypto_cxof.h"

static uint8_t fmt[32 + MAX_MSG + 9];  /* the formatted input          */
static unsigned long long fmt_len;     /* how many bytes of fmt[] used */

/* How many bytes does it take to write x? (always at least 1) */
static int byte_count(uint64_t x) {
  int n = 1;
  while (n < 8 && (x >> (8 * n)) != 0) {
    n++;
  }
  return n;
}

/* left_encode: the byte count, then x. Returns how many bytes it wrote. */
static int left_encode(uint8_t* dest, uint64_t x) {
  int n = byte_count(x);
  int i;
  dest[0] = (uint8_t)n;
  for (i = 0; i < n; i++) {
    dest[1 + i] = (uint8_t)(x >> (8 * (n - 1 - i)));
  }
  return n + 1;
}

/* right_encode: x, then the byte count. Returns how many bytes it wrote. */
static int right_encode(uint8_t* dest, uint64_t x) {
  int n = byte_count(x);
  int i;
  for (i = 0; i < n; i++) {
    dest[i] = (uint8_t)(x >> (8 * (n - 1 - i)));
  }
  dest[n] = (uint8_t)n;
  return n + 1;
}

/* Build  bytepad(key, 32) || x || right_encode(L)  in fmt[]. */
static void format_input(const uint8_t* x, unsigned long long x_len,
                         uint64_t L_bits) {
  unsigned long long n = 0;
  n += left_encode(fmt, 32);            /* left_encode(32)          */
  memcpy(fmt + n, key, KEY_LEN);        /* the key K                */
  n += KEY_LEN;
  while (n % 32 != 0) {                 /* zeros up to 32 bytes     */
    fmt[n] = 0;
    n++;
  }
  memcpy(fmt + n, x, x_len);            /* X                        */
  n += x_len;
  n += right_encode(fmt + n, L_bits);   /* right_encode(L)          */
  fmt_len = n;
}
#endif

/* ===================== THE MODES ==========================================
   Each mode sets three names:
     MODE_NAME    the text written into the CSV
     KEY_BYTES    the key length, for the CSV
     SIZE_LIMIT   the largest size the mode accepts
   and has two functions:
     prepare(size)   work done once per size, BEFORE timing starts; it
                     also sets in_len and out_len for the CSV
     one_call(size)  THE call to Ascon: the only thing that is timed
   ========================================================================= */

#if defined(MODE_AUTH)
/* The designers' Ascon-Mac, Ascon-Prf or Ascon-PrfShort. The api.h of the
   folder compiled in sets the output length (CRYPTO_BYTES). */
#include "api.h"
#include "crypto_auth.h"
#define MODE_NAME "auth"
#define KEY_BYTES KEY_LEN
#define SIZE_LIMIT MAX_MSG
static void prepare(unsigned long long size) {
  in_len = size;
  out_len = CRYPTO_BYTES;
}
static int one_call(unsigned long long size) {
  return crypto_auth(out, msg, size, key);
}

#elif defined(MODE_KEYED_HASH)
/* A MAC or PRF made from Hash256 or XOF128: hash the key followed by the
   message. The hash has no key input, so the key goes in as data.
   key || message is built before timing. */
#include "api.h"
#include "crypto_hash.h"
#define MODE_NAME "keyed_hash"
#define KEY_BYTES KEY_LEN
#define SIZE_LIMIT MAX_MSG
static uint8_t keyed[KEY_LEN + MAX_MSG];      /* the key, then the message */
static void prepare(unsigned long long size) {
  memcpy(keyed, key, KEY_LEN);
  memcpy(keyed + KEY_LEN, msg, size);
  in_len = size;
  out_len = CRYPTO_BYTES;
}
static int one_call(unsigned long long size) {
  return crypto_hash(out, keyed, KEY_LEN + size);
}

#elif defined(MODE_AMAC)
/* AMAC, NIST's planned MAC:
     CXOF128( bytepad(K,32) || X || right_encode(L),  L,  "AMAC" || S )
   K = our key, X = the message, L = 128 bits (a 16-byte tag, like
   Ascon-Mac), S = empty. The input is formatted before timing. */
#define MODE_NAME "amac"
#define KEY_BYTES KEY_LEN
#define SIZE_LIMIT MAX_MSG
static void prepare(unsigned long long size) {
  format_input(msg, size, 16 * 8);
  in_len = size;
  out_len = 16;
}
static int one_call(unsigned long long size) {
  (void)size;  /* not needed here: the message is already inside fmt[] */
  return crypto_cxof(out, 16, fmt, fmt_len, (const unsigned char*)"AMAC", 4);
}

#elif defined(MODE_AKDF)
/* AKDF, NIST's planned KDF:
     CXOF128( bytepad(K,32) || X || right_encode(L),  L,  "AKDF" || S )
   K = our key, X = 16 bytes of key data, S = "encryption key", and
   L = the size asked for: the length of the derived key. */
#define MODE_NAME "akdf"
#define KEY_BYTES KEY_LEN
#define SIZE_LIMIT MAX_OUT
static void prepare(unsigned long long size) {
  format_input(msg, X_LEN, size * 8);
  in_len = X_LEN + BENCH_LABEL_LEN;
  out_len = (int)size;
}
static int one_call(unsigned long long size) {
  /* the customization string is "AKDF" followed by the label (18 bytes) */
  return crypto_cxof(out, size, fmt, fmt_len,
                     (const unsigned char*)("AKDF" BENCH_LABEL),
                     4 + BENCH_LABEL_LEN);
}

#elif defined(MODE_PRF_KDF)
/* Ascon-Prf given exactly AKDF's inputs: the same key K in its key slot,
   X followed by the label S as its message, and the same output length.
   crypto_prf() is the designers' function (their crypto_auth() calls it).
   No header declares it, so we declare it here, exactly as in their prf.c. */
int crypto_prf(unsigned char* out, unsigned long long outlen,
               const unsigned char* in, unsigned long long inlen,
               const unsigned char* k);
#define MODE_NAME "prf_kdf"
#define KEY_BYTES KEY_LEN
#define SIZE_LIMIT MAX_OUT
static uint8_t x_label[X_LEN + BENCH_LABEL_LEN];     /* X || S, 30 bytes */
static void prepare(unsigned long long size) {
  memcpy(x_label, msg, X_LEN);
  memcpy(x_label + X_LEN, BENCH_LABEL, BENCH_LABEL_LEN);
  in_len = X_LEN + BENCH_LABEL_LEN;
  out_len = (int)size;
}
static int one_call(unsigned long long size) {
  return crypto_prf(out, size, x_label, X_LEN + BENCH_LABEL_LEN, key);
}

#else
#error "Compile with one of: -DMODE_AUTH -DMODE_KEYED_HASH -DMODE_AMAC -DMODE_AKDF -DMODE_PRF_KDF"
#endif

/* ---- THE CLOCK ------------------------------------------------------------
   __rdtsc() reads the CPU's cycle counter in one instruction. This is the
   same method as the designers' own timing tool (tests/cpucycles.h). */
/* V2 timing experiment:
   Compile with -DBENCH_V2_FENCED for LFENCE-ordered timestamps.
   Without that flag, preserve the original V1 timing method. */
static uint64_t read_cycles(void) {
#ifdef BENCH_V2_FENCED
  _mm_lfence();
  uint64_t timestamp = __rdtsc();
  _mm_lfence();
  return timestamp;
#else
  return __rdtsc();
#endif
}

/* ---- CORE PINNING ---------------------------------------------------------
   Keep the program on one CPU core, at high priority, so that Windows does
   not move it or interrupt it in the middle of a measurement.
   Returns 1 if it worked, 0 if not. */
static int pin_to_core(int core) {
  if (SetThreadAffinityMask(GetCurrentThread(), (DWORD_PTR)1 << core) == 0) {
    return 0;
  }
  SetPriorityClass(GetCurrentProcess(), HIGH_PRIORITY_CLASS);
  return 1;
}

/* ---- TEST DATA ------------------------------------------------------------
   A tiny random-number generator (xorshift64) that always starts from the
   same number (the seed): every computer gets the same bytes, and every
   function gets the same input. Only test data, never for security. */
static uint64_t rng_state;
static uint8_t rng_byte(void) {
  rng_state ^= rng_state << 13;
  rng_state ^= rng_state >> 7;
  rng_state ^= rng_state << 17;
  return (uint8_t)(rng_state >> 24);
}

/* ---- STOP THE COMPILER CHEATING -------------------------------------------
   We never use the results, so the compiler could delete the calls and we
   would time an empty loop. Mixing one output byte into a "volatile"
   variable forbids that. */
static volatile uint8_t sink = 0;

/* ---- HOW MANY CALLS PER TIMED BATCH ----------------------------------------
   One call is too short to time on its own, so we time a batch of calls
   and divide. About 256 KB of work per batch, and never fewer than 32. */
static unsigned long long reps_for(unsigned long long size) {
  unsigned long long reps = 262144 / size;
  if (reps < 32) {
    reps = 32;
  }
  return reps;
}

/* ---- ONE TIMED BATCH --------------------------------------------------------
   Read the clock, make `reps` calls, read the clock again. Returns non-zero
   if any call failed, so a failed call is never reported as a time. */
static int measure(unsigned long long size, unsigned long long reps,
                   uint64_t* cycles) {
  unsigned long long i;
  int rc = 0;
  uint64_t c0 = read_cycles();
  for (i = 0; i < reps; i++) {
    rc |= one_call(size);
    sink ^= out[0];
  }
  *cycles = read_cycles() - c0;
  return rc;
}

int main(int argc, char* argv[]) {
  const char* label = "unknown";
  int runs = 30;
  char sizes[256] = "16";
  int core = 2;
  char* tok;
  int i;

  /* 0. Read the arguments. */
  if (argc > 1) label = argv[1];
  if (argc > 2) runs = atoi(argv[2]);
  if (argc > 3) {
    strncpy(sizes, argv[3], sizeof(sizes) - 1);
    sizes[sizeof(sizes) - 1] = '\0';
  }
  if (argc > 4) core = atoi(argv[4]);

  /* 1. Pin to one core, or say clearly that it did not work. */
  if (pin_to_core(core)) {
    fprintf(stderr, "pinned to core %d\n", core);
  } else {
    fprintf(stderr, "WARNING: could not pin to core %d - running unpinned\n",
            core);
  }

  /* 2. Make ALL the test data once, before any timing starts. */
  rng_state = 20260901ULL;
  for (i = 0; i < KEY_LEN; i++) key[i] = rng_byte();
  for (i = 0; i < MAX_MSG; i++) msg[i] = rng_byte();

  /* 3. VERIFY MODE (runs = 0): one call per size, result printed in hex.
        Nothing is timed. This proves that the program computes the right
        answer before we trust its timings. */
  if (runs == 0) {
    printf("target,mode,size,output_hex\n");
    tok = strtok(sizes, ",");
    while (tok != NULL) {
      unsigned long long size = strtoull(tok, NULL, 10);
      if (size >= 1 && size <= SIZE_LIMIT) {
        prepare(size);
        if (one_call(size) != 0) {
          fprintf(stderr, "ERROR: %s refused size %llu\n", label, size);
          return 1;
        }
        printf("%s,%s,%llu,", label, MODE_NAME, size);
        for (i = 0; i < out_len; i++) printf("%02X", out[i]);
        printf("\n");
      }
      tok = strtok(NULL, ",");
    }
    return 0;
  }

  /* 4. MEASURE: for each size, one warm-up batch that is thrown away, then
        `runs` timed batches, each printed as one CSV line. */
  printf("target,mode,key_bytes,msg_bytes,out_bytes,run,reps,cycles\n");
  tok = strtok(sizes, ",");
  while (tok != NULL) {
    unsigned long long size = strtoull(tok, NULL, 10);
    unsigned long long reps;
    uint64_t cycles;
    int run;

    if (size < 1 || size > SIZE_LIMIT) {
      fprintf(stderr, "WARNING: size %llu is not allowed here - skipped\n",
              size);
    } else {
      prepare(size);                    /* input preparation, not timed */
      reps = reps_for(size);

      /* The warm-up: the first calls run with cold caches. A function that
         refuses this size (Ascon-PrfShort over 16 bytes) stops the program
         here, so a failure is never timed. */
      if (measure(size, reps, &cycles) != 0) {
        fprintf(stderr, "ERROR: %s refused size %llu (not supported)\n",
                label, size);
        return 1;
      }
      for (run = 0; run < runs; run++) {
        if (measure(size, reps, &cycles) != 0) {
          fprintf(stderr, "ERROR: %s failed at size %llu\n", label, size);
          return 1;
        }
        printf("%s,%s,%d,%llu,%d,%d,%llu,%llu\n", label, MODE_NAME, KEY_BYTES,
               in_len, out_len, run, reps, (unsigned long long)cycles);
      }
    }
    tok = strtok(NULL, ",");
  }
  return 0;
}
