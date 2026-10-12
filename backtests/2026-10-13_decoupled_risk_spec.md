# The decoupled spec — fast challenge, small funded — 2026-10-13

**This is the current recommended configuration.** It beats every single-risk setting on speed,
probability of profit, median outcome and cost simultaneously.

## The idea
The challenge and the funded account reward **opposite** things, and there is no reason to size them
the same:

- **Challenge rewards speed.** Pass rate is scale-invariant (gambler's ruin), so betting larger costs
  nothing in probability while collapsing 29 days to 5.
- **Funded account rewards survival.** The trailing drawdown locks at breakeven, so small size keeps
  you alive to collect repeated payouts.

## The spec
| | |
|---|---|
| Strategy | ORB on NQ, 5 windows (10/20/30/45/60), long only, 0.5:1 bracket |
| **Challenge risk** | **1.25%** of account (~$625) |
| **Funded risk** | **0.30%** of account (~$150) |
| Instrument | MNQ, integer contracts, per-trade stop sizing |
| Plan | 5 sequential attempts, stop after the first pass |

## Result

| | 0.50% throughout | 1.25% throughout | **decoupled 1.25% → 0.30%** |
|---|---|---|---|
| median days to pass | 29 | 5 | **5** |
| P(≥1 pass in 5) | 93.9% | 92.9% | **92.9%** |
| total spend | $215 | $111 | **$111** |
| funded never pays | 25.1% | 60.2% | **17.4%** |
| **P(end in profit)** | 66.5% | 37.0% | **73.9%** |
| **median outcome** | +$836 | −$198 | **+$1,068** |
| mean outcome | +$1,259 | +$1,479 | +$1,419 |

## Full outcome distribution

| outcome | probability |
|---|---|
| lose > $300 | 2.4% |
| lose $0–300 | 23.5% |
| make $0–500 | 9.5% |
| make $500–1,500 | 24.8% |
| make $1,500–3,000 | 23.3% |
| make $3,000–6,000 | 14.9% |
| make > $6,000 | 1.5% |

p10 −$245 · p90 +$3,741

## Funded-phase risk is sharply optimal at 0.30%

| funded risk | $ budget | trades affordable | never pays | median outcome |
|---|---|---|---|---|
| 0.15% | $75 | 9.8% | 97.6% | −$247 |
| 0.20% | $100 | 17.5% | 40.0% | −$41 |
| 0.25% | $125 | 27.0% | 25.4% | +$484 |
| **0.30%** | **$150** | **36.5%** | **17.4%** | **+$1,068** |
| 0.40% | $200 | 54.4% | 20.5% | +$1,019 |
| 0.50% | $250 | 68.7% | 25.1% | +$906 |
| 0.75% | $375 | 88.3% | 40.9% | +$384 |

**Do not go below 0.30%.** At 0.15% a $75 budget cannot buy a single MNQ contract (median stop is
94 points = $188/contract), so the account simply stops trading and never reaches the five winning
days a payout requires.

## Why this was not found earlier
Every prior analysis swept a SINGLE risk number applied to both phases. The two phases were never
treated as independent decisions. Nothing about the firm's rules forces them to match.

## Caveats
- Never paper traded. +0.025R against ±0.6R of measured exit noise.
- Assumes Topstep's published payout rules (5 winning days ≥$150, 50%/$2,000 payout cap, 90/10).
- Contract sizing uses the real per-trade ORB stop distance (median 94 pts) and integer MNQ lots.
