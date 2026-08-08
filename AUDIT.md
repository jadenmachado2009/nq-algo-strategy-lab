# Strategy Audit — 2026-08-09

Code read of every strategy in `strategies/` before any backtesting. Findings ordered by severity.

---

## 1. `htf_bias_strategy.pine` — FATAL: this strategy cannot ever open a trade

```pine
h4_high_prev = request.security(syminfo.tickerid, "240", high[1],  ...)   // high  of previous 4H bar
h4_low_prev  = request.security(syminfo.tickerid, "240", low[1],   ...)   // low   of previous 4H bar
h4_close     = request.security(syminfo.tickerid, "240", close[1], ...)   // close of previous 4H bar

h4_bull = h4_close > h4_high_prev    // close[1] > high[1]
h4_bear = h4_close < h4_low_prev     // close[1] < low[1]
```

All three `request.security` calls read the **same bar** — index `[1]`. A candle's close can never exceed its own high, and never fall below its own low. So:

- `h4_bull` is always `false`
- `h4_bear` is always `false`
- therefore `long_condition` and `short_condition` are always `false`

**The strategy takes zero trades.** If you ran this and saw an empty Strategy Tester, this is why — it isn't a data or session problem.

The intent was clearly "current 4H close broke above the *prior* 4H high", which needs a one-bar offset between the close and the level it's compared against:

```pine
h4_high_prev = request.security(syminfo.tickerid, "240", high[2],  ...)   // high  of the bar BEFORE last
h4_low_prev  = request.security(syminfo.tickerid, "240", low[2],   ...)
h4_close     = request.security(syminfo.tickerid, "240", close[1], ...)   // close of the last closed bar
```

Fixed version written to `strategies/htf_bias_strategy_fixed.pine`. Unverified — it now *can* trade, which means it now needs a real backtest.

Second issue in the same file: `default_qty_type = strategy.percent_of_equity` with `default_qty_value = 1` sizes every trade at 1% of equity as *notional*, not 1% risk. That is not risk-based sizing and will not correspond to how a prop account is evaluated.

---

## 2. `PB_StupidSimple_v1.pine` — liquidity sweep is computed, plotted, and then ignored

```pine
liqSweepLong  = low  < swingLow[1]  and close > swingLow[1]
liqSweepShort = high > swingHigh[1] and close < swingHigh[1]
```

Both are calculated (L202–203) and plotted as chart markers (L267–268), but neither appears in the entry conditions:

```pine
longCondition  = inSession and htfBullContext and bull5_valid and priceInBull5FVG and bullIFVG
shortCondition = inSession and htfBearContext and bear5_valid and priceInBear5FVG and bearIFVG
```

Liquidity sweep is a core part of the ICT model this is meant to implement. Right now it's decorative — you are visually seeing sweep markers on the chart and may be crediting the strategy with a filter it does not apply. Either add `and liqSweepLong` / `and liqSweepShort` to the entry conditions, or delete the plots so the chart stops implying a filter that isn't there.

**Second issue — the IFVG detector latches.** `ifvg_bear_top` is declared `var` (persists across bars), and the scan is guarded by `na(ifvg_bear_top)`:

```pine
for i = 1 to 5
    if high[i] < low[i + 2] and na(ifvg_bear_top)
        ifvg_bear_top := low[i + 2]
        ...
```

Once set, it stays set until an inversion fires and resets it to `na`. So the strategy can be waiting on an FVG from hundreds of bars ago while fresher, more relevant ones form and are ignored. Combined with the 5-bar scan window, the IFVG trigger is far less responsive than the code reads at a glance. Add an age-based expiry.

**Third — dead variable.** `entryPrice` is assigned on every entry and never read.

**Fourth — flagged in your own comments.** L146–155 concedes the IFVG is an approximation and that true IFVG "cannot be read in real-time without repainting". That's an honest note, and it means backtest results for this strategy carry a modelling caveat that must be recorded alongside the numbers.

---

## 3. `CBE_v1.pine` — `seqLen` does not do what its name says

Input is labelled "Sequence Length", range 2–6:

```pine
seqLen = input.int(3, 'Sequence Length', minval = 2, maxval = 6)

lBody1 = open[seqLen]     - close[seqLen]
lBody2 = open[seqLen - 1] - close[seqLen - 1]
lBody3 = open[seqLen - 2] - close[seqLen - 2]
```

Only ever three candles are examined, regardless of `seqLen`. The parameter is an **offset**, not a length — at `seqLen = 6` the strategy inspects bars 6, 5, 4 and ignores bars 3, 2, 1, 0 entirely, trading on a pattern that finished four bars ago.

This matters for optimisation: sweeping `seqLen` is not testing sequence length, it's testing staleness. Almost certainly it should be a genuine length with a loop.

**Second issue — no session filter.** Your stated focus is NY session intraday; this trades around the clock. On FX that means Asian-session chop is in the sample.

**Third — sizing makes percentage metrics meaningless.** `initial_capital = 1000000` with `default_qty_value = 2` contracts. Net profit % and drawdown % will both be near zero and tell you nothing. Judge this one on expectancy per trade and profit factor, or set capital to something realistic for a prop account.

Commission (`$2.5/contract`) and slippage (2 ticks) are set correctly — better than most.

---

## 4. `patty_swing_strategy.pine` — not audited

460 lines, out of scope for this pass. Audit before backtesting.

---

## Cross-cutting

**None of these have been validated out-of-sample**, and the TradingView → FastAPI → MT5 pipeline is already built and capable of placing live orders. The gap between "signal logic exists" and "signal logic has a demonstrated edge" is the entire risk here. Backtest before anything is wired to execution.
