"""
ORB — Opening Range Breakout on MNQ (Micro E-mini Nasdaq-100 futures).
QuantConnect/LEAN port of research/orb.py.

WHY THIS EXISTS
---------------
research/orb.py measured +0.022R over 7,063 trades, but on Dukascopy data that
was later shown to track the CASH Nasdaq-100 index, not the futures contract
(mean difference vs ^NDX was +5 pts; vs NQ=F it was -97 pts). Basis and roll do
not affect ORB, which is intraday and flat by the close — but the cash index is
computed from 100 constituent stocks that open STAGGERED over the first several
minutes of the session. Its opening prints are stale, and the opening range is
the one thing this strategy depends on.

This run answers one question: does the edge survive on real CME futures data?

DESIGN
------
Two things happen in the same backtest, deliberately:

  1. REAL TRADING of the 60-minute window. Actual orders, LEAN's fill engine,
     per-contract commission and tick slippage, proper contract rollover. This
     validates the execution path.

  2. SHADOW ACCOUNTING for all five windows (10/20/30/45/60), computed with
     arithmetic IDENTICAL to research/orb.py — entry at the next bar's open plus
     one tick, stop at the opposite side of the range, target = 0.5 x risk,
     stop-checked-before-target inside a bar, explicit commission. No orders are
     placed for these. This gives the pooled figure directly comparable to the
     7,063-trade Dukascopy number, from one backtest instead of five.

The shadow numbers are the headline. The traded window is the control: if its
realised R diverges badly from its own shadow, the fill model is the problem,
not the data.

NORMALIZATION
-------------
RAW, deliberately. A ratio-adjusted series rescales historical point distances,
which would silently corrupt an absolute cost of 1.12 points per round trip. ORB
rebuilds its range every day and is flat by the close, so roll gaps between days
never touch a position. RAW is both safer and more faithful here.

Run IN_SAMPLE first, then switch PERIOD to OUT_OF_SAMPLE, change nothing else,
and record both in backtests/ using TEMPLATE.md.
"""

from AlgorithmImports import *
import math


# ── Configuration ────────────────────────────────────────────────────────────
# MNQ launched May 2019. Same 70/30 split as the Dukascopy study.
IN_SAMPLE = (datetime(2019, 6, 1), datetime(2024, 6, 30))
OUT_OF_SAMPLE = (datetime(2024, 7, 1), datetime(2026, 10, 1))
FULL = (datetime(2019, 6, 1), datetime(2026, 10, 1))

PERIOD = FULL

BAR_MINUTES = 5

WINDOWS = [10, 20, 30, 45, 60]   # opening-range lengths to shadow-track
TRADED_WINDOW = 60               # the one that places real orders
RR = 0.5                         # target as a fraction of the stop distance
DIRECTION = 1                    # +1 long only (shorts were negative at every window)
MIN_RANGE_PTS = 5.0              # skip days whose opening range is narrower than this

STARTING_CASH = 50_000
RISK_PER_TRADE = 0.0075          # 0.75%, the spec in backtests/2026-10-09_portfolio_bankroll.md
MAX_CONTRACTS = 20

SESSION_OPEN = time(9, 30)       # NY
SESSION_CLOSE = time(16, 0)      # hard RTH boundary for every bar we accept
LAST_ENTRY = time(15, 30)        # no new entries after this
FLATTEN_AT = time(15, 50)

COMMISSION_PER_CONTRACT = 0.62   # per side, IBKR tiered MNQ all-in
SLIPPAGE_TICKS = 1               # per side
TICK_SIZE = 0.25
COMMISSION_PTS = COMMISSION_PER_CONTRACT / 2.0   # $2/point on MNQ -> points/side
SLIP_PTS = TICK_SIZE


# ── Cost models (identical to cbe_mnq.py) ────────────────────────────────────
class PerContractFeeModel(FeeModel):
    def get_order_fee(self, parameters):
        qty = abs(parameters.order.absolute_quantity)
        return OrderFee(CashAmount(qty * COMMISSION_PER_CONTRACT, "USD"))


class TickSlippageModel:
    def get_slippage_approximation(self, asset, order):
        return SLIPPAGE_TICKS * TICK_SIZE


