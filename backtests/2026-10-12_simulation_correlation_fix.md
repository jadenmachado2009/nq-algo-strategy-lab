# Correlated trades, and two bugs in v5 — 2026-10-12

**Verdict:** v5's pass rate (43.5%) was approximately right. Its **days-to-pass (54) was wrong by
3.6x** — the correct figure is **15**. Two code bugs and one methodological error, all fixed.

## Error 1 — simulations assumed independent trades

Every pass-rate figure in this repo drew `trades_per_day` INDEPENDENT samples from the pooled
R-multiple distribution. ORB's windows are nested on the same price path, so they are nothing like
independent:

| | observed | if independent |
|---|---|---|
| all same-day trades same sign | **67.5%** | 3.8% |
| all winners | 45.4% | — |
| all losers | 22.1% | — |

Correct method: resample whole SESSIONS and replay that session's actual trade set, preserving the
correlation. Every figure below uses session resampling.

## Error 2 — HHMM arithmetic in orb.py

```python
open_end = RTH_OPEN + (window_min // 60) * 100 + (window_min % 60)   # w=45 -> 975
```

975 is not a valid time. No 5-minute bar falls in the 960–999 band, so **every window from 35 to 55
silently collapsed onto the 30-minute range.** The canonical set (10, 20, 30, 45, 60) therefore
contained a DUPLICATE — 45m was byte-identical to 30m, double-counted in every pooled figure.

Fixed to work in minutes. Corrected pooled figures (all slightly BETTER):

| | v5 published | corrected |
|---|---|---|
| trades | 7,072 | **6,995** |
| full-period edge | +0.0227R | **+0.0246R** |
| out-of-sample edge | +0.0297R | **+0.0316R** |

## Corrected pass rates — 5 windows, session resampling

| risk | pass (DLL on) | pass (DLL off) | median days |
|---|---|---|---|
| **0.50%** | **43.9%** | 39.0% | **15** |
| 0.75% | 49.8% | 39.6% | 8 |
| 1.00% | 56.7% | 39.1% | 6 |
| 1.50% | 54.3% | 36.4% | 5 |

v5 published **43.5% in 54 days** at 0.50%. The pass rate holds; the duration does not.

## Error 3 — the "11 windows" optimisation was an artefact

Adding windows appeared to give 46.7% in 15 days. Under session resampling it appears even better
(61.8%), but decomposing it shows why:

| 11 windows, 0.50% | pass |
|---|---|
| full rules | 61.8% |
| **no daily loss limit** | **40.1%** |

**The daily loss limit is worth +21.8 points.** With ~10 correlated trades a bad day is clipped at
−$1,000 while a good day runs to +$1,381 — an asymmetry created by the rule, not by the edge.

That benefit requires the lockout to intervene **between** losses. With 11 overlapping positions a
single adverse move hits them together and it cannot. The honest bracket:

| | DLL intervenes | DLL cannot |
|---|---|---|
| 11 windows | 61.8% | **40.1%** |
| 5 windows | 43.9% | **39.0%** |

**The 5-window spec is robust (39–44%); the 11-window spec is fragile (40–62%).** Recommend 5
windows: its result does not depend on an unverifiable assumption about lockout timing.

## What stands
- ORB's edge: +0.0246R full period, +0.0316R out-of-sample, 87.5% likely positive
- No detectable decay (permutation p = 0.184)
- Data fidelity 0.9840 vs real NQ futures
- EV per attempt positive at every plausible edge; break-even 4.1%

## Method note
Third time a confident figure in this repo failed on checking. All three were unverified
assumptions, not arithmetic: a default argument (apex vs topstep), two numbers that looked
comparable (single-config vs pooled OOS), and now an independence assumption that was never true.
Independence should be TESTED, not assumed, whenever trades share a price path.
