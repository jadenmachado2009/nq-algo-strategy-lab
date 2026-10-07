# The prop playbook: a strategy that fits the convexity maths

Built from DeltaTrend Trading's framing — a challenge account is a convex payoff, so optimise the
**risk geometry**, not the entry signal. Everything below assumes **no edge**, because three
independent searches found none, and random entries measured −0.015R.

Produced by `research/geometry_search.py`. Numbers are Monte Carlo, 20,000 paths per policy.

---

## Why a risk policy and not an entry signal

| Lever | Range tested | Effect on pass rate |
|---|---|---|
| Entry edge | −0.10R → +0.10R | 13% → 43% |
| Risk per trade | 0.75% → 5% | 29% → 2% |
| **Frozen-trail escalation** | off → on | **+$49 to +$73 EV per attempt** |

The entry edge is the lever we cannot move (nothing beat the null test). The other two we control
completely.

## The structural feature being exploited

A real futures trailing drawdown **stops rising** once you are far enough ahead:

```
dd_line = min(peak − D, cap)       cap = $0 (Topstep-style), +$100 (Apex-style)
```

- **Before the trail freezes:** every dollar of profit drags the liquidation level up behind you.
  A pullback kills you. Variance is expensive → trade small.
- **After it freezes:** profit is pure buffer, the floor never moves again. Variance is cheap →
  trade bigger.

A fixed-risk plan ignores this. The policy below does not — and that difference alone is worth
+$49 (Topstep-style) to +$73 (Apex-style) per attempt.

---

## The spec

**Entry:** any mechanical rule with no measurable edge is acceptable — that is the point. Use
something cheap and repeatable (e.g. opening-range break of the first 5m bar, or the Donchian-20
breakout already coded). What matters is the cost profile, not the signal.

**Costs:** stops must be wide. At a 1×ATR stop (~70 pts hourly, ~12 pts on 5m) cost drag is
0.016–0.097R per trade. At a 10-point stop it is 0.112R, which alone breaks the maths.

**Risk policy:**

| Rule | Setting |
|---|---|
| Base risk per trade | **0.75% of account** |
| Reward:risk | **2:1** (3:1 raises the pass rate slightly, 1:1 raises EV — see table) |
| Trades per day | **1** (more trades grind the trailing line for no benefit) |
| Once equity ≥ 60% of target | **halve risk to 0.375%** |
| Once the trail has frozen (peak ≥ D) | **raise risk ×1.5–2** |
| Stop trading | the moment the target is hit and min trading days are met |
| Daily | flat by the close, never hold overnight |

The two conditional rules are the whole edge of the playbook: *protect the run-up while the trail
is still chasing you, press once it has stopped.*

## Expected results (zero edge, −0.02R)

| Firm profile | Policy | Pass rate | Net EV per attempt |
|---|---|---|---|
| Topstep-like 50k | EV-best (1.00%, ×3 locked, ×0.5 near, RR 1) | 22.6% | **+$196** |
| Topstep-like 50k | Pass-best (0.75%, ×0.5 near, RR 3) | **31.1%** | +$162 |
| Topstep-like 50k | Balanced (0.75%, ×2 locked, ×0.5 near, RR 2) | 29.9% | +$146 |
| Apex-like 50k | EV-best (1.00%, ×2 locked, RR 1) | 30.1% | **+$408** |
| Apex-like 50k | Pass-best (0.60% fixed, RR 3) | **33.8%** | +$334 |

Apex-style scores higher mainly because there is no separate activation fee and the drawdown is
$2,500 rather than $2,000.

## Robustness: what if the strategy is worse than we think?

| True edge | Pass (balanced) | EV (balanced) | EV (pass-best) |
|---|---|---|---|
| 0.00R | 32.0% | +$180 | +$200 |
| −0.02R (measured for random entries) | 29.9% | +$146 | +$162 |
| −0.05R | 26.3% | +$93 | +$110 |
| −0.10R | 21.2% | +$24 | +$28 |

Still positive at −0.10R, which is worse than anything we have measured except CBE (−0.15R). The
geometry improvements pushed the break-even edge from −0.075R down to roughly **−0.12R**.

## Consistency rules

Checked explicitly: the share of total profit coming from the single best day, against a 50%
(Topstep-style) and 30% (Apex-style) cap. Every policy in the tables above passes **100%** of the
time except the aggressive RR-3 escalation variant (84%), which is why `EV(strict)` — EV assuming
consistency failures forfeit the account — is the ranking column in the tool.

Low risk per trade and one trade per day is what keeps this clean: no single day can dominate when
the target takes 6+ net winners to reach.

---

## What a positive EV actually means for you (`bankroll.py`)

EV per attempt is an average over many attempts. The payoff is a lottery: most attempts lose the
fee, a minority pay a few thousand. Apex-like profile, EV-best policy, zero edge:

| Attempts | Capital at risk | P(in profit) | Median | Mean |
|---|---|---|---|---|
| **1** | $167 | **22%** | **−$167** | +$411 |
| 5 | $835 | 71% | +$965 | +$2,032 |
| 10 | $1,670 | 84% | +$2,830 | +$4,035 |
| 20 | $3,340 | 93% | +$7,460 | +$8,082 |

Also: **27% of funded accounts never pay out at all**, and the median payout ($900) is less than
half the mean ($1,902) — the average is carried by a minority of good runs.

Treat each fee as spent money. One attempt is a losing bet 78% of the time.

## What this is not

1. **Not a profitable trading strategy.** It makes money from the *fee structure*, not the market.
   Expected value comes from a capped downside, not from forecasting.
2. **71% of attempts still fail.** The EV is an average over many attempts, each costing a real fee.
   Position this as a repeated game or not at all.
3. **The model omits:** scaling plans, payout waiting periods, platform fees, news-event rules,
   and the possibility that a firm simply changes its terms. One gap is known to matter: **Apex-style
   fees are a monthly subscription, not a one-off**, so an evaluation spanning two months costs
   double what these tables assume.
4. **Verify the real rules before paying anything.** The two profiles here are *stylised*. Actual
   trailing-drawdown mechanics, caps, consistency definitions and fees differ per firm and change.
5. **Age:** funded accounts require you to be 18+, and contracts with minors are void. Settle who
   signs and who receives payouts before any of this matters.

## Next test before any money moves

Re-run `geometry_search.py` with the **exact** published terms of the specific firm being
considered, including its scaling plan and payout schedule. If EV survives that, the spec above is
the one to trade.
