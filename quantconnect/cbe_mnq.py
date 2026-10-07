"""
CBE — Candle Body Exhaustion on MNQ (Micro E-mini Nasdaq-100 futures).
QuantConnect/LEAN port. Logic identical to quantconnect/cbe_v1.py (the FX
port); everything that changes is futures plumbing:

  1. Continuous contract for signals, mapped front-month contract for orders.
     Signals and ATR run on a back-adjusted continuous series so roll gaps
     don't create fake candles. Orders go to the actual contract being traded.

  2. Rolls are handled explicitly. When LEAN maps to a new contract, any
     position in the old one is flattened and its orders cancelled. Without
     this a backtest silently holds an expiring contract.

  3. Stop and target are anchored to the FILL price of the traded contract,
     not the adjusted continuous close — the two differ by the roll adjustment.

  4. Per-contract commission and tick-based slippage (futures cost model),
     plus a prop-style daily loss limit and a hard flatten before the close.

Run IN_SAMPLE while tuning. Then switch PERIOD to OUT_OF_SAMPLE, change
nothing else, and record both runs in backtests/ using TEMPLATE.md.
"""

from AlgorithmImports import *
import math


# ── Configuration ────────────────────────────────────────────────────────────
# MNQ launched May 2019. 70/30 split of the available history.
IN_SAMPLE = (datetime(2019, 6, 1), datetime(2023, 12, 31))
OUT_OF_SAMPLE = (datetime(2024, 1, 1), datetime(2026, 6, 30))

PERIOD = IN_SAMPLE

BAR_MINUTES = 5

SEQ_LEN = 3          # consecutive shrinking-body candles required
MIN_BODY_ATR = 0.1   # first candle body must be >= this * ATR
ATR_LEN = 14
ATR_SL = 1.7
ATR_TP = 2.5

STARTING_CASH = 50_000       # typical prop evaluation size
RISK_PER_TRADE = 0.01        # 1% of equity at risk, sized off stop distance
MAX_CONTRACTS = 10
MAX_DAILY_LOSS = 0.02        # stop trading for the day at -2% of day-start equity

SESSION_START = time(9, 30)  # NY time — cash open
SESSION_END = time(11, 30)   # no NEW entries after this
FLATTEN_AT = time(15, 50)    # close anything still open, never hold overnight

COMMISSION_PER_CONTRACT = 0.62   # per side, approx. IBKR tiered MNQ all-in
SLIPPAGE_TICKS = 1               # per side
TICK_SIZE = 0.25


# ── Cost models ──────────────────────────────────────────────────────────────
class PerContractFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        qty = abs(parameters.order.absolute_quantity)
        return OrderFee(CashAmount(qty * COMMISSION_PER_CONTRACT, "USD"))


class TickSlippageModel:
    def get_slippage_approximation(self, asset, order):
        return SLIPPAGE_TICKS * TICK_SIZE


