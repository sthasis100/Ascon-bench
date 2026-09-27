/* =========================================================================
* NOTE:
 * OUR OWN CODE - written by Team 4, University at Albany (INSuRE, Fall 2026)
 * for the project "Performance Benchmarking for Ascon Extensions (v1)".
 * This file is NOT part of the Ascon designers' repository (ascon-c).
 * -------------------------------------------------------------------------
 * WHY
 *   We time everything with RDTSC, the CPU's cycle counter. It is only safe
 *   if the counter is "invariant": it ticks at the same rate all the time,
 *   even when the CPU speeds up or slows down. The CPU says so itself, in
 *   one bit that the CPUID instruction returns.
 *
 * WHAT IT PRINTS (run_all.py reads these three lines)
 *   brand=...              the CPU's name
 *   invariant_tsc=1        1 = safe to use, 0 = not safe
 *   cpuid16_base_mhz=...   the base frequency in MHz, or 0 if not reported
 *   The exit code is 0 if the counter is invariant, and 1 if it is not.
 *
 * BUILD AND RUN (Command Prompt, in the project folder)
 *   gcc -O2 -Wall -Wextra src\check_tsc.c -o build\check_tsc.exe
 *   build\check_tsc.exe
 * ========================================================================= */
#include <cpuid.h>  /* GCC's helper for the CPUID instruction */
#include <stdio.h>
#include <string.h>

int main(void) {
  unsigned int a, b, c, d;     /* the four registers CPUID fills in    */
  unsigned int max_basic;      /* the highest normal CPUID question    */
  unsigned int max_extended;   /* the highest extended CPUID question  */
  unsigned int name[12];       /* 48 characters of the CPU's name      */
  char brand[49];
  int invariant = 0;
  unsigned int base_mhz = 0;
  int i;
  int start;

  /* Which CPUID questions does this CPU answer? */
  max_basic = __get_cpuid_max(0, NULL);
  max_extended = __get_cpuid_max(0x80000000, NULL);

  /* 1. The CPU's name. Questions 0x80000002, 0x80000003 and 0x80000004
        each give 16 characters of it, in the four registers. */
  memset(name, 0, sizeof(name));
  if (max_extended >= 0x80000004) {
    for (i = 0; i < 3; i++) {
      __cpuid(0x80000002 + i, a, b, c, d);
      name[i * 4 + 0] = a;
      name[i * 4 + 1] = b;
      name[i * 4 + 2] = c;
      name[i * 4 + 3] = d;
    }
  }
  memcpy(brand, name, 48);
  brand[48] = '\0';

  /* 2. The check that matters: question 0x80000007, register EDX, bit 8.
        1 means the cycle counter is invariant (Intel and AMD both use it). */
  if (max_extended >= 0x80000007) {
    __cpuid(0x80000007, a, b, c, d);
    invariant = (d >> 8) & 1;
  }

  /* 3. The base frequency in MHz: question 0x16, register EAX. Many CPUs
        do not report it here; then it stays 0 and run_all.py uses the
        CPU's name or the Windows registry instead. */
  if (max_basic >= 0x16) {
    __cpuid(0x16, a, b, c, d);
    base_mhz = a;
  }

  /* Some CPUs put spaces in front of their name: skip them. */
  start = 0;
  while (brand[start] == ' ') {
    start++;
  }

  printf("brand=%s\n", brand + start);
  printf("invariant_tsc=%d\n", invariant);
  printf("cpuid16_base_mhz=%u\n", base_mhz);
  if (invariant) {
    return 0;
  }
  return 1;
}
