# Research — strategy search and prop-account EV

Two tools, built 2026-10-07. Both answer questions that backtesting a single strategy can't.

## `search.py` — bounded strategy search with a null test

450 combos (3 trend filters × 5 entry triggers × 3 sessions × 2 volatility filters × 5 exit sets),
simulated on ~2.4 years of free hourly NQ data with MNQ costs (0.62 pts round-trip commission,
1 tick slippage per side), entry at the next bar open, stop-first inside a bar, flat at day end.

The point is the **null test**: the same grid is rerun on block-bootstrapped synthetic price
paths (same volatility clustering, no real structure). That distribution is what luck alone
produces across 450 tries.

**Result (2026-10-07, 2024-05 → 2026-10):**

| | expectancy |
|---|---|
| Best combo on real data (`rsi_mom \| ema50>200 \| morning \| SL/TP 1.0/2.0`, PF 1.42, 154 trades) | **+0.227R** |
| Best combo on noise, mean of 30 reps | +0.194R |
| Best combo on noise, worst case | +0.330R |
| **p-value (noise ≥ real)** | **0.27** |

**Verdict: nothing found.** A PF 1.42 "winner" is exactly what searching 450 combos produces
on noise. Without the null test this would have looked like a discovery.

## `prop_mc.py` / `prop_edge_sensitivity.py` — prop account as a structured product

From DeltaTrend Trading, *"stop trading like an idiot"*: a challenge account has a convex payoff
(downside capped at the fee, upside uncapped), so the question is not "is the strategy +EV?" but
"which risk-per-trade maximises net EV after fees, and what's the pass rate?" Monte Carlo,
20,000 paths per setting, modelling trailing drawdown, daily loss, minimum trading days,
activation fee, split, and the funded phase.

**Net EV per attempt vs true edge** (50k futures eval: $3,000 target, $2,000 trailing DD, $314 fees, 90% split):

| True edge | Best risk/trade | Pass rate | Net EV |
|---|---|---|---|
| −0.20R | 1.50% | 6.1% | −$110 |
| −0.10R | 0.75% | 14.4% | −$41 |
| **−0.075R** | — | — | **$0 (break-even)** |
| −0.02R | 0.75% | 22.1% | +$119 |
| 0.00R | 0.75% | 24.3% | +$180 |
| +0.05R | 0.75% | 30.2% | +$373 |

Two real findings:

1. **The convexity claim holds.** You don't need a profitable strategy — you need one better than
   about **−0.075R per trade**, traded at **~0.75% risk**. Too much risk kills it: at 2%+ you hit the
   trailing drawdown before the target regardless of edge.
2. **But you can't measure which side of that line you're on.** With an R standard deviation of ~1.4,
   distinguishing −0.075R from 0 at 95% confidence needs **~1,340 trades**. Our search winners had
   150–320. Only CBE had enough (≈1,500 trades, −0.15R measured) — and it sits clearly below the line,
   which is why its simulated prop EV is −$111/attempt.

**Consequence:** the prop play is only actionable with a strategy whose edge is measured over
~1,500+ trades. That is a *sample-size* problem, not a strategy-hunting problem.

## Honest caveats
- Hourly data and 2.4 years only (free Yahoo limit). Validation of any survivor belongs on
  QuantConnect 2019–2023, which this search has never seen.
- The prop model omits consistency rules, scaling plans and payout waiting periods — all of which
  reduce EV. Treat the EV column as an optimistic bound.
- Trades are resampled independently; real losing streaks cluster worse than that, which lowers
  pass rates further.
