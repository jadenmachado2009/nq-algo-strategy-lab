"""PB "Stupid Simple" ICT entry model — pure logic, no broker imports.

Port of strategies/PB_StupidSimple_v1.pine with the AUDIT.md findings fixed:

  1. LIQUIDITY SWEEP IS NOW A FILTER. In the Pine version the sweep was
     computed, plotted, and then left out of the entry conditions — the chart
     implied a filter the strategy never applied. Here an entry requires a
     sweep of the recent swing within SWEEP_LOOKBACK bars.

  2. IFVG NO LONGER LATCHES. The Pine detector stored the first gap it found
     in a `var` guarded by `na(...)`, so it could sit on a gap from hundreds of
     bars ago while fresher ones formed. Here the scan always takes the MOST
     RECENT qualifying gap and ignores anything older than IFVG_MAX_AGE bars.

  3. 5M FVG ZONES EXPIRE. Same staleness problem: a zone stays tradeable until
     filled or FVG_MAX_AGE bars old, whichever comes first.

  4. Dead `entryPrice` variable dropped.

Caveat carried over from the Pine comments: the IFVG is an approximation
(true sub-minute inversion can't be read without repainting), so results
carry a modelling caveat. Stated here so it stays attached to the numbers.

A "signal" is evaluated on CLOSED bars only and returns distances measured
from the last close, so every engine (replay, QC, live) anchors identically.
"""

from dataclasses import dataclass, field
from datetime import datetime, time


# ── Defaults (match the Pine inputs) ─────────────────────────────────────────
SESSION_START = time(8, 30)
SESSION_END = time(11, 0)
HTF_LOOKBACK = 10          # HTF bars to scan for the most recent FVG
FVG_MAX_AGE = 24           # 5m FVG zone expiry (2 hours)
IFVG_MAX_AGE = 20          # how recent the inverted gap must be
SWEEP_LOOKBACK = 5         # sweep must have happened within this many bars
SWING_LEN = 10             # swing high/low lookback for the sweep test
RETRACE_PCT = 0.5
SL_ATR_MULT = 1.0
RR = 2.0
ATR_LEN = 14


@dataclass(frozen=True)
class Bar:
    time: datetime         # bar CLOSE time, New York
    open: float
    high: float
    low: float
    close: float


@dataclass
class Zone:
    top: float
    bot: float
    age: int = 0


def wilder_atr(bars: list[Bar], length: int) -> float | None:
    if len(bars) < length + 1:
        return None
    trs = [max(b.high - b.low, abs(b.high - p.close), abs(b.low - p.close))
           for p, b in zip(bars, bars[1:])]
    atr = sum(trs[:length]) / length
    for tr in trs[length:]:
        atr = (atr * (length - 1) + tr) / length
    return atr


