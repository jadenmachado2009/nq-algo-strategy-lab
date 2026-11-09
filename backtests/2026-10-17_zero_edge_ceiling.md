# How far the no-edge maths goes, and where it stops — 2026-10-17

**Verdict:** The zero-edge ceiling is **40.0%** and it is unreachable. Measured configurations span
~26% to ~37%. The entire gap is the cost of the end-of-day ratchet, and the only lever is fewer
ratchets. Maximising it is self-defeating: the same change that lifts the no-edge rate collapses what
an edge is worth.

## 1. Why 40% is the wall
Static gambler's ruin, `P = D/(G+D) = 2000/5000 = 40.0%`. Under a **static** floor and zero edge,
pass probability is *scale-invariant* — bet size cannot change it at all. So 40% is the whole no-edge
story, and nothing about sizing, targets or instruments touches it.

## 2. The gap is entirely the ratchet
Topstep's floor is `min(eod_peak − 2000, 0)`: it steps up after every profitable day. Every point
below 40% is ratchet cost, so the only lever a no-edge trader has is to **finish in fewer days**.

| zero-edge pass | configuration | source |
|---|---|---|
| 25.8% | 0.50% risk, 4 trades/day, independent draws | this study |
| **31.9%** | 0.50% risk, session replay (true exit order) | `2026-10-13_edge_sensitivity` |
| 34.4% | 1 NQ @ 50pt, 1 trade/day, $1,000 risk | `2026-10-11_half_R_coinflip` |
| ~35–37% | $1,500/trade, 1 trade/day | this study |
| 40.0% | static-floor ceiling | textbook |

The 25.8% vs 31.9% difference is the **model, not the rules**: independent draws understate daily
variance, and daily variance is what carries a no-edge account to target.

| | |
|---|---|
| real zero-edge session sd | **2.315R** (405 sessions, 4.52 trades/session) |
| same trades drawn independently | 1.318R |
| analytic √n × per-trade sd | 1.308R (confirms the simulator) |
| clustering inflates daily sd | **1.76×**, i.e. variance **3.1×** |

## 3. Two-phase decomposition — where the game is lost
The floor **pins at breakeven**: once the end-of-day peak reaches +$2,000, `min(peak−2000, 0) = 0`
forever. From that moment it is a static barrier, so phase 2 is exactly `2000/3000 = 66.7%` and **no
sizing decision can improve it.**

| risk | P(reach +$2,000 EOD peak) | × 66.7% | actual pass | residual |
|---|---|---|---|---|
| 0.50% | 38.2% | 25.4% | 25.8% | +0.4pt |
| 1.00% | 40.1% | 26.7% | 28.5% | +1.8pt |
| 2.00% | 40.6% | 27.0% | 27.3% | +0.2pt |
| 3.00% | 44.8% | 29.9% | 23.1% | **−6.8pt** |

The identity holds to within 2 points up to 2% risk and breaks at 3%, where the consistency rule
starts raising the target above $3,000 and the decomposition no longer applies.

**So roughly 60% of all no-edge failure happens before the floor ever locks**, and a 6× change in bet
size moves that first phase only 38.2% → 44.8%. That narrow band is the whole available room.

## 4. Three rules cap it, all deliberately
- **Consistency self-tightens.** `required = max(3000, best_day/0.50)`. At ≥5% risk the simulator
  saturates near 29% because a two-day pass becomes arithmetically impossible: day 2's gain exceeds
  50% of the total and so raises the bar above where you landed. The rule exists to kill exactly the
  lottery play that maximises the no-edge rate.
- **Cost drag compounds per trade.** Taking every signal (~66/day) fails ~98% at any size.
- **The DLL is optionality, not a penalty** — it truncates a day at −$1,000 without ending the
  account — but it also caps how fast the climb can happen.

## 5. The reason not to maximise it
Same trades, same sizes, edge removed by subtracting the pool mean:

| risk | zero edge | real edge (+0.0514R) | edge is worth |
|---|---|---|---|
| 0.50% | 25.8% | 72.8% | **+46.9 pts** |
| 1.00% | 28.5% | 55.2% | +26.7 pts |
| 2.00% | 27.0% | 40.8% | +13.8 pts |
| 4.00% | 17.8% | 26.5% | +8.8 pts |
| 6.00% | 15.9% | 24.3% | +8.4 pts |

Absolute values are inflated by the independence assumption, which helps a positive edge and hurts a
zero one. The session-replay version on record shows the same direction at smaller magnitude: edge
worth **+7.2 pts at 0.50%** against **+4.1 pts at 1.00%**.

**Every step toward maximising the no-edge rate converts the account into a coin flip.** Betting 12×
larger buys ~10 points of zero-edge pass rate and gives up roughly five-sixths of what skill is
worth. The no-edge optimum is only the right objective for someone who is certain they have no edge.

## 6. And it does not make money
Five independent accounts, end to end, zero edge (`2026-10-11_half_R_coinflip`):
mean **+$830**, median **−$81**, P(net > 0) **47%**. The positive mean exists only because the firm
absorbs trading losses while the downside is capped at fees. That is a 47% coin flip with a long
right tail, not income.

## 7. Tested today and rejected
**Flat dollar risk instead of flat fraction of equity.** The hypothesis was that %-of-equity sizing
makes day 2 larger than day 1, which trips the consistency rule and blocks the minimum two-day pass.
Measured: the two are within ~1 point everywhere (e.g. $1,500/trade, 1/day: 35.1% flat-dollar vs
34.9% flat-fraction). The effect is real only at sizes large enough to finish in two days, which is
also where the consistency rule saturates the result anyway. **Hypothesis wrong, no change.**
