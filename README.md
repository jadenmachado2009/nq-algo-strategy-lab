# Pine Strategies

Local working repo for systematic strategy development. Pine Script for signal logic and TradingView-native testing; QuantConnect for multi-year validation.

```
strategies/     Pine Script strategy source
quantconnect/   LEAN/Python ports for multi-year backtesting
ninjatrader/    NinjaScript ports for free sim paper trading (Windows)
execution/      Paper-trading bots (ibkr_paper: MNQ via Interactive Brokers)
backtests/      Recorded results — one file per run, never overwrite
```

NQ futures testing without real money: see `NQ_TESTING.md`.

## Strategy inventory

| File | Concept | Status |
|---|---|---|
| `CBE_v1.pine` | Candle body exhaustion — fade a sequence of shrinking bodies | **Rejected on NQ** (PF 0.80 OOS, 2026-09-17) |
| `PB_StupidSimple_v1.pine` | ICT/PB — HTF FVG context + 5m FVG retrace + IFVG trigger | Audit fixes ported to `execution/ibkr_paper/pb_engine.py`; tested 2026-09-18 — **too few trades to judge** (~6/yr) |
| `htf_bias_strategy.pine` | 4H bias + 15m breakout | **Broken — cannot trade** |
| `patty_swing_strategy.pine` | Swing model | Not yet audited |

## Workflow

1. Write/fix signal logic in Pine, verify visually on chart.
2. Port to `quantconnect/` and run multi-year, multi-regime backtest.
3. Record the result in `backtests/` with the parameter set used.
4. Only strategies that clear the quality bar go near the live TradingView → FastAPI → MT5 pipeline.

The pipeline can already fire live orders. Nothing should be connected to it that hasn't cleared step 3.

## Quality bar

Before a strategy is considered validated:

- [ ] Commission set (0.05%+ FX, or realistic cash-per-contract for futures)
- [ ] Slippage set (1–2 ticks minimum)
- [ ] Sample size > 100 trades
- [ ] Tested across trending *and* ranging regimes
- [ ] Out-of-sample: optimise on first 70%, validate on last 30% — reject if OOS degrades > 30%
- [ ] No single trade contributes > 20% of net profit
- [ ] Robustness: PF holds when key parameters are varied ±20%

Targets: profit factor > 1.5, win rate > 50%, max drawdown < 15%, expectancy > 0.3R.
