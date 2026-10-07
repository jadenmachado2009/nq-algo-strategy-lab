# Backtest — CBE MNQ forward replay — 2026-09-17

**Verdict:** Reject (as currently specified)

## Setup
| | |
|---|---|
| Strategy file | `execution/ibkr_paper/cbe.py` via `forward_replay.py` (same code the paper bot runs) |
| Symbol / timeframe | NQ=F (Yahoo), sized as MNQ ($2/pt), 5m |
| Period | 2026-07-08 → 2026-09-16 (~10 weeks) |
| In-sample or out-of-sample | Forward / unseen — entirely after the QC OOS window (ends 2026-06-30) |
| Commission | $0.62/contract/side |
| Slippage | 1 tick entry and stop; stop assumed first when stop+target share a bar |
| Parameters | SEQ_LEN 3, MIN_BODY_ATR 0.1, ATR 14, SL 1.7×, TP 2.5×, 1% risk, 09:30–11:30 NY, max 4/day, $1k daily loss, flat 15:50 |

## Results
| Metric | Value | Bar | Pass? |
|---|---|---|---|
| Trades | 38 | >100 | No |
| Win rate | 39.5% | >50% | No |
| Profit factor | 0.89 | >1.5 | No |
| Max drawdown | 7.6% | <15% | Yes |
| Expectancy | −0.03R | >0.3R | No |
| Largest win as % of gross profit | 8.3% | <20% | Yes |

Net −$990 (−2.0%). Exits: 13 target, 21 stop, 4 end-of-day.

Robustness (each single change from base, same data): SL 1.4 → PF 1.03; SL 2.0 → 0.86; TP 2.0 → 0.89; TP 3.0 → 0.67; SEQ_LEN 4 → 5 trades, 0.52. No variant clears 1.5.

## Issues
1. No edge on unseen data: PF < 1 at base and PF ≤ 1.03 across all ±20% variants — not a parameter-luck problem.
2. Win rate 39.5% is below the ~41% breakeven implied by ~1.46R winners vs ~1.01R losers after costs.
3. 38 trades is below the 100-trade bar, so this is evidence against, not proof — but nothing here argues for spending 8 weeks paper trading it.

## Next action
Run `quantconnect/cbe_mnq.py` IS + OOS (2019–2026). If multi-year PF is also < 1.3, retire CBE on NQ rather than tuning it; if it passes there, this 10-week window is a regime flag worth investigating before any paper trading.
