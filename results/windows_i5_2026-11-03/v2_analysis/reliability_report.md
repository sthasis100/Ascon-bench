# Benchmarking V2 — preliminary reliability screening

Raw source: `results/windows_i5_2026-11-03/raw_runs.csv`
Configurations: 141
Measurements: 4230
Configurations with substantive screening flags: 25

## Screening rules (exploratory; not acceptance/rejection criteria)

- `HIGH_CV`: sample standard deviation / mean > 10%
- `TEMPORAL_JUMP`: consecutive values change by > 20% (>= 10 samples)
- `SLOW_MEDIAN_VS_MIN`: median > minimum by 20% of median (>= 10 samples)
- `LOW_SAMPLE_COUNT`: fewer than 10 readings; pilot data is not conclusive
- All original readings are retained. No trimming or replacement.

## Flagged configurations

- amac msg=1024B out=16B: median=14722.8984 ticks, CV=7.58%, jump=42.07% at run 11; TEMPORAL_JUMP
- ascon_mac msg=1B out=16B: median=389.8325 ticks, CV=10.55%, jump=37.05% at run 28; HIGH_CV;TEMPORAL_JUMP;SLOW_MEDIAN_VS_MIN
- ascon_mac msg=8B out=16B: median=216.3649 ticks, CV=4.27%, jump=22.06% at run 3; TEMPORAL_JUMP
- ascon_mac msg=1536B out=16B: median=5692.3765 ticks, CV=3.62%, jump=20.09% at run 22; TEMPORAL_JUMP
- ascon_prf msg=64B out=64B: median=762.9817 ticks, CV=4.65%, jump=25.44% at run 23; TEMPORAL_JUMP
- ascon_prf msg=128B out=64B: median=992.52 ticks, CV=6.25%, jump=23.71% at run 26; TEMPORAL_JUMP
- ascon_prf msg=16384B out=64B: median=58886.3125 ticks, CV=14.22%, jump=79.47% at run 22; HIGH_CV;TEMPORAL_JUMP
- ascon_prfshort msg=8B out=16B: median=129.1094 ticks, CV=11.78%, jump=26.43% at run 8; HIGH_CV;TEMPORAL_JUMP
- cxof128 msg=256B out=64B: median=4597.8066 ticks, CV=6.39%, jump=35.28% at run 20; TEMPORAL_JUMP
- cxof128 msg=1536B out=64B: median=21730.8824 ticks, CV=8.67%, jump=22.08% at run 13; TEMPORAL_JUMP
- cxof128_ref msg=256B out=64B: median=5203.6396 ticks, CV=5.44%, jump=30.1% at run 3; TEMPORAL_JUMP
- cxof128_ref msg=4096B out=64B: median=61419.2188 ticks, CV=10.28%, jump=22.07% at run 4; HIGH_CV;TEMPORAL_JUMP
- hash256_bare msg=8B out=32B: median=544.599 ticks, CV=8.45%, jump=42.09% at run 4; TEMPORAL_JUMP
- hash256_bare msg=1536B out=32B: median=21432.5 ticks, CV=7.95%, jump=44.47% at run 2; TEMPORAL_JUMP
- mac_from_hash256 msg=1B out=32B: median=672.879 ticks, CV=6.23%, jump=28.79% at run 23; TEMPORAL_JUMP
- mac_from_hash256 msg=256B out=32B: median=4267.2959 ticks, CV=14.02%, jump=31.39% at run 21; HIGH_CV;TEMPORAL_JUMP
- mac_from_hash256 msg=512B out=32B: median=7876.459 ticks, CV=12.32%, jump=24.6% at run 18; HIGH_CV;TEMPORAL_JUMP
- mac_from_xof128 msg=16B out=16B: median=666.4725 ticks, CV=11.64%, jump=38.16% at run 28; HIGH_CV;TEMPORAL_JUMP
- mac_from_xof128 msg=4096B out=16B: median=62533.5938 ticks, CV=6.54%, jump=36.4% at run 19; TEMPORAL_JUMP
- prf_from_xof128 msg=8B out=64B: median=2044.8918 ticks, CV=21.98%, jump=55.81% at run 9; HIGH_CV;TEMPORAL_JUMP;SLOW_MEDIAN_VS_MIN
- prf_from_xof128 msg=32B out=64B: median=2584.4006 ticks, CV=19.56%, jump=26.31% at run 22; HIGH_CV;TEMPORAL_JUMP;SLOW_MEDIAN_VS_MIN
- prf_from_xof128 msg=256B out=64B: median=4570.6182 ticks, CV=6.07%, jump=25.1% at run 1; TEMPORAL_JUMP
- prf_from_xof128 msg=4096B out=64B: median=57090.2031 ticks, CV=4.66%, jump=25.38% at run 29; TEMPORAL_JUMP
- prf_kdf msg=30B out=64B: median=575.1487 ticks, CV=20.98%, jump=48.14% at run 21; HIGH_CV;TEMPORAL_JUMP
- xof128_bare msg=256B out=64B: median=4340.1523 ticks, CV=6.24%, jump=34.73% at run 5; TEMPORAL_JUMP

## Targeted repeat-run comparisons

- ascon_mac msg=1B: original median 389.8325 vs repeat 230.4223 ticks/call (-40.89% change)

## Interpretation limits

These are diagnostics, not proof of a CPU-frequency cause, a compiler bug, or incorrect cryptographic output.
Repetitions within one run are not independent experimental sessions. This report does not claim confidence intervals or cross-platform significance.
Measurement units are TSC ticks/call, not direct elapsed nanoseconds.
Investigate flags with separately recorded repeat sessions and environment logs.
