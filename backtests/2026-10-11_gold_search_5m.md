# Bounded search + null test on gold (XAUUSD -> GC/MGC) — 2026-10-11

**Verdict:** Nothing found. p = 0.733. Third consecutive null across three instruments.

## Why gold
The NQ studies ran on Dukascopy data tracking the CASH Nasdaq-100 index, whose opening prints are
stale (100 constituents open staggered). Gold has no opening auction and arbitrages against its
future in one trade rather than 100.

Fidelity measured BEFORE the study, against real futures (5m, ~55 days):

| spot -> future | 5m return corr | bar-range ratio |
|---|---|---|
| **XAUUSD -> GC** | **0.9835** | **0.996** |
| GBPUSD -> 6B | 0.9679 | 1.140 |
| EURUSD -> 6E | 0.9673 | 1.050 |

Gold's bars are effectively the futures' bars. This is the first study in the repo where data
fidelity was established before, not after.

## Setup
| | |
|---|---|
| Tool | `research/search_gold.py`, data via `research/fetch_data.py` |
| Data | Dukascopy XAUUSD 5m, 2019-01 → 2026-10, 551,536 bars |
| Split | IS 2018-12 → 2024-06 (386,075) / OOS 2024-06 → 2026-10 (165,461) |
| Grid | 3 trends × 5 triggers × 3 sessions × 2 vol filters × 4 exits = 360 |
| Costs | MGC: 0.324 pts round trip ($3.24), commission + 1 tick/side |
| Restriction | stops ≥ 1.5×ATR, **fixed before any result was seen** |

## The cost finding, which was the surprise
Gold is MORE expensive than NQ relative to its own volatility:

| session (NY) | median 5m ATR | drag @1×ATR | @3×ATR |
|---|---|---|---|
| all hours | 1.35 | 0.241R | 0.080R |
| NY morning 08:00–11:30 | 2.21 | 0.147R | 0.049R |
| NY RTH 09:30–16:00 | 1.85 | 0.175R | 0.058R |
| Asia 19:00–02:00 | 0.99 | 0.326R | 0.109R |
| *NQ reference* | *11.60* | *0.097R* | *0.032R* |

A 1×ATR stop on gold costs 0.241R per trade — past the prop break-even line of −0.12R before the
strategy does anything. Hence the ≥1.5×ATR restriction.

## Result — best in-sample

| exp(R) | PF | WR | n | CI95 | strategy |
|---|---|---|---|---|---|
| **+0.019** | 1.03 | 43.0% | 323 | [−0.134, +0.172] | macd_cross \| ema50>200 \| open30 \| atr>median \| 2.0/3.0 |
| +0.008 | 1.01 | 42.8% | 362 | [−0.136, +0.152] | macd_cross \| ema50>200 \| open30 \| none \| 2.0/3.0 |
| −0.005 | 0.99 | 42.6% | 695 | [−0.109, +0.099] | macd_cross \| none \| open30 \| none \| 2.0/3.0 |

334 of 360 combos qualified. Only two were positive, both with confidence intervals ~8× the estimate.

## Null test — FAILED

| | expectancy |
|---|---|
| Best real | +0.019R |
| Best on noise, mean | **+0.063R** |
| Best on noise, max | +0.196R |
| **p-value** | **0.733** |

**Noise beat the real data on average.** A 360-combo grid on block-bootstrapped gold produces a
better-looking best combo than the real series does, three times out of four. Out-of-sample was
never touched, per protocol.

## Three searches, three nulls

| Study | Instrument | Grid | Best real | Noise mean | p |
|---|---|---|---|---|---|
| 2026-10-07 | NQ hourly | 450 | +0.227R | +0.194R | 0.27 |
| 2026-10-07 | NQ 5m | 450 | — | — | 0.72 |
| **2026-10-11** | **Gold 5m** | **360** | **+0.019R** | **+0.063R** | **0.733** |

Different instrument, different vendor, verified fidelity, same answer. This is now the most
robust finding in the repo: **this family of indicator-combination strategies has no edge**, and
the grids that appear to find one are finding noise.

## Impact on pass probability
With no verified edge, the Topstep pass rate is the zero-edge baseline:

| True edge | Pass rate (best risk) |
|---|---|
| ORB as recorded (+0.022R) | 36.5% |
| **Zero edge — what we can verify** | **29.8%** |
| What ES showed (−0.042R) | 19.7% |

The README's 39.2% / +$502 EV figures assume ORB's +0.022R, which was measured on cash-index data,
failed to replicate on ES and YM, and cannot be sized at current MNQ prices. Those figures need
correcting.

## Next action
Not another grid. Three nulls across two instruments is enough evidence that this search family is
exhausted. Either paper trade something already specified and measure real fills, or stop.