def _htf_bucket(t: datetime, hours: int) -> datetime:
    return t.replace(minute=0, second=0, microsecond=0, hour=(t.hour // hours) * hours)


def latest_fvg(bars: list[Bar], bullish: bool, lookback: int) -> Zone | None:
    """Most recent 3-bar gap within `lookback` completed bars, newest first."""
    n = len(bars)
    for i in range(n - 1, max(n - 1 - lookback, 2) - 1, -1):
        a, c = bars[i - 2], bars[i]
        if bullish and c.low > a.high:
            return Zone(top=c.low, bot=a.high, age=n - 1 - i)
        if not bullish and c.high < a.low:
            return Zone(top=a.low, bot=c.high, age=n - 1 - i)
    return None


def swept(bars: list[Bar], long: bool, lookback: int, swing_len: int) -> bool:
    """Did a bar in the last `lookback` bars take out the prior swing and close back inside?"""
    for i in range(len(bars) - 1, max(len(bars) - 1 - lookback, swing_len) - 1, -1):
        window = bars[i - swing_len:i]
        if not window:
            continue
        if long:
            level = min(b.low for b in window)
            if bars[i].low < level <= bars[i].close:
                return True
        else:
            level = max(b.high for b in window)
            if bars[i].high > level >= bars[i].close:
                return True
    return False


@dataclass
class PBEngine:
    """Feeds on closed 5m bars; keeps the HTF series and live 5m FVG zones."""
    session_start: time = SESSION_START
    session_end: time = SESSION_END
    retrace_pct: float = RETRACE_PCT
    sl_atr_mult: float = SL_ATR_MULT
    rr: float = RR
    atr_len: int = ATR_LEN
    htf_lookback: int = HTF_LOOKBACK
    fvg_max_age: int = FVG_MAX_AGE
    ifvg_max_age: int = IFVG_MAX_AGE
    sweep_lookback: int = SWEEP_LOOKBACK
    swing_len: int = SWING_LEN

    bars: list[Bar] = field(default_factory=list)
    h1: list[Bar] = field(default_factory=list)
    h4: list[Bar] = field(default_factory=list)
    bull5: Zone | None = None
    bear5: Zone | None = None

    # ── HTF aggregation ──────────────────────────────────────────────────────
    def _push_htf(self, series: list[Bar], bar: Bar, hours: int) -> None:
        bucket = _htf_bucket(bar.time, hours)
        if series and _htf_bucket(series[-1].time, hours) == bucket:
            cur = series[-1]
            series[-1] = Bar(bar.time, cur.open, max(cur.high, bar.high), min(cur.low, bar.low), bar.close)
        else:
            series.append(bar)
        del series[:-200]

    def _htf_context(self, price: float, bullish: bool) -> bool:
        for series in (self.h1, self.h4):
            # exclude the in-progress HTF bar — it isn't closed yet
            z = latest_fvg(series[:-1], bullish, self.htf_lookback)
            if z and z.bot <= price <= z.top:
                return True
        return False

    # ── main ─────────────────────────────────────────────────────────────────
    def on_bar(self, bar: Bar) -> tuple[int, float, float] | None:
        """Returns (direction, stop_dist, target_dist) measured from bar.close, or None."""
        self.bars.append(bar)
        del self.bars[:-400]
        self._push_htf(self.h1, bar, 1)
        self._push_htf(self.h4, bar, 4)

        # age / invalidate the tracked 5m zones
        for name in ("bull5", "bear5"):
            z = getattr(self, name)
            if z:
                z.age += 1
                filled = bar.close < z.bot if name == "bull5" else bar.close > z.top
                if filled or z.age > self.fvg_max_age:
                    setattr(self, name, None)

        if len(self.bars) >= 3:
            a, c = self.bars[-3], self.bars[-1]
            if c.low > a.high:
                self.bull5 = Zone(top=c.low, bot=a.high)
            elif c.high < a.low:
                self.bear5 = Zone(top=a.low, bot=c.high)

        if not (self.session_start <= bar.time.time() <= self.session_end):
            return None
        atr = wilder_atr(self.bars, self.atr_len)
        if atr is None:
            return None

        # LONG: price retraced into a live bullish 5m FVG, inside HTF bullish FVG,
        # a bearish gap has just been inverted upward, and liquidity was swept.
        if self.bull5:
            level = self.bull5.top - (self.bull5.top - self.bull5.bot) * self.retrace_pct
            if (self.bull5.bot <= bar.low <= level
                    and self._htf_context(bar.close, bullish=True)
                    and self._inverted(bullish=True)
                    and swept(self.bars, True, self.sweep_lookback, self.swing_len)):
                stop = bar.low - atr * self.sl_atr_mult
                stop_dist = bar.close - stop
                if stop_dist > 0:
                    return 1, stop_dist, stop_dist * self.rr

        if self.bear5:
            level = self.bear5.bot + (self.bear5.top - self.bear5.bot) * self.retrace_pct
            if (level <= bar.high <= self.bear5.top
                    and self._htf_context(bar.close, bullish=False)
                    and self._inverted(bullish=False)
                    and swept(self.bars, False, self.sweep_lookback, self.swing_len)):
                stop = bar.high + atr * self.sl_atr_mult
                stop_dist = stop - bar.close
                if stop_dist > 0:
                    return -1, stop_dist, stop_dist * self.rr
        return None

    def _inverted(self, bullish: bool) -> bool:
        """Most recent opposite-direction gap (not older than ifvg_max_age) closed through."""
        z = latest_fvg(self.bars[:-1], not bullish, self.ifvg_max_age)
        if z is None:
            return False
        close = self.bars[-1].close
        return close > z.top if bullish else close < z.bot


def signal(bars: list[Bar], engine: PBEngine) -> tuple[int, float, float] | None:
    """Convenience wrapper: feed the newest closed bar to a persistent engine."""
    return engine.on_bar(bars[-1])
