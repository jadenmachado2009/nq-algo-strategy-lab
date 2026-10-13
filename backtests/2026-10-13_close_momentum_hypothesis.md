# Conditional close momentum — hypothesis test — 2026-10-13

**Source:** "NQ Conditional Close Momentum Hypothesis", J. Machado, 2026-10-13.
**Verdict:** Mechanism supported (4 of 5 predictions pass). Effect too small to trade. Not a
replacement for ORB; at best an overlay.

## The hypothesis
Forced hedging flow into the 16:00 ET cash close extends the day's move over the final 30 minutes,
but ONLY in high-volatility regimes. Short-gamma dealers must buy rallies and sell declines
(Baltussen et al., JFE 2021); leveraged/inverse ETFs must trade AUM x L(L-1) x r at the close, and
L(L-1) > 0 for every such fund. Dealer gamma is short after sell-offs and long in calm uptrends,
which is why the regime condition is required rather than optional.

Pre-registered with five predictions and a calibration band (54-56% hit rate; ">=60% means a bug").

## Setup
Dukascopy NQ 5m, 1,940 sessions with full closing-window coverage. ROD = P(15:30)/P(prev 16:00) - 1;
sigma20 from the prior 20 close-to-close returns; high-vol = sigma20 above its trailing 252-session
median; eligible = high-vol AND |z| >= 0.5 AND not calendar-excluded. Entry at the 15:30 open, exit
at the 15:55 close. Costs 1.12 pts (0.76 bp) round trip.

**456 eligible days = 59/year.** The hypothesis predicted 60-70/year.

## Scorecard

| prediction | result | verdict |
|---|---|---|
| 1. direction | +2.39bp, t=+0.89, hit 51.5% | weak — sign right, not significant |
| 2. dose-response | −3.87 → +3.26 → **+7.79**bp across \|z\| terciles | **PASS**, monotonic |
| 3. regime split | high +2.39 vs **low −2.65 (t=−2.80)** | **PASS**, strongly |
| 4. placebo (13:00-13:30) | +0.32bp, t=+0.17 | **PASS**, no effect |
| 5. reversal (1-3 sessions) | −17.0, −8.2, −10.5bp | **PASS**, all negative |

**The exclusions do real work.** Calendar-excluded high-vol days: +0.26bp (t=0.02). |z| < 0.5 days:
+0.39bp (t=0.17). Both exactly zero — the effect lives precisely where the mechanism says it should,
which is the single most convincing part of the result.

## A look-ahead bug the pre-registered placebo caught
The first implementation used sign(ROD) measured at 15:30 to predict the 13:00-13:30 return. That
return is part of the path from the prior close to 15:30, so ROD contains it by construction. The
buggy placebo read **+5.69bp at t=+3.36**, which would have been reported as the hypothesis FAILING
its own kill condition. Corrected to give the placebo its own run-of-day (ROD measured at 13:00):
+0.32bp, t=+0.17.

Without a pre-specified placebo this bug would have produced a false rejection.

## Why it is not tradeable
- hit rate **51.5%**, below the author's own 54-56% calibration band
- **out-of-sample negative**: IS +5.66bp (n=288) vs OOS −3.20bp (n=168)
- block bootstrap by month: +2.39bp, 95% CI [−3.48, +9.02], P(>0) = 76.2%
- 7 of 9 high-vol episodes positive, but magnitude dominated by 2020 (+26.6bp vs +4-8bp elsewhere)

**Arithmetic for the prop use case:** +2.39bp x 59 trades = 141bp/year. The challenge needs 600bp.
That is four years per attempt. Reaching it in reasonable time would need ~250x account notional,
which the catastrophe stop at sigma20 makes impossible within a $2,000 drawdown.

The author anticipated this: *"Judge this strategy on the P&L it adds, not standalone."*

## What this changes
Nothing about the recommended spec. ORB remains the only strategy here with a tradeable edge. This
is the first hypothesis tested rather than searched, and it produced far more information per hour
than 1,260 grid combinations did — four structural signatures, one caught bug, and a clear verdict.

Tool: `research/close_momentum.py`
