# Edge sensitivity, and the correct zero-edge baseline — 2026-10-13

**Why this exists:** earlier records implicitly benchmarked ORB's ~39% pass rate against 40%, the
gambler's-ruin value `D/(G+D) = 2000/5000`. That figure assumes a **static** floor. Topstep's floor
trails and locks at breakeven, which is strictly harsher, so 40% was never the right comparison and
ORB's result looked worse than it is.

## Method
The exact model (sessions replayed in true exit order, no INFLIGHT parameter). Every trade in the
pool is shifted by a constant so the pool mean equals a target edge, leaving the within-session
correlation structure untouched.

## Result

| true edge | pass @ 0.50% | pass @ 1.00% |
|---|---|---|
| −0.0500 | 18.1% | 27.6% |
| −0.0200 | 26.2% | 32.4% |
| **0.0000** | **31.9%** | 35.7% |
| **+0.0246 (ORB)** | **39.1%** | 39.8% |
| +0.0500 | 46.7% | 44.5% |
| +0.1000 | 60.6% | 52.0% |
| +0.2000 | 80.9% | 63.0% |

Monotonic in edge at both risk levels, which is the basic sanity check this model had not previously
been given.

## Finding 1 — the correct baseline is 31.9%, not 40%

```
zero edge under Topstep's real rules    31.9%
ORB's measured +0.0246R                 39.1%
                                        ------
the edge is worth                       +7.2 points
```

The trailing-and-locking floor costs roughly 8 points against the static-floor textbook value.

## Finding 2 — smaller bets make an edge count for more

| | zero edge | ORB | edge is worth |
|---|---|---|---|
| 0.50% risk | 31.9% | 39.1% | **+7.2 pts** |
| 1.00% risk | 35.7% | 39.8% | +4.1 pts |

Larger bets raise the zero-edge floor (variance alone gets you to target more often) but compress
what skill adds. This corrects the earlier claim that "there is no free lunch in the risk dial."

**Accurate statement:** with a SMALL edge the risk dial barely matters, because variance dominates
either way — which is why ORB looked flat across risk. With a REAL edge, smaller bets are clearly
better: at +0.10R it is 60.6% at 0.50% against 52.0% at 1.00%.

This is a third independent reason to run 0.50%, alongside funded-account survival (36.7% never pay
out vs 60.3%) and the worst day staying inside the $2,000 limit.

## Implication
If live trading shows the edge is nearer +0.05R than +0.025R, the correct response is to **lower**
risk, not raise it. The payoff to edge improvement is steepest at small bet sizes.
