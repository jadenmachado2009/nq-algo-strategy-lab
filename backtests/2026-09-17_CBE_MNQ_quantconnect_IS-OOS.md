# Backtest — CBE MNQ QuantConnect IS + OOS — 2026-09-17

**Verdict:** Reject — retire CBE on NQ

## Setup
| | |
|---|---|
| Strategy file | `quantconnect/cbe_mnq.py` (QC projects 36649889 IS, 36649890 OOS) |
| Symbol / timeframe | MNQ continuous (back-adjusted signals, OI-mapped contract for orders), 5m |
| Period | IS 2019-06-01 → 2023-12-31 · OOS 2024-01-01 → 2026-06-30 |
| Commission | $0.62/contract/side |
| Slippage | 1 tick/side |
| Parameters | SEQ_LEN 3, MIN_BODY_ATR 0.1, ATR 14, SL 1.7×, TP 2.5×, 1% risk, max 10 contracts, 09:30–11:30 NY, 2% daily loss, flat 15:50 |

No parameters were tuned — both runs use the defaults carried over from the FX port.

## Results
| Metric | In-sample | Out-of-sample | Bar | Pass? |
|---|---|---|---|---|
| Trades | 931 | 528 | >100 | Yes / Yes |
| Win rate | 40.1% | 38.6% | >50% | No / No |
| Profit factor | 0.90 | 0.80 | >1.5 | No / No |
| Max drawdown | 52.2% | 47.0% | <15% | No / No |
| Net profit | −45.8% | −43.8% | | |
| Avg trade (after fees) | ≈ −$24 | ≈ −$41 | | |
| Largest win as % of gross profit | 0.4% | 0.9% | <20% | Yes / Yes |
| Sharpe | −0.86 | −1.70 | | |

Forward replay on Jul–Sep 2026 (separate file) agreed: PF 0.89.

## Issues
1. PF < 1 in every window tested (2019–23, 2024–26, Jul–Sep 2026), across 1,500 trades — this is a real absence of edge, not noise.
2. Fading shrinking-body runs on NQ's NY open fights the index's trend days; losers aren't smaller than designed, winners just don't come often enough (39–40% vs ~43% breakeven at ~1.3R).
3. Earlier runs today were invalid: bracket orders never placed because backtest market orders fill inside `market_order()` before the ticket is assigned. Fixed (match entry by order tag) before these numbers were produced.

## Next action
Stop work on CBE for NQ. Do not tune it — with PF 0.80 OOS, any parameter set that passes would be curve-fit. Move to the next strategy in the inventory.
