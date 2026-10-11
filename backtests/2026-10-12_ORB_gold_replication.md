# ORB replicated on gold (XAUUSD -> GC/MGC) — 2026-10-12

**Verdict:** Passes the null test (p = 0.000). **Fails out-of-sample (−0.027R).** The combination is
the finding: it shows the null test's bar is lower than we had been reading it.

## Setup
| | |
|---|---|
| Tool | `research/orb_gold.py` |
| Data | Dukascopy XAUUSD 5m, 2019-01 → 2026-10, 551,536 bars (fidelity verified: 0.9835 / 0.996 vs GC) |
| Grid | 3 session opens × 6 windows × 3 directions = 54 configs |
| Costs | MGC, 0.324 pts round trip |
| Split | IS 2018-12 → 2024-06 / OOS 2024-06 → 2026-10, OOS touched once |

Three opens tested because gold has no single unambiguous one: 09:30 NY equity, 08:20 COMEX gold,
03:00 London. The null test ran over the whole 54-config grid, pricing the extra comparisons.

## Result

| | |
|---|---|
| Best in-sample | **+0.011R**, 928 trades, WR 64.2%, 09:30 NY equity / 30m / long |
| Noise mean | −0.061R |
| Noise max | −0.027R |
| **p-value** | **0.000** |
| **Out-of-sample** | **−0.027R ± 0.063**, 430 trades, WR 62.8%, PF 0.92 |

## What replicated

Three structural features carried over from NQ, which is not nothing:

1. **The 09:30 NY equity open won**, beating gold's own COMEX open (08:20) and London (03:00).
   Gold's best opening range is keyed to the equity session, consistent with macro flow.
2. **Long beat short at every window**, the same asymmetry found on NQ.
3. **Win rate ~64%**, where a 0.5:1 bracket belongs.

The shape is real. The magnitude is not tradeable.

## The methodological finding

ORB passed the null test and still lost money out of sample. Those are not contradictory, because
they ask different questions:

- **Null test:** is this better than what random search finds in *noise*? On gold, all 15 noise runs
  were negative (mean −0.061R) because noise pays the toll and gold's toll is heavy. The bar was
  therefore **−0.027R**. A mediocre +0.011R clears it easily.
- **Out-of-sample:** does it still work on data it never saw? No.

**The null test's bar is "beats noise after costs", not "is profitable."** On a high-cost instrument
that bar sits well below zero. This applies retroactively to NQ's p = 0.00, where noise averaged
−0.031R — that result also cleared a sub-zero bar.

A null test rules out *one* failure mode (data mining). It does not establish an edge. We had been
treating it as if it did.

## ORB across every instrument tested

| Instrument | In-sample | Null | Out-of-sample |
|---|---|---|---|
| NQ 5m | +0.034R | p = 0.00 | +0.011R ± 0.056 |
| **Gold 5m** | **+0.011R** | **p = 0.000** | **−0.027R ± 0.063** |
| ES 5m | −0.042R | — | — |
| YM 5m | −0.003R | — | — |

Both out-of-sample confidence intervals straddle zero. **ORB has no demonstrable out-of-sample edge
on any instrument tested.** The v4 claim that it is "the first strategy to pass the null test" is
true and much weaker than it reads.

## Impact
Pass probability stays at the zero-edge baseline. The Topstep economics are unchanged, and remain
positive-EV through convexity rather than edge.

## Next action
Not another instrument. Four now (NQ, ES, YM, gold) with the same answer. The open question is no
longer "which market" but whether anything in this strategy family survives real fills — which only
paper trading answers.
