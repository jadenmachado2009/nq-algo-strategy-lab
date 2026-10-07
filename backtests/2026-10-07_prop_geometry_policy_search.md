# Risk-policy search (prop geometry) — 2026-10-07

**Verdict:** Pass — first positive result in the project, and it does not depend on having an edge.

## Setup
| | |
|---|---|
| Tool | `research/geometry_search.py` |
| Trade distribution | zero-edge, −0.02R (what random entries measured on real NQ) |
| Paths | 20,000 per policy |
| Policy space | base risk × locked-multiplier × near-target multiplier × RR × trades/day = 256 policies |
| Firm profiles | Topstep-like 50k (trail $2,000 freezing at $0, 50% consistency, $314 fees) · Apex-like 50k (trail $2,500 freezing at +$100, 30% consistency, $167 fee) |

## Results (Topstep-like)
| Policy | Pass rate | Net EV (consistency-adjusted) |
|---|---|---|
| Best fixed risk (0.75%, RR 3) | 29.7% | +$147 |
| **Best adaptive (1.00%, ×3 after trail freezes, ×0.5 near target, RR 1)** | 22.6% | **+$196** |
| Highest pass rate (0.75%, ×0.5 near target, RR 3) | **31.1%** | +$162 |

Apex-like: best adaptive +$408 at 30.1% pass; best fixed +$334 at 33.8%.

Gain purely from exploiting the frozen trailing drawdown: **+$49 (Topstep-like), +$73 (Apex-like)** per attempt.

## Robustness
Still EV-positive at a true edge of −0.10R (+$24), versus a previous break-even of −0.075R under
fixed risk. Measured inputs for comparison: random entries −0.015R, CBE −0.05R in-sample and
−0.11R out-of-sample (the −0.16R figure quoted earlier came from a 41-trade forward replay and is
too small a sample to represent the strategy).

Consistency rule (largest day as a share of total profit) holds 100% for all recommended policies;
only the aggressive RR-3 escalation variant drops to 84%, and the tool ranks by EV assuming those
failures forfeit.

## Issues
1. Firm profiles are stylised. Real terms, scaling plans and payout schedules must replace them
   before this is actionable.
2. Trades are i.i.d. draws; clustered losing streaks would lower pass rates.
3. 71% of attempts still lose the fee — this is a repeated game or nothing.
4. A bug found and fixed during this run: the frozen trail is `min(peak − D, cap)`, not `max(...)`.
   The wrong sign made the account fail on any dollar of drawdown and understated every policy.

## Next action
Re-run with one specific firm's exact published terms. If EV survives, this is the spec to trade —
see `research/PROP_PLAYBOOK.md`.
