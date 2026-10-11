# ORB cross-instrument replication — NQ vs ES vs YM — 2026-10-10

**Verdict:** FAILS to replicate. The ORB edge is NQ-specific. It is negative on ES and flat on YM.

## Why this test
Out-of-sample *in time* (ORB's original test) reuses the same instrument, so a result can still be an
artefact of one market's microstructure. Replication on a *different but correlated instrument* is a
stronger test: ES, NQ and YM trade the same session, the same hours, the same participants and the
same macro. If opening-range breakouts captured a general behavioural effect, it should appear on all
three.

## Setup
Identical rules, identical period, long only, 5 windows (10/20/30/45/60) pooled.
Costs modelled per instrument on the micro contract:

| | $/point | tick | commission (pts/side) | round trip |
|---|---|---|---|---|
| MNQ | $2.00 | 0.25 | 0.31 | 1.12 pts |
| MES | $5.00 | 0.25 | 0.124 | 0.75 pts |
| MYM | $0.50 | 1.00 | 1.24 | 4.48 pts |

Data: Dukascopy 5m, 2019-01 → 2026-10, ~531k bars each. Price scales verified independently
(NQ 6,130–31,361 / ES 2,185–7,843 / YM 18,186–54,737).

## Result

| Instrument | n | WR | exp(R) | 95% CI | cost drag |
|---|---|---|---|---|---|
| **NQ (MNQ)** | 7,063 | 65.4% | **+0.022** | [+0.007, +0.038] | 0.010R |
| **ES (MES)** | 7,463 | 62.8% | **−0.042** | [−0.058, −0.027] | 0.034R |
| **YM (MYM)** | 6,862 | 63.4% | **−0.003** | [−0.018, +0.012] | 0.023R |

Win rates are nearly identical across all three (62.8–65.4%). The expectancy is not.

## Reading it

**1. Cost structure explains much, but not all, of the spread.** Adding the drag back:

| | net | + drag | ≈ gross |
|---|---|---|---|
| NQ | +0.022 | 0.010 | +0.032 |
| YM | −0.003 | 0.023 | +0.020 |
| ES | −0.042 | 0.034 | −0.008 |

The ordering of cost drag matches the ordering of results exactly. NQ is the cheapest index to trade
relative to its own volatility — the 60m range is ~117 pts against 1.12 pts of cost. YM pays 4.48 pts
round trip because its tick is a whole point and MYM is only $0.50/point. **Part of NQ's "edge" is
simply that NQ is the cheapest of the three to trade**, not that the pattern is stronger there.

**2. Even gross, ES is negative.** So it is not purely a cost story. On gross terms NQ (+0.032) still
leads YM (+0.020) and ES (−0.008).

**3. The narrowest windows degrade worst.** On ES the 10m window is −0.065R vs −0.027R at 60m. A
narrower range means a smaller stop, so a fixed cost is a larger fraction of R. Consistent with the
cost explanation.

## Impact on the ORB case

This is a genuine weakening, and it should be stated plainly:

- ORB passed its null test on NQ (p = 0.00) and was positive in 6 of 8 years. That still stands.
- But it does **not** replicate on the two most closely related instruments. Out-of-instrument
  replication is a harder test than out-of-sample-in-time, and ORB did not pass it.
- The honest reading: ORB on NQ is a *thin, cost-sensitive, instrument-specific* edge. It may be real
  and particular to NQ's higher volatility-to-cost ratio. It may also be that searching NQ and finding
  ORB on NQ was itself a selection, and +0.022R with CI [+0.007, +0.038] is what that looks like.
- It does **not** overturn the NQ result. It does mean the NQ result should not be described as a
  general market-structure effect.

## Note on the search_5m cost guard
`search_5m.py` aborts when cost drag at a **1×ATR stop** exceeds 0.2R. That reference is wrong for
ORB, whose stop is the opening-range width (~10x a 5m ATR). The guard fired spuriously on ES (0.288R)
and YM (0.229R) despite both price scales being correct. Drag here is measured against ORB's actual
stop distance instead. The guard remains correct for the ATR-stop searches it was written for.

## Next action
Unchanged, and now more important: paper trade NQ only, and compare realised R against +0.022R.
An edge this thin and this cost-sensitive is precisely the kind that does not survive real fills.

Tool: `scratchpad/cross2.py` (per-instrument cost patching over `research/orb.py`)
