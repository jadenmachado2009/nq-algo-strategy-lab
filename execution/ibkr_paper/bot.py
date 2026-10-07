"""CBE MNQ bot on an Interactive Brokers PAPER account (ib_async).

Flow per closed 5-min bar:  bars -> cbe.signal -> RiskGuard.can_enter -> bracket order
Every 15s watchdog:         daily P&L / clock / kill switch -> RiskGuard.must_flatten -> flatten

Stops and targets are sent as a bracket attached to the entry, so they live on
IB's servers: if this process or your Wi-Fi dies, the position is still protected.
"""

import asyncio
import logging
from collections import deque
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ib_async import IB, Future, LimitOrder, MarketOrder, StopOrder

import cbe
from config import Settings
from risk import RiskGuard

NY = ZoneInfo("America/New_York")
log = logging.getLogger("cbe")


class CBEBot:
    def __init__(self, s: Settings):
        self.s = s
        self.ib = IB()
        self.guard = RiskGuard(s.max_daily_loss, s.max_trades_per_day,
                               s.session_start, s.session_end, s.flatten_at)
        self.contract = None
        self.account = None
        self.pnl = None
        self.bars = None
        self.events: deque[str] = deque(maxlen=200)
        self._tasks: list[asyncio.Task] = []
        self._stopping = False
        self._flatten_reason_logged: tuple[date, str] | None = None
        self._last_roll_check = datetime.min.replace(tzinfo=timezone.utc)

    # ── lifecycle ────────────────────────────────────────────────────────────
    async def start(self):
        self._tasks = [asyncio.create_task(self._supervisor()),
                       asyncio.create_task(self._watchdog())]

    async def stop(self):
        self._stopping = True
        for t in self._tasks:
            t.cancel()
        if self.ib.isConnected():
            self.ib.disconnect()

    async def _supervisor(self):
        """Connect, and reconnect with backoff whenever the connection drops."""
        backoff = 5
        while not self._stopping:
            try:
                if not self.ib.isConnected():
                    await self._connect()
                    backoff = 5
                await asyncio.sleep(5)
            except Exception as exc:  # noqa: BLE001 — keep the supervisor alive no matter what
                self._event(f"connection problem: {exc!r} — retrying in {backoff}s")
                if self.ib.isConnected():
                    self.ib.disconnect()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 120)

    async def _connect(self):
        s = self.s
        await self.ib.connectAsync(s.host, s.port, clientId=s.client_id, timeout=15)
        accounts = self.ib.managedAccounts()
        paper = [a for a in accounts if a.startswith("DU")]
        if not paper or len(paper) != len(accounts):
            self.ib.disconnect()
            self._stopping = True
            raise RuntimeError(f"FATAL: accounts {accounts} are not all paper (DU…). Bot stopped, refusing to trade.")
        self.account = paper[0]

        self.contract = await self._front_month()
        self.pnl = self.ib.reqPnL(self.account)
        self.bars = await self.ib.reqHistoricalDataAsync(
            self.contract, endDateTime="", durationStr="3 D",
            barSizeSetting=f"{s.bar_minutes} mins", whatToShow="TRADES",
            useRTH=False, formatDate=2, keepUpToDate=True)
        if not self.bars:
            raise RuntimeError("no bars returned — check CME market data permissions on the paper account")
        self.bars.updateEvent += self._on_bars
        self._event(f"connected {self.account}, trading {self.contract.localSymbol}, "
                    f"{len(self.bars)} bars loaded, signals={s.signal_source}")

    async def _front_month(self):
        """Nearest contract that is more than ROLL_DAYS from expiry."""
        details = await self.ib.reqContractDetailsAsync(
            Future(self.s.symbol, exchange=self.s.exchange, currency="USD"))
        cutoff = date.today() + timedelta(days=self.s.roll_days_before_expiry)
        live = sorted(
            (d.contract for d in details
             if datetime.strptime(d.contract.lastTradeDateOrContractMonth[:8], "%Y%m%d").date() > cutoff),
            key=lambda c: c.lastTradeDateOrContractMonth)
        if not live:
            raise RuntimeError(f"no {self.s.symbol} contracts found on {self.s.exchange}")
        return live[0]

    # ── signals ──────────────────────────────────────────────────────────────
    def _on_bars(self, bars, has_new_bar: bool):
        if has_new_bar:
            # The last element is the bar that just STARTED; everything before it is closed.
            closed = [cbe.Bar(b.open, b.high, b.low, b.close) for b in bars[:-1]]
            asyncio.create_task(self._on_closed_bars(closed))

    async def _on_closed_bars(self, closed: list[cbe.Bar]):
        ny_now = datetime.now(NY)
        self.guard.new_bar(ny_now)
        direction, atr = cbe.signal(closed, self.s.seq_len, self.s.atr_len, self.s.min_body_atr)
        if direction == 0 or self.s.signal_source != "local":
            return
        await self.enter(direction, closed[-1].close, atr, source="CBE")

    async def enter(self, direction: int, ref_price: float | None = None,
                    atr: float | None = None, source: str = "webhook") -> str:
        """Single entry path for local signals and webhooks. Returns what happened."""
        side = "LONG" if direction > 0 else "SHORT"
        if not self.ib.isConnected() or self.contract is None:
            return self._event(f"{source} {side} skipped: not connected")

        ny_now = datetime.now(NY)
        self.guard.new_bar(ny_now)
        blocked = self.guard.can_enter(ny_now, self.position() == 0, bool(self.open_trades()))
        if blocked:
            return self._event(f"{source} {side} blocked: {blocked}")

        if ref_price is None or atr is None:
            closed = [cbe.Bar(b.open, b.high, b.low, b.close) for b in self.bars[:-1]]
            atr = cbe.wilder_atr(closed, self.s.atr_len)
            ref_price = closed[-1].close if closed else None
        if atr is None or ref_price is None:
            return self._event(f"{source} {side} skipped: not enough bars for ATR")

        tick = self.s.tick_size
        stop_dist = max(tick, cbe.round_tick(atr * self.s.atr_sl, tick))
        target_dist = max(tick, cbe.round_tick(atr * self.s.atr_tp, tick))
        multiplier = float(self.contract.multiplier or 2)
        qty = cbe.position_size(self.equity(), self.s.risk_pct, stop_dist, multiplier, self.s.max_contracts)
        if qty < 1:
            return self._event(f"{source} {side} skipped: size rounds to 0 (stop {stop_dist} pts)")

        self._place_bracket(direction, qty, ref_price, stop_dist, target_dist)
        self.guard.record_entry()
        return self._event(f"{source} {side} {qty}x {self.contract.localSymbol} ~{ref_price} "
                           f"SL {stop_dist}pt TP {target_dist}pt (risk ${qty * stop_dist * multiplier:.0f})")

    def _place_bracket(self, direction, qty, ref, stop_dist, target_dist):
        tick = self.s.tick_size
        action, exit_action = ("BUY", "SELL") if direction > 0 else ("SELL", "BUY")
        # Stop/target are set from the last close, not the fill. With 1 tick of slippage
        # this shifts R by a few percent — acceptable for paper validation.
        stop_px = cbe.round_tick(ref - direction * stop_dist, tick)
        target_px = cbe.round_tick(ref + direction * target_dist, tick)

        parent = MarketOrder(action, qty, orderId=self.ib.client.getReqId(), transmit=False)
        target = LimitOrder(exit_action, qty, target_px, orderId=self.ib.client.getReqId(),
                            parentId=parent.orderId, tif="DAY", transmit=False)
        stop = StopOrder(exit_action, qty, stop_px, orderId=self.ib.client.getReqId(),
                         parentId=parent.orderId, tif="DAY", transmit=True)
        for o in (parent, target, stop):
            o.account = self.account
            self.ib.placeOrder(self.contract, o)

    # ── protection ───────────────────────────────────────────────────────────
    async def _watchdog(self):
        while not self._stopping:
            await asyncio.sleep(15)
            if not self.ib.isConnected() or self.contract is None:
                continue
            try:
                ny_now = datetime.now(NY)
                reason = self.guard.must_flatten(ny_now, self.daily_pnl())
                if reason and (self.position() != 0 or self.open_trades()):
                    await self.flatten(reason)
                elif reason and self._flatten_reason_logged != (ny_now.date(), reason):
                    self._flatten_reason_logged = (ny_now.date(), reason)
                    self._event(f"flat; entries stopped: {reason}")
                if self.position() == 0 and not self.open_trades():
                    await self._maybe_roll()
            except Exception as exc:  # noqa: BLE001
                self._event(f"watchdog error: {exc!r}")

    async def flatten(self, reason: str) -> str:
        for trade in self.open_trades():
            self.ib.cancelOrder(trade.order)
        pos = self.position()
        if pos != 0:
            order = MarketOrder("SELL" if pos > 0 else "BUY", abs(pos))
            order.account = self.account
            self.ib.placeOrder(self.contract, order)
        return self._event(f"FLATTEN ({reason}): cancelled orders, closed {pos:+g}")

    async def _maybe_roll(self):
        now = datetime.now(timezone.utc)
        if now - self._last_roll_check < timedelta(hours=1):
            return
        self._last_roll_check = now
        front = await self._front_month()
        if front.conId != self.contract.conId:
            old = self.contract.localSymbol
            self.ib.cancelHistoricalData(self.bars)
            self.ib.disconnect()   # supervisor reconnects and subscribes to the new front month
            self._event(f"roll {old} -> {front.localSymbol}")

    async def kill(self) -> str:
        self.guard.killed = True
        return await self.flatten("kill switch — restart the bot to resume")

    # ── state ────────────────────────────────────────────────────────────────
    def position(self) -> float:
        return sum(p.position for p in self.ib.positions(self.account or "")
                   if self.contract and p.contract.conId == self.contract.conId)

    def open_trades(self):
        return [t for t in self.ib.openTrades()
                if self.contract and t.contract.conId == self.contract.conId]

    def equity(self) -> float:
        for v in self.ib.accountValues(self.account or ""):
            if v.tag == "NetLiquidation" and v.currency in ("USD", "BASE"):
                return float(v.value)
        return 0.0

    def daily_pnl(self) -> float | None:
        v = getattr(self.pnl, "dailyPnL", None)
        return None if v is None or v != v else float(v)   # v != v catches NaN

    def status(self) -> dict:
        return {
            "connected": self.ib.isConnected(),
            "account": self.account,
            "contract": getattr(self.contract, "localSymbol", None),
            "position": self.position() if self.ib.isConnected() else None,
            "open_orders": len(self.open_trades()) if self.ib.isConnected() else None,
            "equity": self.equity() if self.ib.isConnected() else None,
            "daily_pnl": self.daily_pnl(),
            "trades_today": self.guard.trades_today,
            "killed": self.guard.killed,
            "halted_day": str(self.guard.halted_day) if self.guard.halted_day else None,
            "ny_time": datetime.now(NY).strftime("%Y-%m-%d %H:%M:%S"),
            "recent_events": list(self.events)[-20:],
        }

    def _event(self, msg: str) -> str:
        stamped = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}"
        self.events.append(stamped)
        log.info(msg)
        return msg
