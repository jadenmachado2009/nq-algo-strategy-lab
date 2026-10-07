# Backtest — PB Stupid Simple (audit-fixed) MNQ — 2026-09-18

**Verdict:** Needs work — undecided on edge, unusable at this trade frequency

## Setup
| | |
|---|---|
| Strategy file | `execution/ibkr_paper/pb_engine.py` (imported unchanged by `quantconnect/pb_mnq.py`, `forward_replay.py` and the live bot) |
| Symbol / timeframe | MNQ continuous, 5m, 1H/4H context aggregated in-engine |
| Period | IS 2019-06-01 → 2023-12-31 · OOS 2024-01-01 → 2026-06-30 · forward Jul–Sep 2026 |
| QC projects | 36685780 (IS), 36685784 (OOS) |
| Commission / slippage | $0.62/contract/side · 1 tick/side |
| Parameters | retrace 0.5, SL 1.0×ATR below sweep low, RR 2.0, sweep ≤5 bars, IFVG ≤20 bars, FVG expiry 24 bars, 08:30–11:00 NY, 1% risk |

Audit fixes applied before testing (all covered by tests in `execution/ibkr_paper/tests/test_pb.py`, 27 passing):
liquidity sweep is now a required entry filter; IFVG takes the most recent gap and expires; 5m FVG zones expire; dead `entryPrice` removed.

## Results
| Metric | In-sample | Out-of-sample | Forward (10wk) | Bar |
|---|---|---|---|---|
| Trades | 29 | 17 | 2 | >100 |
| Trades per year | 6.3 | 6.8 | ~10 | — |
| Win rate | 31.0% | 52.9% | 2/2 | >50% |
| Profit factor | 0.87 | 1.83 | ∞ | >1.5 |
| Max drawdown | 8.0% | 3.1% | 0% | <15% |
| Net | −2.6% | +6.6% | +3.6% | |
| Avg win / avg loss | $806 / $416 | $846 / $520 | — | |

Combined IS+OOS: **PF 1.19 over 46 trades.**

## Issues
1. **Sample far too small to conclude anything.** 46 trades over 7 years. IS says 0.87, OOS says 1.83 — that spread is what noise looks like at n≈20, not evidence of an edge that appeared in 2024.
2. **~6 trades/year is not deployable.** Even if the edge were real, it would take years to prove on a paper account, and a prop evaluation would expire long before the sample matured.
3. **Modelling caveat inherited from the Pine version:** the IFVG is an approximation (true sub-minute inversion can't be read without repainting), so any PB number carries that asterisk.
4. Unlike CBE, nothing here says the idea is dead: the payoff shape is right (avg win ≈ 1.8× avg loss, drawdown small).

## Next action
Raise trade count *before* judging the edge, changing ONE thing at a time on in-sample only, then re-validating OOS untouched:
(a) relax the HTF-FVG containment (the most binding filter — price must sit inside a 1H/4H gap), or
(b) run the same engine across ES/YM/CL as well as NQ to multiply the sample without loosening the logic.
Prefer (b): it grows n without weakening the model.