class CandleBodyExhaustionMNQ(QCAlgorithm):

    def initialize(self):
        self.set_start_date(PERIOD[0].year, PERIOD[0].month, PERIOD[0].day)
        self.set_end_date(PERIOD[1].year, PERIOD[1].month, PERIOD[1].day)
        self.set_cash(STARTING_CASH)
        self.set_time_zone(TimeZones.NEW_YORK)

        self.future = self.add_future(
            Futures.Indices.MICRO_NASDAQ_100_E_MINI,
            Resolution.MINUTE,
            extended_market_hours=True,
            data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            contract_depth_offset=0,
        )
        self.future.set_fee_model(PerContractFeeModel())
        self.future.set_slippage_model(TickSlippageModel())

        self.consolidator = TradeBarConsolidator(timedelta(minutes=BAR_MINUTES))
        self.consolidator.data_consolidated += self.on_bar
        self.subscription_manager.add_consolidator(self.future.symbol, self.consolidator)

        self.atr_ind = AverageTrueRange(ATR_LEN, MovingAverageType.WILDERS)
        self.bars = RollingWindow[TradeBar](SEQ_LEN + 1)

        self.entry_ticket = None
        self.stop_ticket = None
        self.target_ticket = None
        self.pending_direction = 0     # +1 long, -1 short, awaiting entry fill
        self.pending_stop_dist = 0.0
        self.pending_target_dist = 0.0

        self.day_start_equity = STARTING_CASH
        self.halted_today = False
        self.current_day = None

        self.schedule.on(
            self.date_rules.every_day(self.future.symbol),
            self.time_rules.at(FLATTEN_AT.hour, FLATTEN_AT.minute),
            self.flatten_all,
        )

        self.set_warm_up(timedelta(days=10))

    # ── Rolls ────────────────────────────────────────────────────────────────
    def on_data(self, slice):
        if self.is_warming_up:
            return
        for changed in slice.symbol_changed_events.values():
            old = self.symbol(changed.old_symbol)
            if self.portfolio[old].invested or self.transactions.get_open_orders(old):
                self.transactions.cancel_open_orders(old)
                self.liquidate(old, tag="roll")
                self._clear_tickets()

    # ── Pattern (identical to cbe_v1.py) ─────────────────────────────────────
    def _seq(self):
        """Last SEQ_LEN closed bars, oldest first."""
        return [self.bars[i] for i in range(SEQ_LEN - 1, -1, -1)]

    def _shrinking(self, bars, bearish):
        sign = -1 if bearish else 1
        bodies = [sign * (b.close - b.open) for b in bars]
        if not all(body > 0 for body in bodies):
            return False
        if bodies[0] < self.atr_ind.current.value * MIN_BODY_ATR:
            return False
        return all(bodies[i] >= bodies[i + 1] for i in range(len(bodies) - 1))

    # ── Main loop ────────────────────────────────────────────────────────────
    def on_bar(self, sender, bar):
        self.bars.add(bar)
        self.atr_ind.update(bar)

        if self.is_warming_up or not self.bars.is_ready or not self.atr_ind.is_ready:
            return

        self._roll_day()
        if self.halted_today:
            return

        now = self.time.time()
        if not (SESSION_START <= now <= SESSION_END):
            return

        contract = self.future.mapped
        if contract is None:
            return
        if self.portfolio[contract].invested or self.transactions.get_open_orders(contract):
            return

        seq = self._seq()
        atr = self.atr_ind.current.value

        if self._shrinking(seq, bearish=True):       # downside exhausted -> fade long
            self._enter(contract, atr, direction=1)
        elif self._shrinking(seq, bearish=False):    # upside exhausted -> fade short
            self._enter(contract, atr, direction=-1)

    def _roll_day(self):
        today = self.time.date()
        if today != self.current_day:
            self.current_day = today
            self.day_start_equity = self.portfolio.total_portfolio_value
            self.halted_today = False
        pnl = self.portfolio.total_portfolio_value - self.day_start_equity
        if pnl <= -MAX_DAILY_LOSS * self.day_start_equity and not self.halted_today:
            self.halted_today = True
            self.flatten_all()
            self.debug(f"{today} daily loss limit hit ({pnl:.0f}) — halted")

    def _enter(self, contract, atr, direction):
        stop_dist = self._round_tick(atr * ATR_SL)
        target_dist = self._round_tick(atr * ATR_TP)
        if stop_dist < TICK_SIZE:
            return

        multiplier = self.securities[contract].symbol_properties.contract_multiplier
        risk_cash = self.portfolio.total_portfolio_value * RISK_PER_TRADE
        qty = min(MAX_CONTRACTS, math.floor(risk_cash / (stop_dist * multiplier)))
        if qty < 1:
            return

        self.pending_direction = direction
        self.pending_stop_dist = stop_dist
        self.pending_target_dist = target_dist
        self.entry_ticket = self.market_order(contract, direction * qty, tag="entry")

    def on_order_event(self, event):
        if event.status != OrderStatus.FILLED:
            return

        # Entry filled -> place the bracket from the real fill price.
        # Match by tag, not ticket: in backtests a market order fills INSIDE
        # market_order(), before the returned ticket has been assigned.
        order = self.transactions.get_order_by_id(event.order_id)
        if order.tag == "entry":
            qty = event.fill_quantity
            fill = event.fill_price
            d = self.pending_direction
            self.stop_ticket = self.stop_market_order(
                event.symbol, -qty, fill - d * self.pending_stop_dist, tag="stop")
            self.target_ticket = self.limit_order(
                event.symbol, -qty, fill + d * self.pending_target_dist, tag="target")
            self.entry_ticket = None
            return

        # One exit filled -> cancel the other so nothing is left resting
        if not self.portfolio[event.symbol].invested:
            self.transactions.cancel_open_orders(event.symbol)
            self._clear_tickets()

    def flatten_all(self):
        contract = self.future.mapped
        if self.is_warming_up or contract is None:
            return
        self.transactions.cancel_open_orders(contract)
        if self.portfolio[contract].invested:
            self.liquidate(contract, tag="flatten")
        self._clear_tickets()

    def _clear_tickets(self):
        self.stop_ticket = None
        self.target_ticket = None
        self.entry_ticket = None

    @staticmethod
    def _round_tick(x):
        return round(x / TICK_SIZE) * TICK_SIZE

    # ── Result summary ───────────────────────────────────────────────────────
    def on_end_of_algorithm(self):
        trades = self.trade_builder.closed_trades
        if not trades:
            self.log("NO TRADES — check session filter, warm-up, or pattern conditions.")
            return

        pnls = [t.profit_loss - t.total_fees for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        pf = gross_win / gross_loss if gross_loss else float("inf")
        win_rate = len(wins) / len(pnls) * 100

        avg_win = gross_win / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0
        expectancy = (len(wins) / len(pnls)) * avg_win - (len(losses) / len(pnls)) * avg_loss
        avg_risk = STARTING_CASH * RISK_PER_TRADE   # approx: 1R at starting equity
        top_share = max(wins) / gross_win * 100 if wins else 0

        self.log("=" * 60)
        self.log(f"MNQ CBE  {PERIOD[0].date()} -> {PERIOD[1].date()}  ({BAR_MINUTES}m)")
        self.log(f"Trades        {len(pnls)}        (need >100)")
        self.log(f"Win rate      {win_rate:.1f}%    (target >50%)")
        self.log(f"Profit factor {pf:.2f}           (target >1.5)")
        self.log(f"Expectancy    ${expectancy:.2f}/trade  ~{expectancy / avg_risk:.2f}R  (target >0.3R)")
        self.log(f"Largest win   {top_share:.1f}% of gross profit  (>20% = concentrated)")
        self.log("Max drawdown  -> read 'Drawdown' in the QC results panel (target <15%)")
        self.log("=" * 60)
