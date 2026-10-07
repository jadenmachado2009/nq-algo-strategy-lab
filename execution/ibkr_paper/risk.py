"""Risk guard. Sits between any signal and the broker. No broker imports."""

from dataclasses import dataclass, field
from datetime import date, datetime, time


@dataclass
class RiskGuard:
    max_daily_loss: float
    max_trades_per_day: int
    session_start: time
    session_end: time
    flatten_at: time

    killed: bool = False                 # manual kill switch — stays on until restart
    halted_day: date | None = None       # daily loss limit hit on this NY date
    trades_today: int = 0
    _day: date | None = field(default=None, repr=False)

    def new_bar(self, ny_now: datetime) -> None:
        if ny_now.date() != self._day:
            self._day = ny_now.date()
            self.trades_today = 0

    def must_flatten(self, ny_now: datetime, daily_pnl: float | None) -> str | None:
        """Reason to flatten everything right now, or None."""
        if self.killed:
            return "kill switch"
        if daily_pnl is not None and daily_pnl <= -self.max_daily_loss:
            self.halted_day = ny_now.date()
            return f"daily loss {daily_pnl:.0f} <= -{self.max_daily_loss:.0f}"
        if ny_now.time() >= self.flatten_at:
            return "end-of-day flatten"
        return None

    def can_enter(self, ny_now: datetime, is_flat: bool, has_open_orders: bool) -> str | None:
        """None if an entry is allowed, else the reason it is blocked."""
        if self.killed:
            return "kill switch"
        if self.halted_day == ny_now.date():
            return "halted for the day (daily loss)"
        if ny_now.weekday() >= 5:
            return "weekend"
        if not (self.session_start <= ny_now.time() <= self.session_end):
            return "outside entry window"
        if not is_flat or has_open_orders:
            return "already in a position / orders working"
        if self.trades_today >= self.max_trades_per_day:
            return "max trades for the day"
        return None

    def record_entry(self) -> None:
        self.trades_today += 1
