# Monte Carlo with the edge treated as unknown — 2026-10-19

**Verdict:** The sims were never the gap — this repo has run 40,000-path challenge simulations,
block-bootstrapped null tests and 2,000–20,000-rep confidence intervals throughout. The gap was
that **every one of them conditions on a known edge.** Correcting that barely moves the average
pass rate and completely removes any confidence in it: across the live data's own 95% interval
the pass rate spans **0.0% to 56.1%**.

## What was already Monte Carlo
| machinery | scale |
|---|---|
| `topstep.combine` / `funded` | 40,000 paths |
| `bankroll.payout_distribution` | 100,000 paths |
| `search.bootstrap` null tests | block-bootstrapped synthetic price paths |
| every CI in the repo | 2,000–20,000 day-clustered reps |

## What was added
1. **Parameter uncertainty.** Each path draws its own true edge from the day-clustered bootstrap
   distribution of the pool mean (bootstrap-as-posterior), rather than every path sharing the
   point estimate.
2. **Regime persistence.** Sessions resampled in multi-day blocks. 2026Q3 showed bad conditions
   lasting months; i.i.d. session draws cannot produce a two-month hole.
3. **Monte Carlo error** reported on every figure, so sub-point differences are not read as
   findings.

## Result — out-of-sample pool, 0.50% risk, 40,000 paths
| model | pass | MC se | days p50 | days p90 |
|---|---|---|---|---|
| fixed edge, i.i.d. sessions | 52.2% | 0.25 | 15 | 30 |
| + edge uncertainty | 51.4% | 0.25 | 15 | 29 |
| + 5-day blocks | 51.4% | 0.25 | 15 | 30 |
| + 21-day blocks | 54.9% | 0.25 | 17 | 31 |

- **Edge uncertainty alone: −0.8 pts.** Pass rate is close to linear in edge over the relevant
  range, so averaging a near-linear function over a symmetric spread lands near its middle. The
  point estimate of the *average* survives; confidence in it does not.
- **Regime persistence: +3.6 pts** with a positive edge — blocking raises effective variance,
  and variance helps reach a target under a ratcheting floor.

## Finding — persistence amplifies the sign of the edge
| pool | edge | i.i.d. | 21-day blocks |
|---|---|---|---|
| out-of-sample half | +0.0514R | 51.4% | **54.9%** |
| live tracker, 38 sessions | −0.1037R | 10.0% | **0.0%** |

Blocking helps a positive edge and is fatal to a negative one. Since the live data cannot
establish the sign (P(edge > 0) = 12.5%), this is the mechanism that makes waiting correct.

## The headline — pass rate against the one unmeasured input
Full-period session structure, 21-day blocks, 30,000 paths per point:

| true edge | −0.18 | −0.10 | −0.04 | 0.00 | +0.04 | +0.08 | +0.12 |
|---|---|---|---|---|---|---|---|
| pass | 0.1% | 5.1% | 19.7% | **37.3%** | 49.6% | 59.0% | 68.8% |

| interval | edge 95% CI | implied pass rate |
|---|---|---|
| seven-year history | [+0.0013, +0.0582] | 38% – 53% |
| **38 live sessions** | [−0.2860, +0.0701] | **0.0% – 56.1%** |

**Zero edge under these blocks passes 37.3%.** The seven-year history passes 44.7%. Seven years
of measured edge is worth about **seven points over a coin flip**, and 38 live sessions cannot
establish that the edge exists at all.

## Known bias in this model
Same-day trades are applied in **window order** (10, 20, 30, 45, 60) rather than true exit order,
because the padded session matrix carries no exit timestamps. That fires the $1,000 daily lockout
later than it should. Measured against `2026-10-13_edge_sensitivity.md` at a matched +0.0246R
edge on a matched pool: **44.7% here against 39.1% there, so this model reads ~5.6 points
optimistic.** Horizon is not the cause (120-day and 60-day runs agree to 0.1 pt). The relative
comparisons above are internal to one model and hold; the absolute levels are upper bounds.

Fixing it means recording a per-trade exit bar index through `orb_rescue.trades_no_target` and
sorting each session by it. Not done.

## Status
No change to the recommendation. The figure this produces — pass rate against true edge, with
both credible intervals drawn underneath — is the clearest single argument in the repo for why
funding now is premature: **the decision is governed by an input nobody has measured to better
than a 56-point span.**
