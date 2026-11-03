#include <stdio.h>
#include <stdint.h>
#include <inttypes.h>
#include <string.h>
#include <windows.h>
#include <x86intrin.h>

#define SAMPLES 30
#define SESSIONS 3
#define WARMUP 100
#define BATCH 512
#define TAG_BYTES 16
#define KEY_BYTES 16

typedef int (*auth_fn)(unsigned char *,
                       const unsigned char *,
                       unsigned long long,
                       const unsigned char *);

typedef int (*verify_fn)(const unsigned char *,
                         const unsigned char *,
                         unsigned long long,
                         const unsigned char *);

extern int ascon_mac_auth(unsigned char *,
                          const unsigned char *,
                          unsigned long long,
                          const unsigned char *);
extern int ascon_mac_verify(const unsigned char *,
                            const unsigned char *,
                            unsigned long long,
                            const unsigned char *);
extern int ascon_prfs_auth(unsigned char *,
                           const unsigned char *,
                           unsigned long long,
                           const unsigned char *);
extern int ascon_prfs_verify(const unsigned char *,
                             const unsigned char *,
                             unsigned long long,
                             const unsigned char *);

static const struct {
    const char *name;
    auth_fn auth;
    verify_fn verify;
} algorithms[] = {
    {"Ascon-Mac", ascon_mac_auth, ascon_mac_verify},
    {"Ascon-PrfShort", ascon_prfs_auth, ascon_prfs_verify}
};

static unsigned char key[KEY_BYTES];
static unsigned char message[17];
static unsigned char tag[TAG_BYTES];
static volatile uint64_t checksum = 0;

static uint64_t read_ticks(void) {
    _mm_lfence();
    uint64_t t = __rdtsc();
    _mm_lfence();
    return t;
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

static int validate(void) {
    const size_t sizes[] = {1, 8, 16};

    for (int a = 0; a < 2; a++) {
        for (int n = 0; n < 3; n++) {
            size_t len = sizes[n];
            unsigned char first[16];
            unsigned char second[16];

            if (algorithms[a].auth(first, message, len, key))
                return -1;
            if (algorithms[a].auth(second, message, len, key))
                return -1;
            if (memcmp(first, second, 16))
                return -1;
            if (algorithms[a].verify(first, message, len, key))
                return -1;

            first[0] ^= 1;
            if (algorithms[a].verify(first, message, len, key) == 0)
                return -1;
        }
    }

    if (ascon_prfs_auth(tag, message, 17, key) != -1)
        return -1;

    fprintf(stderr,
            "PASS: Both algorithms passed API self-tests.\n");
    fprintf(stderr,
            "PASS: PrfShort rejected 17-byte input.\n");
    return 0;
}

static int run_batch(int a, size_t len) {
    for (int i = 0; i < BATCH; i++) {
        if (algorithms[a].auth(tag, message, len, key))
            return -1;
        checksum += tag[i % TAG_BYTES];
    }
    return 0;
}

int main(int argc, char **argv) {
    const size_t sizes[] = {1, 8, 16};

    for (int i = 0; i < KEY_BYTES; i++)
        key[i] = (unsigned char)i;

    for (int i = 0; i < 17; i++)
        message[i] = (unsigned char)i;

    if (validate()) {
        fprintf(stderr, "ERROR: API validation failed.\n");
        return 1;
    }

    if (argc > 1) {
        if (strcmp(argv[1], "--self-test") == 0)
            return 0;
        fprintf(stderr, "Unknown argument.\n");
        return 1;
    }

    DWORD_PTR old_mask = SetThreadAffinityMask(
        GetCurrentThread(), (DWORD_PTR)1);

    if (!old_mask) {
        fprintf(stderr, "ERROR: CPU affinity failed.\n");
        return 1;
    }

    SetThreadPriority(GetCurrentThread(),
                      THREAD_PRIORITY_ABOVE_NORMAL);

    uint64_t overhead = timer_overhead();

    fprintf(stderr,
            "Comparative benchmark: 2 algorithms, 3 sizes, "
            "3 sessions, 30 samples.\n");

    printf("algorithm,implementation,session,input_bytes,"
           "sample,batch_calls,total_tsc_ticks,"
           "timer_overhead_ticks,net_tsc_ticks_per_call\n");

    for (int session = 1; session <= SESSIONS; session++) {
        fprintf(stderr, "Session %d/%d\n",
                session, SESSIONS);

        for (int n = 0; n < 3; n++) {
            size_t len = sizes[n];

            for (int a = 0; a < 2; a++) {
                for (int w = 0; w < WARMUP; w++) {
                    if (algorithms[a].auth(
                            tag, message, len, key))
                        return 1;
                }
            }

            for (int sample = 1;
                 sample <= SAMPLES; sample++) {

                for (int slot = 0; slot < 2; slot++) {
                    int a = ((sample + session) % 2 == 0)
                            ? slot : 1 - slot;

                    uint64_t start = read_ticks();
                    int result = run_batch(a, len);
                    uint64_t end = read_ticks();

                    if (result || end < start) {
                        fprintf(stderr,
                                "ERROR: Measurement failed.\n");
                        return 1;
                    }

                    uint64_t total = end - start;
                    uint64_t net = total > overhead
                                   ? total - overhead : 0;

                    double per_call =
                        (double)net / BATCH;

                    printf("%s,opt64,%d,%zu,%d,%d,"
                           "%" PRIu64 ",%" PRIu64 ",%.3f\n",
                           algorithms[a].name,
                           session, len, sample, BATCH,
                           total, overhead, per_call);
                }
            }
        }
    }

    fprintf(stderr,
            "Completed 540 measurements. "
            "Checksum=%" PRIu64 "\n", checksum);

    SetThreadAffinityMask(GetCurrentThread(), old_mask);
    return 0;
}
