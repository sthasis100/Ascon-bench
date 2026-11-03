
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <inttypes.h>
#include <windows.h>
#include <x86intrin.h>

#include "api.h"
#include "crypto_auth.h"

#define MAX_LEN 65536
#define SAMPLES 30
#define SESSIONS 3
#define WARMUP 100

static unsigned char message[MAX_LEN];
static unsigned char key[CRYPTO_KEYBYTES];
static unsigned char tag[CRYPTO_BYTES];

static volatile uint64_t checksum = 0;

static uint64_t read_ticks(void) {
    _mm_lfence();
    uint64_t t = __rdtsc();
    _mm_lfence();
    return t;
}

static int batch_count(size_t len) {
    if (len <= 64) return 512;
    if (len <= 1024) return 128;
    if (len <= 16384) return 16;
    return 4;
}

static int run_batch(size_t len, int calls) {
    for (int i = 0; i < calls; i++) {
        int result = crypto_auth(tag, message, len, key);
        if (result != 0) return -1;
        checksum += tag[i % CRYPTO_BYTES];
    }
    return 0;
}

static uint64_t timer_overhead(void) {
    uint64_t best = UINT64_MAX;

    for (int i = 0; i < 1000; i++) {
        uint64_t a = read_ticks();
        uint64_t b = read_ticks();

        if (b >= a && b - a < best)
            best = b - a;
    }

    return best;
}

int main(void) {
    const size_t sizes[] = {
        1, 8, 16, 32, 64, 128,
        256, 512, 1024, 4096,
        16384, 65536
    };

    const size_t count = sizeof(sizes) / sizeof(sizes[0]);

    DWORD_PTR old_mask = SetThreadAffinityMask(
        GetCurrentThread(), (DWORD_PTR)1
    );

    if (!old_mask) {
        fprintf(stderr, "ERROR: Cannot set CPU affinity\n");
        return 1;
    }

    SetThreadPriority(
        GetCurrentThread(),
        THREAD_PRIORITY_ABOVE_NORMAL
    );

    for (size_t i = 0; i < MAX_LEN; i++)
        message[i] = (unsigned char)(i & 255);

    for (size_t i = 0; i < CRYPTO_KEYBYTES; i++)
        key[i] = (unsigned char)i;

    uint64_t overhead = timer_overhead();

    fprintf(stderr,
        "Ascon-Mac V3: sessions=%d samples=%d sizes=%zu\n",
        SESSIONS, SAMPLES, count
    );

    fprintf(stderr,
        "Estimated timer overhead: %" PRIu64 " TSC ticks\n",
        overhead
    );

    printf(
        "algorithm,implementation,session,input_bytes,"
        "sample,batch_calls,total_tsc_ticks,"
        "timer_overhead_ticks,net_tsc_ticks_per_call\n"
    );

    for (int session = 1; session <= SESSIONS; session++) {

        fprintf(stderr, "Session %d/%d\n", session, SESSIONS);

        for (size_t n = 0; n < count; n++) {
            size_t len = sizes[n];
            int calls = batch_count(len);

            for (int w = 0; w < WARMUP; w++) {
                if (crypto_auth(tag, message, len, key) != 0)
                    return 1;
            }

            for (int sample = 1; sample <= SAMPLES; sample++) {

                uint64_t start = read_ticks();

                int result = run_batch(len, calls);

                uint64_t end = read_ticks();

                if (result != 0 || end < start) {
                    fprintf(stderr, "Benchmark failure\n");
                    return 1;
                }

                uint64_t total = end - start;

                uint64_t adjusted =
                    total > overhead ? total - overhead : 0;

                double per_call =
                    (double)adjusted / (double)calls;

                printf(
                    "Ascon-Mac,opt64,%d,%zu,%d,%d,"
                    "%" PRIu64 ",%" PRIu64 ",%.3f\n",
                    session,
                    len,
                    sample,
                    calls,
                    total,
                    overhead,
                    per_call
                );
            }
        }
    }

    fprintf(stderr,
        "Completed: %zu samples; checksum=%" PRIu64 "\n",
        count * SAMPLES * SESSIONS, checksum
    );

    SetThreadAffinityMask(GetCurrentThread(), old_mask);

    return 0;
}
