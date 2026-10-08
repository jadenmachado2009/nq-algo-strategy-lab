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

## `search_5m.py` — the same search on 531k bars of 5-minute data

The hourly run left 150–320 trades per combo (CI ±0.15R), too wide to detect the +0.10R edge the
prop maths rewards. This run uses Dukascopy 5-minute NQ, 2019–2026, **531,355 bars**, split 70/30
in time, with the null test run on the in-sample half only.

**Result (2026-10-07):** best in-sample +0.074R over 1,772 trades (Donchian-20 breakout + 50/200
trend filter + NY morning; the entire top-10 is that family). Null test over 25 synthetic paths:
best-on-noise **mean +0.115R**, max +0.275R → **p = 0.72**. The real winner is below the typical
noise winner. Out-of-sample: −0.023R over 811 trades.

Year by year the family decays — +0.17R (2019), +0.11/+0.09/+0.07R (2021–23), then −0.00/−0.04/−0.02R
(2024–26) — which is why an in-sample window ending mid-2024 looked positive.

Full write-up: `backtests/2026-10-07_search_5m_2019-2026.md`.

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
   150–320. Only CBE had enough (≈1,500 trades, −0.05R in-sample / −0.11R out-of-sample) — below the line,
   which is why its simulated prop EV is −$111/attempt.

**Consequence:** the prop play is only actionable with a strategy whose edge is measured over
~1,500+ trades. That is a *sample-size* problem, not a strategy-hunting problem.

## `geometry_search.py` — searching risk policies instead of signals

Since no entry edge survived testing, this searches the lever that does move: risk geometry. It
exploits the fact that a real futures trailing drawdown **freezes** once you are far enough ahead
(`dd_line = min(peak - D, cap)`), so variance is expensive before the freeze and cheap after it.

**Result (zero-edge trade distribution, -0.02R — achievable only with stops >= 2xATR hourly; see the correction note below):** a policy of 0.75% base risk, 1 trade/day,
halving risk inside 60% of target and escalating once the trail freezes reaches **~30% pass rate**
and **+$146 to +$408 net EV per attempt** depending on firm profile — and stays positive down to a
true edge of about -0.10R. Using the frozen-trail structure is worth +$49 to +$73 per attempt over
the best fixed-risk policy. Consistency-rule compliance is checked and holds at 100% for the
recommended settings.

Full spec, numbers and caveats: **`research/PROP_PLAYBOOK.md`**.

## Correction (2026-10-09)

An earlier zero-edge baseline of -0.002R was not reproducible — rerunning the same code on data
differing by ten bars gave -0.075R. Trades from a single price path are not independent, so the
naive standard error understated the uncertainty. Measured properly over 7.8 years and ~20,000
random-entry trades, the zero-skill expectancy is a function of STOP WIDTH:

| Setup | Measured |
|---|---|
| 5m, 1xATR (~12 pts) | **-0.12R** (below the -0.075R break-even line) |
| Hourly, 1xATR (~71 pts) | -0.08R |
| Hourly, 2xATR (~143 pts) | -0.031R |
| Hourly, 3xATR (~214 pts) | **-0.016R** |

So "no edge required" holds only with wide stops. With tight stops the scheme is EV-negative before
any strategy is involved.

## Honest caveats
- Hourly data and 2.4 years only (free Yahoo limit). Validation of any survivor belongs on
  QuantConnect 2019–2023, which this search has never seen.
- The prop model omits consistency rules, scaling plans and payout waiting periods — all of which
  reduce EV. Treat the EV column as an optimistic bound.
- Trades are resampled independently; real losing streaks cluster worse than that, which lowers
  pass rates further.
