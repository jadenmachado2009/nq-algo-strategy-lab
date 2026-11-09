# The trade-off: days against skill, and where the spec should sit — 2026-11-10

**Verdict:** Expected days to a funded account and the share of that result attributable to edge
are the two ends of one curve. There is no third axis. **0.75R at $250/trade** is the right point:
27 expected days against the current spec's 36, with a *higher* skill contribution, not a traded-off
one. Two unrelated criteria have now selected 0.75R.

## Method
For each (target, bet size) the Topstep 50K challenge is simulated twice on the same sessions — once
with the measured edge, once with the pool mean subtracted so the edge is exactly zero. The gap is
what skill is worth. Session replay, 21-day blocks, 30,000 paths, four seeds averaged.

`E[days to funded] = median days per attempt / pass rate`, because a failed attempt costs the
attempt and not a new fee — the $49/month runs either way.

## The frontier

| ORB 0.75R | E[days] | skill worth | a coin flip gets |
|---|---|---|---|
| $62/trade | 202 | +40pt | 20% |
| $150 | 60 | +20pt | 33% |
| **$250** | **27** | **+15pt** | 33% |
| $400 | 11 | +9pt | 44% |
| $500 | 10 | +8pt | **53%** |

At $500 a trader with no edge at all passes **52.5%**. Most of that pass rate is the firm handing
out variance, not the strategy earning anything.

**0.75R dominates 0.50R at every size tested** — fewer days *and* more skill, not a trade:

| size | 0.50R | 0.75R |
|---|---|---|
| $62 | 328d / +32pt | 202d / +40pt |
| $150 | 92d / +17pt | 60d / +20pt |
| $250 | 36d / +11pt | **27d / +15pt** |

## Finding — the response surface is stepped, not smooth
A reproducible hole at **$320/trade**: skill contribution collapses to **+2.9pt**, against +12.4pt
at $290 and +10.6pt at $360. The zero-edge pass rate jumps from 32.7% to 42.3% between $290 and
$320 while the with-edge rate stays flat.

It appears in **all three** target curves at the same dollar figure, survived four seeds and 120,000
paths per point with standard errors under 0.15pt. It is not sampling noise — an earlier read of
this as noise on a single seed was wrong.

Cause: the rules are denominated in fixed dollars ($3,000 target, $2,000 MLL, $1,000 DLL) and so is
the bet, so the number of losses that trip each threshold changes in steps. **Test the exact size
you intend to trade; never read a value off the curve between tested points.**

## Why a bigger edge matters more than it looks
| | edge | size | zero-edge rate | skill worth |
|---|---|---|---|---|
| `ayaantrades` "Enhanced" (published figures) | +0.0795R | 1 MNQ (0.12%) | 14.7% | **+55.3pt** |
| ORB, best spec | +0.0304R | $250 (0.50%) | 32.5% | +15.3pt |

A larger edge does not simply raise the odds — **it buys the right to bet small**, which is what
makes a pass rate skill-driven rather than variance-driven. ORB cannot reach that corner: at 0.12%
risk it does not reach target before the horizon expires.

Closing that gap is **entry selectivity**, not exits — the October sweep showed out-of-sample
expectancy is flat (+0.040R to +0.066R) across every target from 0.25R to 2.00R. With 1,499 sessions
any filter chosen now carries a serious fitting risk. It is a project, not a parameter.

## End-to-end value of the recommended spec
0.75R, 0.50% risk, Topstep 50K, challenge through funded, fees included:

| | |
|---|---|
| Pass | 55.7%, median 32 days |
| Payout if funded | median $1,625, mean $2,065 |
| Never paid at all | 19.1% |
| EV per attempt | **+$969** |
| Weighted by P(edge > 0) = 54.9% | **~+$532** |

## Status
Spec updated to 0.75R, flat at 16:00 ET, $250/trade. **Not a recommendation to trade today** — the
tracker reads MARGINAL and the edge is not established.
