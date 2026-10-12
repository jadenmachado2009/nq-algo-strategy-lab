# Exact model — INFLIGHT assumption removed and verified — 2026-10-13

**Supersedes `2026-10-12_FINAL_corrected_economics.md`.** The last published figures rested on an
assumed `INFLIGHT = 2`. That parameter is now measured and then eliminated entirely.

## 1. The assumption, measured
How many positions are already open when cumulative daily loss reaches the limit? Measured over
1,553 sessions by tracking each window's real entry and exit bar:

| positions in-flight | share |
|---|---|
| 0 | 33.2% |
| 1 | 27.7% |
| 2 | 9.4% |
| 3 | 29.7% |
| **mean** | **1.36** (median 1) |

Max simultaneous open positions per session averages **3.83**; on 41.6% of sessions all five are
open at once.

## 2. The assumption, removed
The simulator now replays each session in true **exit order**, and a leg is taken if its ENTRY
preceded the moment the lockout fired. No parameter.

| risk | pass (5 seeds) | median days | 1% worst day | floor (no lockout) |
|---|---|---|---|---|
| **0.50%** | **39.4% ±0.2%** | 14 | **−$1,455** | 39.0% |
| 0.75% | 40.4% ±0.3% | 8 | −$2,018 | 39.6% |
| 1.00% | 40.2% ±0.3% | 5 | −$2,626 | 39.1% |
| 1.25% | 40.3% ±0.3% | 4 | −$3,273 | 39.2% |

**The daily lockout is worth essentially nothing** — 40.2% against a 39.1% floor at 1% risk. By the
time it fires the positions are already open, and a lockout cannot close them. Earlier figures of
+17.6 points from the lockout were entirely an artefact of assuming instantaneous closure.

**Pass rate is flat at ~39–40% at every risk level.** Gambler's-ruin scale invariance. Risk changes
how fast you resolve and how bad your worst day is — not whether you pass.

## 3. Economics

| risk | pass | days | never paid out | E[payout] | EV | break-even |
|---|---|---|---|---|---|---|
| **0.50%** | 39.1% | 14 | **36.7%** | $1,468 | **+$466** | 3.7% |
| 0.75% | 40.1% | 8 | 50.0% | $1,556 | +$515 | 3.5% |
| 1.00% | 39.8% | 5 | 60.3% | $1,740 | +$584 | 3.1% |

## 4. Sequential attempts at 0.50%

| tries | spend | P(≥1 pass) | P(profit) | median | mean |
|---|---|---|---|---|---|
| 1 | $49 | 39.1% | 24.5% | −$49 | +$468 |
| 3 | $97 | 77.4% | 47.9% | −$147 | +$924 |
| **5** | **$115** | **91.6%** | **56.3%** | **+$461** | **+$1,085** |
| 10 | $125 | 99.3% | 61.0% | +$695 | +$1,187 |

## Recommendation changes: 0.50%, not 1.00%
Pass rate is identical across risk, so the choice is decided downstream:

- **Funded survival.** 36.7% never pay out at 0.50% versus 60.3% at 1.00%. Smaller size means the
  funded account lives longer and banks more payouts.
- **Median outcome.** Five attempts gives **+$461** at 0.50% against **−$198** at 1.00%.
- **Worst day.** −$1,455 is the only figure that stays inside the $2,000 maximum loss limit.

1.00% has a higher mean EV (+$584 vs +$466) but a worse median. For a small bankroll the median is
the number that matters.

## Standing caveats
- Never paper traded. +0.025R against ±0.6R of measured exit noise.
- Edge 87.5% likely positive on a day-clustered bootstrap, not established at 95%.
- Day-clustering does not handle multi-day regime clustering.
