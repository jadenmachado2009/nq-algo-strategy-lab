"""
CBE — Candle Body Exhaustion. QuantConnect/LEAN port of strategies/CBE_v1.pine

Concept: a run of N consecutive same-direction candles whose bodies shrink
monotonically signals exhaustion; fade it. ATR-based stop and target.

Differences from the Pine original, all deliberate — see AUDIT.md:

  1. seq_len is a REAL sequence length here. In the Pine version it was an
     offset: three candles were always examined, and raising seqLen just moved
     the window further into the past (at seqLen=6 it traded a pattern that had
     finished four bars earlier). Sweeping it there tested staleness, not
     sequence length. Here seq_len=N examines N consecutive candles ending on
     the bar that just closed.

  2. Optional NY-session filter. The Pine version traded around the clock,
     which puts Asian-session chop in the sample for an intraday FX model.

  3. Capital sized so percentage metrics mean something. The Pine version ran
     $1,000,000 against 2 contracts, which drives net-profit-% and drawdown-%
     to near zero and makes both unreadable.

  4. IS/OOS split is explicit. Optimise on IN_SAMPLE, then re-run untouched on
     OUT_OF_SAMPLE. If profit factor degrades >30%, the edge is fitted.
"""

from AlgorithmImports import *


# ── Configuration ────────────────────────────────────────────────────────────
# Optimise against IN_SAMPLE only. When you are done tuning, switch to
# OUT_OF_SAMPLE and change nothing else. That run is the honest one.
IN_SAMPLE = (datetime(2019, 1, 1), datetime(2023, 12, 31))
OUT_OF_SAMPLE = (datetime(2024, 1, 1), datetime(2026, 6, 30))

PERIOD = IN_SAMPLE

SYMBOL = "EURUSD"
BAR_MINUTES = 15

SEQ_LEN = 3          # consecutive shrinking-body candles required
MIN_BODY_ATR = 0.1   # first candle body must be >= this * ATR
ATR_LEN = 14
ATR_SL = 1.7
ATR_TP = 2.5

RISK_PER_TRADE = 0.01   # 1% of equity at risk per trade, sized off stop distance

SESSION_FILTER = True
SESSION_START = time(8, 30)   # NY time
SESSION_END = time(11, 0)