# ── Per-window shadow state machine ──────────────────────────────────────────
class WindowTracker:
    """Replicates research/orb.py exactly, one opening-range length.

    States: BUILDING -> ARMED -> PENDING -> IN -> DONE (one trade per day max).
    """

    def __init__(self, minutes):
        self.minutes = minutes
        self.r_multiples = []
        self.reset_day()

    def reset_day(self):
        self.hi = None
        self.lo = None
        self.state = "BUILDING"
        self.entry = 0.0
        self.stop = 0.0
        self.target = 0.0
        self.risk = 0.0

    def _minutes_since_open(self, t):
        return (t.hour * 60 + t.minute) - (SESSION_OPEN.hour * 60 + SESSION_OPEN.minute)

    def on_bar(self, bar):
        """`bar` is a closed 5m TradeBar whose END time is bar.end_time."""
        # Minutes elapsed at the bar's CLOSE. A 09:30-09:35 bar closes at +5.
        elapsed = self._minutes_since_open(bar.end_time.time())
        if elapsed <= 0:
            return
        if self.state == "DONE":
            return

        # 1. Build the opening range
        if elapsed <= self.minutes:
            self.hi = bar.high if self.hi is None else max(self.hi, bar.high)
            self.lo = bar.low if self.lo is None else min(self.lo, bar.low)
            return

        if self.state == "BUILDING":
            if self.hi is None or self.lo is None or (self.hi - self.lo) < max(MIN_RANGE_PTS, 2 * TICK_SIZE):
                self.state = "DONE"
                return
            self.state = "ARMED"

        # 2. Fill a pending entry at THIS bar's open (signal was last bar's close)
        if self.state == "PENDING":
            self.entry = bar.open + DIRECTION * SLIP_PTS
            self.stop = self.lo if DIRECTION > 0 else self.hi
            self.risk = abs(self.entry - self.stop)
            if self.risk < TICK_SIZE:
                self.state = "DONE"
                return
            self.target = self.entry + DIRECTION * self.risk * RR
            self.state = "IN"
            # fall through: the entry bar can also resolve the trade

        # 3. Track the exit. Stop is checked BEFORE target inside a bar.
        if self.state == "IN":
            exit_px = None
            if DIRECTION > 0:
                if bar.low <= self.stop:
                    exit_px = min(bar.open, self.stop) - SLIP_PTS
                elif bar.high >= self.target:
                    exit_px = self.target
            else:
                if bar.high >= self.stop:
                    exit_px = max(bar.open, self.stop) + SLIP_PTS
                elif bar.low <= self.target:
                    exit_px = self.target
            if exit_px is not None:
                self._record(exit_px)
            return

        # 4. Armed and waiting: first CLOSE beyond the range triggers an entry
        #    at the NEXT bar's open.
        if self.state == "ARMED" and bar.end_time.time() <= LAST_ENTRY:
            if DIRECTION > 0 and bar.close > self.hi:
                self.state = "PENDING"
            elif DIRECTION < 0 and bar.close < self.lo:
                self.state = "PENDING"

    def on_session_end(self, last_close):
        """Flat by the close: anything still open exits at the final bar."""
        if self.state == "IN":
            self._record(last_close - DIRECTION * SLIP_PTS)
        self.state = "DONE"

    def _record(self, exit_px):
        pnl = (exit_px - self.entry) * DIRECTION - 2 * COMMISSION_PTS
        self.r_multiples.append(pnl / self.risk)
        self.state = "DONE"


