# ORB on NQ — full re-verification on reproducible data — 2026-10-12

**Verdict:** The v4 figure of 39.2% stands and is slightly conservative. The edge is probably real
(87.5% confidence) but not established at 95%. The live risk is 2026, which is negative and cannot
be distinguished from noise.

## Why this re-run
Three claims needed checking: (a) that the Dukascopy NQ data was unfit — now measured FALSE
(0.9840 return correlation vs NQ=F, see 2026-10-12_cash_vs_futures_ORB.md); (b) that 39.2% was
unreproducible; (c) that ORB had no out-of-sample edge. (b) and (c) were both wrong, and this
records the corrected analysis.

Data re-downloaded via `research/fetch_data.py nq 2019 2026` — 532,181 bars, now reproducible.

## ORB reproduces exactly

| | original (deleted data) | re-downloaded |
|---|---|---|
| best in-sample, 60m long | +0.034R / 884 trades | **+0.035R / 886** |
| out-of-sample, 60m long | +0.011R / 380 | **+0.009R / 379** |

## The error that was corrected
Earlier analysis quoted **+0.011R** as ORB's out-of-sample edge. That is the SINGLE BEST CONFIG
(60m long, 379 trades). The spec used in the bankroll analysis is **five windows pooled**, whose
out-of-sample edge is **+0.0297R over 2,105 trades** — HIGHER than the full-period +0.0227R.

The edge did not decay out of sample. The wrong two numbers were being compared.

## Direction selection survives
Long-only was chosen in-sample. Out-of-sample, on data never seen:

| direction | n | WR | edge |
|---|---|---|---|
| **long** | 2,105 | 65.1% | **+0.0297R** |
| short | 1,881 | 62.7% | +0.0052R |
| both | 2,970 | 63.2% | +0.0035R |

The choice holds up. It was not an artefact of the in-sample fit.

## Day-clustered confidence intervals
2,105 trades sit on only 461 sessions (4.6/day, nested ranges on one price path). A naive CI assumes
independence and is too narrow. Clustering by session:

| period | n | sessions | edge | 95% CI | P(>0) |
|---|---|---|---|---|---|
| full OOS | 2,105 | 461 | +0.0297 | [−0.0202, +0.0768] | **87.5%** |
| 2024 | 495 | 110 | +0.0401 | [−0.0636, +0.1393] | 78.5% |
| 2025 | 918 | 195 | +0.0601 | [−0.0125, +0.1302] | 94.8% |
| **2026** | 692 | 156 | **−0.0180** | [−0.1113, +0.0666] | **34.4%** |

(Naive CI on the full OOS would read [+0.0027, +0.0567] and falsely clear zero.)

## Pass rate, uncertainty propagated
Resampling sessions, rebuilding the pool, and running the Topstep model on each:

```
median 48.4%  |  95% range [18.2%, 79.1%]
P(above the 28% zero-edge floor) = 91.7%
```

Point estimates: full OOS pool -> **46.1%** | 2026 pool only -> **18.3%** | edge zeroed -> **27.4%**

## The unresolved question
2026 is negative. The CIs overlap in both directions — 2026's interval contains +0.030, and the
full-OOS interval contains −0.018. **The data cannot distinguish a stable edge having a bad year
from an edge that has decayed.** That single question is worth 28 points of pass rate.

More history will not resolve it, because the question is about the current regime. Only forward
data will.

## Corrected figures for the README
| | v4 says | should say |
|---|---|---|
| Pass rate | 39.2% | **~46% central, 28% floor, 95% range 18–79%** |
| Edge | +0.022R full period | **+0.0297R out-of-sample, 87.5% likely positive** |
| Caveat | "2026 is the weakest" | **2026 is NEGATIVE (−0.018R) and decay cannot be ruled out** |

EV per attempt stays positive at every edge in the plausible range, since break-even is 4.1%.
