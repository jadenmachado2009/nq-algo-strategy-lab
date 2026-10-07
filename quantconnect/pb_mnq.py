"""
PB "Stupid Simple" ICT entry model on MNQ — QuantConnect/LEAN port.

The signal logic is NOT reimplemented here. This file uploads alongside
execution/ibkr_paper/pb_engine.py and imports PBEngine from it, so the backtest, the
forward replay and the live bot run byte-identical strategy code. Only the
plumbing (data, sizing, orders, risk limits) lives here.

Same futures plumbing as cbe_mnq.py:
  - continuous contract for signals, mapped front-month for orders
  - rolls flatten the old contract
  - stop/target anchored to the FILL price, entry matched by ORDER TAG
    (in backtests a market order fills inside market_order(), before the
    returned ticket is assigned — matching by ticket silently skips brackets)
  - per-contract commission, tick slippage, daily loss limit, EOD flatten

Run IN_SAMPLE, then OUT_OF_SAMPLE with nothing else changed.
"""

from AlgorithmImports import *
import math

from pb_engine import Bar as PBBar, PBEngine


IN_SAMPLE = (datetime(2019, 6, 1), datetime(2023, 12, 31))
OUT_OF_SAMPLE = (datetime(2024, 1, 1), datetime(2026, 6, 30))

PERIOD = IN_SAMPLE

BAR_MINUTES = 5

STARTING_CASH = 50_000
RISK_PER_TRADE = 0.01
MAX_CONTRACTS = 10
MAX_DAILY_LOSS = 0.02
FLATTEN_AT = time(15, 50)

COMMISSION_PER_CONTRACT = 0.62
SLIPPAGE_TICKS = 1
TICK_SIZE = 0.25


class PerContractFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        qty = abs(parameters.order.absolute_quantity)
        return OrderFee(CashAmount(qty * COMMISSION_PER_CONTRACT, "USD"))


class TickSlippageModel:
    def get_slippage_approximation(self, asset, order):
        return SLIPPAGE_TICKS * TICK_SIZE


class PBStupidSimpleMNQ(QCAlgorithm):

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

        self.engine = PBEngine()

        self.pending_direction = 0
        self.pending_stop_dist = 0.0
        self.pending_target_dist = 0.0

        self.day_start_equity = STARTING_CASH
        self.halted_today = False
        self.current_day = None
        self.signals_seen = 0

        self.schedule.on(
            self.date_rules.every_day(self.future.symbol),
            self.time_rules.at(FLATTEN_AT.hour, FLATTEN_AT.minute),
            self.flatten_all,
        )

        self.set_warm_up(timedelta(days=10))

    def on_data(self, slice):
        if self.is_warming_up:
            return
        for changed in slice.symbol_changed_events.values():
            old = self.symbol(changed.old_symbol)
            if self.portfolio[old].invested or self.transactions.get_open_orders(old):
                self.transactions.cancel_open_orders(old)
                self.liquidate(old, tag="roll")

    def on_bar(self, sender, bar):
        # Feed every bar to the engine, warm-up included: it needs history to
        # build the 1H/4H series and its FVG zones before the first live bar.
        signal = self.engine.on_bar(PBBar(bar.end_time, bar.open, bar.high, bar.low, bar.close))
        if self.is_warming_up or signal is None:
            return

        self._roll_day()
        if self.halted_today:
            return

        contract = self.future.mapped
        if contract is None:
            return
        if self.portfolio[contract].invested or self.transactions.get_open_orders(contract):
            return

        direction, stop_dist, target_dist = signal
        self.signals_seen += 1
        self._enter(contract, direction, stop_dist, target_dist)

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

    def _enter(self, contract, direction, stop_dist, target_dist):
        stop_dist = self._round_tick(stop_dist)
        target_dist = self._round_tick(target_dist)
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
        self.market_order(contract, direction * qty, tag="entry")

    def on_order_event(self, event):
        if event.status != OrderStatus.FILLED:
            return
        order = self.transactions.get_order_by_id(event.order_id)
        if order.tag == "entry":
            qty = event.fill_quantity
            fill = event.fill_price
            d = self.pending_direction
            self.stop_market_order(event.symbol, -qty, fill - d * self.pending_stop_dist, tag="stop")
            self.limit_order(event.symbol, -qty, fill + d * self.pending_target_dist, tag="target")
            return
        if not self.portfolio[event.symbol].invested:
            self.transactions.cancel_open_orders(event.symbol)

    def flatten_all(self):
        contract = self.future.mapped
        if self.is_warming_up or contract is None:
            return
        self.transactions.cancel_open_orders(contract)
        if self.portfolio[contract].invested:
            self.liquidate(contract, tag="flatten")

    @staticmethod
    def _round_tick(x):
        return round(x / TICK_SIZE) * TICK_SIZE

    def on_end_of_algorithm(self):
        trades = self.trade_builder.closed_trades
        self.log(f"Signals generated: {self.signals_seen}")
        if not trades:
            self.log("NO TRADES — filters may be too restrictive for this sample.")
            return

        pnls = [t.profit_loss - t.total_fees for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        gross_win, gross_loss = sum(wins), abs(sum(losses))
        pf = gross_win / gross_loss if gross_loss else float("inf")
        avg_win = gross_win / len(wins) if wins else 0
        avg_loss = gross_loss / len(losses) if losses else 0
        expectancy = (len(wins) / len(pnls)) * avg_win - (len(losses) / len(pnls)) * avg_loss

        self.log("=" * 60)
        self.log(f"MNQ PB  {PERIOD[0].date()} -> {PERIOD[1].date()}  ({BAR_MINUTES}m)")
        self.log(f"Trades        {len(pnls)}        (need >100)")
        self.log(f"Win rate      {len(wins) / len(pnls) * 100:.1f}%    (target >50%)")
        self.log(f"Profit factor {pf:.2f}           (target >1.5)")
        self.log(f"Expectancy    ${expectancy:.2f}/trade")
        self.log("=" * 60)
