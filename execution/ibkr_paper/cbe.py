"""CBE signal logic — pure functions, no broker imports, unit-tested offline.

Must stay behaviourally identical to quantconnect/cbe_mnq.py and
ninjatrader/CBE_MNQ.cs. If you change one, change all three.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Bar:
    open: float
    high: float
    low: float
    close: float


def wilder_atr(bars: list[Bar], length: int) -> float | None:
    """ATR with Wilder smoothing (same as Pine ta.atr / LEAN WILDERS)."""
    if len(bars) < length + 1:
        return None
    trs = [
        max(b.high - b.low, abs(b.high - p.close), abs(b.low - p.close))
        for p, b in zip(bars, bars[1:])
    ]
    atr = sum(trs[:length]) / length
    for tr in trs[length:]:
        atr = (atr * (length - 1) + tr) / length
    return atr


def shrinking(seq: list[Bar], bearish: bool, atr: float, min_body_atr: float) -> bool:
    """All candles in seq (oldest first) same direction, bodies non-increasing,
    first body >= min_body_atr * ATR."""
    sign = -1 if bearish else 1
    bodies = [sign * (b.close - b.open) for b in seq]
    if not all(body > 0 for body in bodies):
        return False
    if bodies[0] < atr * min_body_atr:
        return False
    return all(bodies[i] >= bodies[i + 1] for i in range(len(bodies) - 1))


def signal(closed_bars: list[Bar], seq_len: int, atr_len: int, min_body_atr: float) -> tuple[int, float | None]:
    """Evaluate on CLOSED bars only. Returns (direction, atr):
    +1 fade long, -1 fade short, 0 nothing."""
    atr = wilder_atr(closed_bars, atr_len)
    if atr is None or len(closed_bars) < seq_len:
        return 0, atr
    seq = closed_bars[-seq_len:]
    if shrinking(seq, bearish=True, atr=atr, min_body_atr=min_body_atr):
        return 1, atr
    if shrinking(seq, bearish=False, atr=atr, min_body_atr=min_body_atr):
        return -1, atr
    return 0, atr


def round_tick(x: float, tick: float) -> float:
    return round(x / tick) * tick


def position_size(equity: float, risk_pct: float, stop_dist: float,
                  multiplier: float, max_contracts: int) -> int:
    if stop_dist <= 0:
        return 0
    qty = int((equity * risk_pct) // (stop_dist * multiplier))
    return max(0, min(max_contracts, qty))