class OpeningRangeBreakoutMNQ(QCAlgorithm):

    def initialize(self):
        self.set_start_date(PERIOD[0].year, PERIOD[0].month, PERIOD[0].day)
        self.set_end_date(PERIOD[1].year, PERIOD[1].month, PERIOD[1].day)
        self.set_cash(STARTING_CASH)
        self.set_time_zone(TimeZones.NEW_YORK)

        self.future = self.add_future(
            Futures.Indices.MICRO_NASDAQ_100_E_MINI,
            Resolution.MINUTE,
            extended_market_hours=False,
            data_normalization_mode=DataNormalizationMode.RAW,
            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
            contract_depth_offset=0,
        )
        self.future.set_fee_model(PerContractFeeModel())
        self.future.set_slippage_model(TickSlippageModel())

        self.consolidator = TradeBarConsolidator(timedelta(minutes=BAR_MINUTES))
        self.consolidator.data_consolidated += self.on_bar
        self.subscription_manager.add_consolidator(self.future.symbol, self.consolidator)

        self.trackers = {w: WindowTracker(w) for w in WINDOWS}
        self.current_day = None
        self.last_close = None
        self.day_count = 0
        # Free-tier QC accounts have been reported to silently clamp a backtest
        # to a short rolling window instead of the configured dates. Logging the
        # CONFIGURED range would hide that completely, so record what we were
        # actually fed and compare the two at the end.
        self.first_bar = None
        self.last_bar = None

        # Real-order state for the traded window
        self.traded = self.trackers[TRADED_WINDOW]
        self.traded_today = False
        self.pending_stop = None
        self.pending_risk = None

        self.schedule.on(
            self.date_rules.every_day(self.future.symbol),
            self.time_rules.at(FLATTEN_AT.hour, FLATTEN_AT.minute),
            self.flatten_all,
        )

        self.set_warm_up(timedelta(days=2))

    # ── Rolls ────────────────────────────────────────────────────────────────
    def on_data(self, slice):
        if self.is_warming_up:
            return
        for changed in slice.symbol_changed_events.values():
            old = self.symbol(changed.old_symbol)
            if self.portfolio[old].invested or self.transactions.get_open_orders(old):
                self.transactions.cancel_open_orders(old)
                self.liquidate(old, tag="roll")
            # A roll mid-session makes the day's range incomparable. Abandon it.
            for t in self.trackers.values():
                t.state = "DONE"
            self.traded_today = True

    # ── Main loop ────────────────────────────────────────────────────────────
    def on_bar(self, sender, bar):
        if self.is_warming_up:
            return

        # RTH ONLY. MNQ trades nearly 24h, and LEAN may deliver evening bars
        # belonging to the next trading date. Letting those through would roll
        # `current_day` at 18:00 and reset every window mid-session. It also
        # keeps this identical to the validated RTH-only reference: the
        # Dukascopy study let entries fire as late as 23:55, which is 7.1% of
        # 60m trades on an index that is not trading then.
        bar_time = bar.end_time.time()
        if not (SESSION_OPEN < bar_time <= SESSION_CLOSE):
            return

        # New session: close out shadow trades, reset every window.
        day = bar.end_time.date()
        if day != self.current_day:
            if self.current_day is not None and self.last_close is not None:
                for t in self.trackers.values():
                    t.on_session_end(self.last_close)
            self.current_day = day
            self.day_count += 1
            for t in self.trackers.values():
                t.reset_day()
            self.traded_today = False

        self.last_close = bar.close
        if self.first_bar is None:
            self.first_bar = bar.end_time
        self.last_bar = bar.end_time

        # Shadow accounting for every window, including the traded one.
        prev_state = self.traded.state
        for t in self.trackers.values():
            t.on_bar(bar)

        # Real orders mirror the traded window's own transitions.
        self._mirror_real_orders(prev_state)

    def _mirror_real_orders(self, prev_state):
        """Place a real bracket when the traded window moves PENDING -> IN."""
        if self.traded_today or prev_state != "PENDING" or self.traded.state != "IN":
            return

        contract = self.future.mapped
        if contract is None:
            return
        if self.portfolio[contract].invested or self.transactions.get_open_orders(contract):
            return

        stop_dist = self.traded.risk
        if stop_dist < TICK_SIZE:
            return

        multiplier = self.securities[contract].symbol_properties.contract_multiplier
        risk_cash = self.portfolio.total_portfolio_value * RISK_PER_TRADE
        qty = min(MAX_CONTRACTS, math.floor(risk_cash / (stop_dist * multiplier)))
        if qty < 1:
            return

        self.traded_today = True
        self.pending_stop = self.traded.stop
        self.pending_risk = stop_dist
        self.market_order(contract, DIRECTION * qty, tag="entry")

    def on_order_event(self, event):
        if event.status != OrderStatus.FILLED:
            return

        # Match by TAG, not ticket: in backtests a market order fills INSIDE
        # market_order(), before the returned ticket has been assigned.
        order = self.transactions.get_order_by_id(event.order_id)
        if order.tag == "entry":
            qty = event.fill_quantity
            fill = event.fill_price
            risk = abs(fill - self.pending_stop)
            if risk < TICK_SIZE:
                self.liquidate(event.symbol, tag="degenerate-risk")
                return
            self.stop_market_order(event.symbol, -qty, self.pending_stop, tag="stop")
            self.limit_order(event.symbol, -qty, fill + DIRECTION * risk * RR, tag="target")
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

    # ── Result summary ───────────────────────────────────────────────────────
    def on_end_of_algorithm(self):
        if self.last_close is not None:
            for t in self.trackers.values():
                t.on_session_end(self.last_close)

        self.log("=" * 72)
        self.log(f"ORB on REAL MNQ FUTURES  ({BAR_MINUTES}m, {self.day_count} sessions)")
        self.log(f"  CONFIGURED range: {PERIOD[0].date()} -> {PERIOD[1].date()}")
        if self.first_bar is None:
            self.log("  ACTUAL data seen: NONE — no bars reached the algorithm.")
        else:
            span_days = (self.last_bar - self.first_bar).days
            want_days = (PERIOD[1] - PERIOD[0]).days
            self.log(f"  ACTUAL data seen: {self.first_bar.date()} -> {self.last_bar.date()} "
                     f"({span_days} days of {want_days} configured)")
            if span_days < want_days * 0.8:
                self.log("  *** WARNING: the backtest was CLAMPED to a shorter window than configured.")
                self.log("  *** Free-tier accounts do this silently. Every number below is on that")
                self.log("  *** short window only and is NOT comparable to the 7.8-year reference.")
        self.log(f"Long only, target = {RR} x stop, costs {2 * COMMISSION_PTS:.2f} pts commission "
                 f"+ {SLIP_PTS} pt slippage/side")
        self.log("")
        self.log("SHADOW ACCOUNTING — arithmetic identical to research/orb.py")
        self.log(f"  {'window':>7} {'n':>6} {'WR':>7} {'exp(R)':>9} {'+/-95%':>9} {'PF':>6}")

        pooled = []
        for w in WINDOWS:
            rs = self.trackers[w].r_multiples
            pooled.extend(rs)
            self.log(f"  {w:>6}m {self._fmt(rs)}")
        self.log(f"  {'ALL':>6}  {self._fmt(pooled)}")
        self.log("")
        # Apples-to-apples baseline: the Dukascopy cash-index data re-run under
        # THESE rules (RTH only, no entries after LAST_ENTRY). The published
        # +0.022R figure included entries as late as 23:55 on a cash index that
        # is not trading then -- 7.1% of 60m entries. Removing them RAISES the
        # number, so the edge does not depend on those synthetic prints.
        self.log("  Dukascopy CASH-INDEX, same rules: 6,479 trades, 65.7% WR, +0.030R  <- COMPARE TO THIS")
        self.log("  (its published figure, looser rules: 7,063 trades, 65.4% WR, +0.022R)")
        self.log("  ES (same vendor) -0.042R | YM -0.003R | prop break-even about -0.12R")

        # Control: did the real fills track the traded window's shadow?
        trades = self.trade_builder.closed_trades
        self.log("")
        self.log(f"REAL ORDERS — {TRADED_WINDOW}m window, {RISK_PER_TRADE:.2%} risk")
        if not trades:
            self.log("  NO TRADES — check session filter, warm-up, or mapping.")
        else:
            pnls = [t.profit_loss - t.total_fees for t in trades]
            wins = [p for p in pnls if p > 0]
            gross_win = sum(wins)
            gross_loss = abs(sum(p for p in pnls if p <= 0))
            approx_r = STARTING_CASH * RISK_PER_TRADE
            self.log(f"  trades {len(pnls)}  win rate {len(wins) / len(pnls):.1%}  "
                     f"PF {gross_win / gross_loss if gross_loss else float('inf'):.2f}")
            self.log(f"  net ${sum(pnls):,.0f}  approx {sum(pnls) / len(pnls) / approx_r:+.3f}R/trade "
                     f"(1R ~ ${approx_r:,.0f})")
            self.log(f"  shadow {TRADED_WINDOW}m for comparison: "
                     f"{len(self.traded.r_multiples)} trades")
            self.log("  A large gap between these two is a FILL-MODEL problem, not a data problem.")
        self.log("=" * 72)

    @staticmethod
    def _fmt(rs):
        n = len(rs)
        if n == 0:
            return f"{0:>6} {'-':>7} {'-':>9} {'-':>9} {'-':>6}"
        wins = [r for r in rs if r > 0]
        losses = [r for r in rs if r <= 0]
        mean = sum(rs) / n
        var = sum((r - mean) ** 2 for r in rs) / n if n > 1 else 0.0
        ci = 1.96 * math.sqrt(var) / math.sqrt(n)
        gl = -sum(losses)
        pf = (sum(wins) / gl) if gl > 0 else float("inf")
        return f"{n:>6} {len(wins) / n:>6.1%} {mean:>+9.3f} {ci:>9.3f} {pf:>6.2f}"
