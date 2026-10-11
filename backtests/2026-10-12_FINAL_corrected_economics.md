# ORB on Topstep 50K — definitive corrected economics — 2026-10-12

**Supersedes every pass-rate figure previously published here.** This is the first calculation with
all four known modelling errors fixed at once.

## Corrections applied
1. **Session resampling.** Earlier sims drew independent trades from the pooled R distribution.
   ORB's windows are nested on one price path — same-day trades agree in sign 67.5% of the time
   against 3.8% if independent. Whole sessions are now resampled and replayed intact.
2. **HHMM window bug.** `930 + 45 = 975` is not a time, so windows 35–55 collapsed onto the
   30-minute range. The canonical set contained a duplicate. Fixed to work in minutes.
3. **Daily lockout is not instantaneous.** A lockout stops you OPENING trades; it cannot close
   positions you already hold. ORB's windows trigger 10–15 min apart and overlap, so 2 positions
   are assumed in-flight when it fires. This is the correction that matters most — see below.
4. **Topstep's April 2026 payout caps** modelled in the funded stage (50% of balance, $2,000
   ceiling, $125 minimum).

## Input
ORB NQ, 5 windows (10/20/30/45/60), long only, 0.5:1, MNQ costs.
**6,995 trades over 1,553 sessions, 65.2% WR, +0.0246R.**

## Pass rate and duration (5 seeds each)

| risk | $/trade | pass | median days | 1% worst day | breaches $2,000 MLL? |
|---|---|---|---|---|---|
| 0.40% | $200 | 39.7% ±0.1% | 20 | −$1,354 | no |
| 0.50% | $250 | 39.3% ±0.2% | 14 | −$1,455 | no |
| 0.75% | $375 | 39.9% ±0.3% | 8 | −$2,018 | yes |
| **1.00%** | **$500** | **41.7% ±0.2%** | **5** | −$2,184 | yes |
| 1.25% | $625 | 40.7% ±0.3% | 4 | −$2,653 | yes |

**The pass rate is flat at ~40% across every risk level.** This is gambler's-ruin scale invariance:
with a fixed edge, pass probability does not depend on bet size. Risk changes how FAST you resolve,
not WHETHER you pass.

## The error this replaces
An intermediate result claimed **56.7%** at 1% risk. That assumed the daily lockout fires instantly
with nothing open. Sensitivity to that assumption:

| positions in-flight when the lockout fires | pass rate |
|---|---|
| 0 (the false assumption) | 56.7% |
| 1 | 48.0% |
| **2 (realistic for ORB)** | **41.3%** |
| 4 | 39.1% |
| no lockout at all | 39.1% |

The entire 17.6-point "gain" was an artefact. Any apparent benefit from sizing up came from the
same source. **There is no free lunch in the risk dial.**

## Economics

| risk | pass | days | fees | E[payout] | EV/attempt | break-even pass |
|---|---|---|---|---|---|---|
| 0.50% | 39.3% | 14 | $49 | $1,463 | +$467 | 3.7% |
| 0.75% | 39.9% | 8 | $49 | $1,538 | +$506 | 3.5% |
| **1.00%** | **41.7%** | **5** | $49 | $1,823 | **+$648** | **2.9%** |

Funded stage at 1%: **58.4% never pay out**, median $0, mean $1,823, p90 $5,881.

## Sequential attempts at 1.00%

| tries | spend | P(≥1 pass) | P(profit) | median | mean | p90 |
|---|---|---|---|---|---|---|
| 1 | $49 | 41.7% | 17.3% | −$49 | +$649 | +$3,148 |
| 3 | $94 | 80.2% | 33.1% | −$147 | +$1,240 | +$5,058 |
| **5** | **$109** | **93.2%** | **38.6%** | **−$198** | **+$1,447** | +$5,425 |
| 10 | $117 | 99.5% | 41.5% | −$198 | +$1,553 | +$5,608 |

**Positive EV, negative median.** Break-even is 2.9% against an actual 41.7% — a 14× margin — but
most individual attempts lose the fee, because 58% of funded accounts never produce a payout. The
expectancy sits in the ~25% of runs reaching several thousand.

## Standing caveats
- **Never paper traded.** A +0.025R edge against ±0.6R of measured exit noise has little room.
- The −$2,184 worst day is what overlapping positions do. This needs automation and a hard daily
  stop; a manual trader will not close five positions quickly enough.
- Edge is 87.5% likely positive on a day-clustered bootstrap, not established at 95%.
- 2026 is negative (−0.018R) but a permutation test gives p = 0.184 and 2020 was worse and
  recovered fully.

## Method note
Fourth correction to a published figure in this repo, and the fourth was an unverified assumption
rather than arithmetic. The pattern: a plausible mechanism stated without a test attached. Each one
cost minutes to check and produced a materially different answer.