class CandleBodyExhaustion(QCAlgorithm):

    def initialize(self):
        self.set_start_date(PERIOD[0].year, PERIOD[0].month, PERIOD[0].day)
        self.set_end_date(PERIOD[1].year, PERIOD[1].month, PERIOD[1].day)
        self.set_cash(100_000)

        forex = self.add_forex(SYMBOL, Resolution.MINUTE, Market.OANDA)
        self.symbol = forex.symbol

        # Spread + slippage. Without these the results are fantasy.
        forex.set_slippage_model(ConstantSlippageModel(0.0001))
        forex.set_fee_model(ConstantFeeModel(0.0))  # FX cost is in the spread

        self.consolidator = QuoteBarConsolidator(timedelta(minutes=BAR_MINUTES))
        self.consolidator.data_consolidated += self.on_bar
        self.subscription_manager.add_consolidator(self.symbol, self.consolidator)

        self.atr = AverageTrueRange(ATR_LEN)
        # seq_len candles for the pattern, +1 so a full sequence is always available
        self.bars = RollingWindow[QuoteBar](SEQ_LEN + 1)

        self.ny = TimeZones.NEW_YORK
        self.entry_price = None
        self.trade_log = []

        self.set_warm_up(timedelta(days=30))

    # ── Pattern ──────────────────────────────────────────────────────────────
    def _bodies(self):
        """Bodies of the last SEQ_LEN closed bars, oldest first."""
        return [self.bars[i] for i in range(SEQ_LEN - 1, -1, -1)]

    def _shrinking_bearish(self, bars):
        """All bearish, bodies monotonically shrinking oldest -> newest."""
        bodies = [b.open - b.close for b in bars]
        if not all(b.close < b.open for b in bars):
            return False
        if bodies[0] < self.atr.current.value * MIN_BODY_ATR:
            return False
        return all(bodies[i] >= bodies[i + 1] for i in range(len(bodies) - 1))

    def _shrinking_bullish(self, bars):
        bodies = [b.close - b.open for b in bars]
        if not all(b.close > b.open for b in bars):
            return False
        if bodies[0] < self.atr.current.value * MIN_BODY_ATR:
            return False
        return all(bodies[i] >= bodies[i + 1] for i in range(len(bodies) - 1))

    def _in_session(self, utc_time):
        if not SESSION_FILTER:
            return True
        ny_time = Extensions.convert_from_utc(utc_time, self.ny).time()
        return SESSION_START <= ny_time <= SESSION_END

    # ── Main loop ────────────────────────────────────────────────────────────
    def on_bar(self, sender, bar):
        self.bars.add(bar)
        self.atr.update(TradeBar(bar.end_time, self.symbol,
                                 bar.open, bar.high, bar.low, bar.close, 0))

        if self.is_warming_up or not self.bars.is_ready or not self.atr.is_ready:
            return
        if self.portfolio[self.symbol].invested:
            return
        if not self._in_session(bar.end_time):
            return

        seq = self._bodies()
        atr = self.atr.current.value

        # Shrinking bearish run -> downside exhausted -> fade long
        if self._shrinking_bearish(seq):
            self._enter(bar.close, atr, long=True)
        # Shrinking bullish run -> upside exhausted -> fade short
        elif self._shrinking_bullish(seq):
            self._enter(bar.close, atr, long=False)

    def _enter(self, price, atr, long):
        stop_dist = atr * ATR_SL
        if stop_dist <= 0:
            return

        risk_cash = self.portfolio.total_portfolio_value * RISK_PER_TRADE
        qty = risk_cash / stop_dist
        qty = qty if long else -qty

        if abs(qty) < 1:
            return

        self.market_order(self.symbol, qty)
        self.entry_price = price

        if long:
            self.stop_market_order(self.symbol, -qty, price - stop_dist)
            self.limit_order(self.symbol, -qty, price + atr * ATR_TP)
        else:
            self.stop_market_order(self.symbol, -qty, price + stop_dist)
            self.limit_order(self.symbol, -qty, price - atr * ATR_TP)

    def on_order_event(self, order_event):
        if order_event.status != OrderStatus.FILLED:
            return
        # One side filled -> cancel the other so no naked order is left resting
        if not self.portfolio[self.symbol].invested:
            self.transactions.cancel_open_orders(self.symbol)

    # ── Result summary ───────────────────────────────────────────────────────
    def on_end_of_algorithm(self):
        stats = self.trade_builder.closed_trades
        if not stats:
            self.log("NO TRADES — check the pattern conditions or session filter.")
            return

        pnls = [t.profit_loss for t in stats]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        pf = gross_win / gross_loss if gross_loss else float("inf")
        win_rate = len(wins) / len(pnls) * 100

        avg_win = gross_win / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0
        expectancy = (len(wins) / len(pnls)) * avg_win - (len(losses) / len(pnls)) * avg_loss

        # A single dominant trade means the "edge" is one lucky fill.
        top_share = max(wins) / gross_win * 100 if wins else 0

        self.log("=" * 52)
        self.log(f"Period        {PERIOD[0].date()} -> {PERIOD[1].date()}")
        self.log(f"Trades        {len(pnls)}       (need >100 to be meaningful)")
        self.log(f"Win rate      {win_rate:.1f}%   (target >50%)")
        self.log(f"Profit factor {pf:.2f}          (target >1.5)")
        self.log(f"Expectancy    {expectancy:.2f} per trade")
        self.log(f"Largest win   {top_share:.1f}% of gross profit  (>20% = concentrated)")
        self.log("=" * 52)
