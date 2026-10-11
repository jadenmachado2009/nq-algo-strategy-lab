# Does cash-index data misstate the opening range? — 2026-10-12

**Verdict: No. The earlier claim that it did was wrong, and this measures it.**

## The claim being tested
From 2026-10-10 onward this repo asserted that Dukascopy's NQ feed (which tracks the CASH
Nasdaq-100, +5 pts vs ^NDX, −97 vs NQ=F) corrupted the ORB study, because the cash index is computed
from 100 constituents that open staggered, making its first prints stale — precisely where an
opening-range strategy reads. That claim motivated the move to gold and is repeated in commit
16f22c9 and in `research/fetch_data.py`.

It was never measured. It is now.

## Method
Yahoo serves 60 days of real NQ=F 5m bars. Over the 38 shared sessions, build the opening range from
both sources and compare the range itself and the breakout signal it generates.

## Result

| Window | cash/futures width | width corr | signal agreement | phantom | missed |
|---|---|---|---|---|---|
| 10m | 0.990 | 0.9977 | 87% | 2 | 0 |
| 15m | 0.966 | 0.9979 | 89% | 1 | 0 |
| 20m | 0.998 | 0.9974 | 89% | 1 | 0 |
| 30m | 0.978 | 0.9971 | 89% | 1 | 0 |
| 45m | 0.978 | 0.9971 | 89% | 1 | 0 |
| 60m | 0.978 | 0.9971 | 89% | 1 | 0 |

Across 38 sessions at the 30m window: 24 fired within one bar of each other, 10 fired on neither,
3 fired a bar apart, 1 phantom, 0 missed.

## Reading it
The staleness hypothesis makes a sharp prediction: the distortion should be **worst at the shortest
window**, because that is where stale constituent prints make up most of the range. The 10m window
should be visibly worse than the 60m.

It isn't. Width ratio and correlation are flat across every window, and signal agreement varies by
two points with no trend. **The predicted effect is absent.**

Intraday index arbitrage is evidently tight enough, and the opening range wide enough (~150 pts),
that a few seconds of stale constituent prints do not move the high or low of a 10-minute range.

## What this corrects
- The cash-index data was a **fair proxy**. ORB's NQ numbers (+0.034R IS, +0.011R ± 0.056 OOS) are
  a reasonable measurement of what the futures would have produced.
- So ORB's weak out-of-sample result is **not a data artefact**. The simpler explanation holds:
  the edge is very small and does not persist.
- `2026-10-10_ORB_cross_instrument.md` and the fidelity rationale in `fetch_data.py` overweight the
  cash-index explanation. The ES/YM replication failures stand on their own evidence; the data
  provenance is not what caused them.

## What stands
- ORB has no demonstrable out-of-sample edge on four instruments (NQ +0.011±0.056, gold
  −0.027±0.063, ES −0.042, YM −0.003).
- The gold work remains worth having: a free, reproducible, fidelity-verified pipeline, plus the
  finding that a null test's bar sits below zero on a high-cost instrument.
- Fidelity still matters as a discipline — it was simply not the binding problem here.

## Method note
This is the second time a confident causal story in this repo failed on measurement (the first being
the zero-edge baseline). Both were cases of a plausible mechanism asserted without a test attached.
The cost of checking was one 60-day comparison.
