# Can ORB be repaired by retargeting? One real improvement, 0.50R -> 0.75R — 2026-10-17

**Verdict:** The target has been set at a mildly suboptimal point the whole time. Moving it from
0.50R to **0.75R** raises expectancy ~29% in the recent half and cuts days-to-pass ~22%, and it is
the only candidate of nine that survives the split test. **It does not rescue the current regime**
(break period −0.099R, P(edge>0) = 13.6%). The DO-NOT-FUND status is unchanged.

## Method — exact reconstruction, no extra data mining
Each trade was run with **no target**, exiting only at its stop or the session close, recording its
maximum favourable excursion. A trade with a target at `rr` wins iff its MFE reaches `rr` before the
stop, and MFE is recorded path-wise up to the stop, so that condition is exact; if MFE < `rr` the
trade ends identically to the no-target case. One pass therefore reconstructs **every** target
exactly. Validated against `orb.orb_trades(rr=0.5)` trade-for-trade: `max|diff| = 4.7e-14`.

Two errors in that reconstruction were caught by the self-check before any result was read:
1. A filled target pays **no exit slippage** — it is a limit order. Entry slippage is already inside
   `entry`, hence inside `risk` and the target level. Charging 2x slip understated every winner.
2. `orb.py` checks the stop **before** the target within a bar, so a bar touching both is a loss.
   The stopping bar's high must not reach MFE.

Without the self-check both would have silently biased the whole sweep.

## The pooled sweep is a trap
On the pooled baseline (2019 → 2026-06, 6,757 trades) expectancy rises **monotonically** with the
target — Spearman +1.000 — from +0.0204R at 0.25R to +0.0640R at 2.00R, with day-clustered P(>0)
above 98% at every single grid point. Read on its own it says "use 2.00R and double the edge."

Split at the original study's 70/30 boundary (2024-06-14), that collapses:

| target | IS mean | IS mean/sd | OOS mean | OOS mean/sd | dominates 0.50R? |
|---|---|---|---|---|---|
| 0.25 | +0.0130 | 0.0286 | +0.0402 | 0.0929 | no |
| 0.30 | +0.0175 | 0.0352 | +0.0465 | 0.0977 | no |
| 0.40 | +0.0201 | 0.0349 | +0.0513 | 0.0927 | no |
| **0.50** | **+0.0225** | **0.0339** | **+0.0514** | **0.0835** | incumbent |
| 0.60 | +0.0326 | 0.0451 | +0.0530 | 0.0797 | no |
| **0.75** | **+0.0366** | **0.0466** | **+0.0662** | **0.0911** | **YES** |
| 1.00 | +0.0462 | 0.0529 | +0.0594 | 0.0730 | no |
| 1.25 | +0.0604 | 0.0648 | +0.0593 | 0.0670 | no |
| 1.50 | +0.0636 | 0.0651 | +0.0501 | 0.0541 | no |
| 2.00 | +0.0658 | 0.0636 | +0.0589 | 0.0596 | no |

Spearman falls from **+1.000 in-sample to +0.588 out-of-sample**. The long-target advantage is a
property of 2019–2024, not of ORB. In 2024–2026 the curve is flat-to-humped and the *shortest*
targets are the best risk-adjusted. **1.25R and 2.00R would have been a fit to the first half.**

Out of sample the bracket barely matters for raw expectancy: everything from 0.25R to 2.00R returns
+0.040R to +0.066R. That cuts both ways — it means the choice is not fragile, and it means
retargeting was never going to be a rescue.

## The test, and its one weakness
Criterion: a candidate must beat the incumbent on **both** mean and mean/sd in **both** halves
independently. Mean/sd is included because pass probability under a trailing drawdown depends on
risk-adjusted return, not raw edge. Requiring only "beats on mean in both halves" admits five
candidates; the second moment narrows it to one.

**Disclosure:** the criterion was fixed after the IS/OOS tables were seen, though before the break
period was evaluated. It names no specific target and 0.75R is its unique survivor, but it is not a
genuine pre-registration and should not be read as one.

## Does it rescue the break? No.
| target | n | sessions | WR | expectancy | day-clustered 95% CI | P(>0) |
|---|---|---|---|---|---|---|
| 0.50R | 249 | 57 | 53.0% | −0.1207R | [−0.2680, +0.0297] | 6.2% |
| 0.75R | 249 | 57 | 48.6% | −0.0987R | [−0.2702, +0.0783] | 13.6% |

Less bad, still negative, and the interval is far too wide to call either way. Nothing in the
0.25R–2.00R range makes the break period positive. **The payoff structure is not what broke, so
changing it cannot be the fix.**

## Pass-rate consequence
Recent half as the pool, Topstep 50K, 4 trades/day. **Independent draws, so both rows are inflated**
— same-day ORB trades agree in sign 67.5% of the time. Relative comparison only.

| target | risk | pass | days to pass | E[payout] | EV/attempt |
|---|---|---|---|---|---|
| 0.50R | 0.50% | 72.8% | 41 | $2,920 | +$1,919 |
| 0.75R | 0.50% | 71.4% | **32** | $2,737 | +$1,749 |
| 0.50R | 1.25% | 51.7% | 10 | $1,846 | +$828 |
| 0.75R | 1.25% | 48.9% | **9** | $2,063 | +$887 |

Pass rate is a wash (−1.4pp); **days-to-pass falls 22%** at the conservative risk level. That was the
stated objective in the 2026-10-13 decoupled spec, so 0.75R is an improvement on the metric that was
being optimised, not on the one being reported.

## What was rejected
- **Shorter targets to match the collapsed MFE** (median 0.52R → 0.44R). Mechanically appealing and
  wrong: a shorter bracket needs a *higher* win rate to clear costs, and 0.40R is worse than 0.50R
  in both halves and in the break.
- **Any regime or volatility filter chosen now.** With 249 break-period trades, any filter that
  excludes this drawdown is fit to it by construction.

## Status
No change to the spec yet and no change to the recommendation. 0.75R is a candidate for the next
version of the spec, to be applied **only if and when** the tracker reads HEALTHY. Retargeting a
strategy that is currently unprofitable does not make it profitable.
