# ORB forward test — FAILED. Do not fund an account yet. — 2026-10-13

**Verdict:** ORB is currently in the worst drawdown of its recorded history. The win rate has fallen
from a seven-quarter average near 66% to **48.6%**, which is below the ~67% a 0.5:1 bracket needs to
break even. **Recommendation: paper trade, do not pay for a Topstep account until the win rate
re-establishes above ~65% over 100+ trades.**

## Method
Two independent tests over the most recent 50 sessions (2026-08-04 → 2026-10-13):

1. **Yahoo `NQ=F`** — real futures contract, a data source never used to build or tune ORB
2. **Dukascopy cash index** — the study's own source, same window

## Result: both sources agree

| source | n | win rate | expectancy |
|---|---|---|---|
| Yahoo, real futures | 160 | 51.2% | **−0.1232R** |
| Dukascopy, cash index | 169 | 52.7% | **−0.1193R** |

Day-clustered 95% CI on the futures result: **[−0.3148, +0.0586]**, P(edge > 0) = **9.9%**.

Bar-range ratio between sources is 0.977, so the small difference is bar geometry. **The agreement
means this is the regime, not a data artefact.**

## Quarterly history — the break is sharp

| quarter | n | win rate | expectancy |
|---|---|---|---|
| 2024Q4 | 212 | 66.5% | +0.0783 |
| 2025Q1 | 216 | 63.4% | +0.0592 |
| 2025Q2 | 244 | 66.4% | +0.0324 |
| 2025Q3 | 224 | 65.6% | +0.0449 |
| 2025Q4 | 224 | 69.6% | +0.1002 |
| 2026Q1 | 185 | 66.5% | +0.0487 |
| 2026Q2 | 262 | 68.7% | +0.0608 |
| **2026Q3** | **210** | **48.6%** | **−0.1612** |
| 2026Q4 | 28 | 71.4% | +0.0210 |

Seven consecutive quarters between 63% and 70%, then a 20-point collapse.

**The win rate is the diagnostic, not the expectancy.** ORB's edge is mechanical: a 0.5:1 bracket
reaches its target more often than its stop, and needs roughly 67% to clear costs. At 48.6% the
arithmetic is broken outright — this is not an unlucky run of magnitudes.

## Severity in context
Rolling 50-session windows across 1,553 sessions, 4 distinct episodes this bad:

| episode | worst |
|---|---|
| 2019-09 | −0.1314R |
| 2020-03 (COVID) | −0.1521R |
| 2020-10 | −0.1308R |
| **2026-08 (now)** | **−0.2106R** |

The current episode is the **worst in the dataset**, deeper than the COVID crash.

Current window sits in the worst **3.3%** of all rolling windows by expectancy and the worst
**1.9%** by win rate.

## A statistic retracted
An earlier draft noted "after a window this bad, the next 50 sessions averaged +0.0954R, 100%
positive." Those windows overlap heavily and reduce to **four independent observations**. That is an
anecdote, not evidence, and it should not inform the decision.

## What this proves about the method
Every historical figure in this repo said ~40% pass rate and a +$1,068 median outcome. The forward
test — the only test run on data that built nothing — says the strategy is currently unprofitable.

Funding on the backtest would have meant trading a 48.6% win-rate strategy through its deepest
drawdown on record while paying fees throughout.

## Next action
1. Paper trade the spec now. Free, and it keeps measuring.
2. Resume funding only when the win rate re-establishes above ~65% over **100+ trades**. 2026Q4's
   71.4% is encouraging but rests on 28 trades, roughly two weeks — that is noise.
3. Estimated wait: 6-10 weeks.
