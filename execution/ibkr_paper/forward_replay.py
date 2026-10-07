"""Forward replay: run the bot's exact strategy + RiskGuard logic bar-by-bar over recent
NQ 5-min data from Yahoo (free, last ~60 days). Data after the QC out-of-sample
window, so the strategy has never seen it.

    .venv/bin/pip install yfinance
    .venv/bin/python forward_replay.py            # CBE (default), prints summary + trades CSV
    STRATEGY=pb .venv/bin/python forward_replay.py    # PB Stupid Simple

Fill model (deliberately conservative):
  - entry at NEXT bar open +/- SLIP ticks (signal is on bar close, like the bot)
  - stop fills at stop -/+ SLIP, or at the open if price gaps through it
  - target fills at the limit price, no slippage
  - if stop and target are both inside one bar, assume the STOP hit first
  - flatten at 15:50 NY bar close, daily loss limit on realized + open P&L
"""

import csv
import sys
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import cbe
import config
import pb_engine as pb
from risk import RiskGuard

NY = ZoneInfo("America/New_York")
MULTIPLIER = 2.0          # MNQ
COMMISSION = 0.62         # per contract per side
SLIP_TICKS = 1
START_EQUITY = 50_000.0


@dataclass
class Trade:
    side: int
    qty: int
    entry_time: object
    entry: float
    stop: float
    target: float
    risk_usd: float
    exit_time: object = None
    exit: float = 0.0
    reason: str = ""

    def pnl(self) -> float:
        gross = (self.exit - self.entry) * self.side * self.qty * MULTIPLIER
        return gross - 2 * COMMISSION * self.qty


def load_bars(bar_minutes: int):
    import yfinance as yf
    df = yf.download("NQ=F", interval=f"{bar_minutes}m", period="60d", progress=False, prepost=True)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    return [(ts.tz_convert(NY).to_pydatetime(), float(r.Open), float(r.High), float(r.Low), float(r.Close))
            for ts, r in df.iterrows()]


def make_signal(name: str, s: config.Settings):
    """Returns f(closed_bars, ny_close_time) -> (direction, stop_dist, target_dist) | None."""
    if name == "cbe":
        window: list[cbe.Bar] = []

        def cbe_sig(o, h, l, c, t):
            window.append(cbe.Bar(o, h, l, c))
            del window[:-400]
            direction, atr = cbe.signal(window, s.seq_len, s.atr_len, s.min_body_atr)
            if not direction or atr is None:
                return None
            return direction, atr * s.atr_sl, atr * s.atr_tp
        return cbe_sig

    if name == "pb":
        engine = pb.PBEngine()

        def pb_sig(o, h, l, c, t):
            return engine.on_bar(pb.Bar(t, o, h, l, c))
        return pb_sig

    raise SystemExit(f"unknown STRATEGY={name!r} (use cbe or pb)")


def run(s: config.Settings, rows, strategy_name: str):
    tick = s.tick_size
    slip = SLIP_TICKS * tick
    bar_len = timedelta(minutes=s.bar_minutes)
    guard = RiskGuard(s.max_daily_loss, s.max_trades_per_day, s.session_start, s.session_end, s.flatten_at)

    equity = START_EQUITY
    emit = make_signal(strategy_name, s)
    trades: list[Trade] = []
    pos: Trade | None = None
    pending: tuple[int, float] | None = None     # (direction, atr at signal)
    day, day_realized = None, 0.0

    def close_pos(t, price, reason):
        nonlocal pos, equity, day_realized
        pos.exit_time, pos.exit, pos.reason = t, price, reason
        equity += pos.pnl()
        day_realized += pos.pnl()
        trades.append(pos)
        pos = None

    for start, o, h, l, c in rows:
        end = start + bar_len
        if end.date() != day:
            day, day_realized = end.date(), 0.0

        # 1. fill a pending entry at this bar's open
        if pending and pos is None:
            direction, raw_stop, raw_target = pending
            stop_dist = max(tick, cbe.round_tick(raw_stop, tick))
            target_dist = max(tick, cbe.round_tick(raw_target, tick))
            qty = cbe.position_size(equity, s.risk_pct, stop_dist, MULTIPLIER, s.max_contracts)
            if qty >= 1:
                fill = o + direction * slip
                pos = Trade(direction, qty, start, fill,
                            fill - direction * stop_dist, fill + direction * target_dist,
                            qty * stop_dist * MULTIPLIER)
        pending = None

        # 2. stop / target inside this bar (stop first if both)
        if pos:
            if pos.side > 0:
                if l <= pos.stop:
                    close_pos(end, min(o, pos.stop) - slip, "stop")
                elif h >= pos.target:
                    close_pos(end, pos.target, "target")
            else:
                if h >= pos.stop:
                    close_pos(end, max(o, pos.stop) + slip, "stop")
                elif l <= pos.target:
                    close_pos(end, pos.target, "target")

        # 3. flatten rules at bar close
        open_pnl = ((c - pos.entry) * pos.side * pos.qty * MULTIPLIER) if pos else 0.0
        reason = guard.must_flatten(end, day_realized + open_pnl)
        if pos and reason:
            close_pos(end, c - pos.side * slip, reason)

        # 4. signal on the bar that just closed
        guard.new_bar(end)
        sig = emit(o, h, l, c, end)
        if sig and guard.can_enter(end, pos is None, False) is None:
            pending = sig
            guard.record_entry()

    return trades, equity


def summarize(trades, equity, rows, s, strategy_name):
    n = len(trades)
    print(f"Strategy {strategy_name.upper()}")
    print(f"Data   {rows[0][0]:%Y-%m-%d} -> {rows[-1][0]:%Y-%m-%d}  ({len(rows)} {s.bar_minutes}m bars, NQ=F, sized as MNQ)")
    if strategy_name == "cbe":
        print(f"Params SEQ_LEN={s.seq_len} ATR_SL={s.atr_sl} ATR_TP={s.atr_tp} risk={s.risk_pct:.1%} "
              f"window {s.session_start:%H:%M}-{s.session_end:%H:%M} NY, max {s.max_trades_per_day}/day")
    else:
        print(f"Params retrace={pb.RETRACE_PCT} SL={pb.SL_ATR_MULT}xATR RR={pb.RR} sweep<={pb.SWEEP_LOOKBACK} bars "
              f"ifvg<={pb.IFVG_MAX_AGE} bars, window {pb.SESSION_START:%H:%M}-{pb.SESSION_END:%H:%M} NY "
              f"(entry gate also capped at {s.max_trades_per_day}/day)")
    if not n:
        print("NO TRADES")
        return
    pnls = [t.pnl() for t in trades]
    rs = [t.pnl() / t.risk_usd for t in trades]
    wins = [p for p in pnls if p > 0]
    gross_w, gross_l = sum(wins), -sum(p for p in pnls if p <= 0)
    curve, peak, mdd = START_EQUITY, START_EQUITY, 0.0
    for p in pnls:
        curve += p
        peak = max(peak, curve)
        mdd = max(mdd, (peak - curve) / peak)
    weeks = max(1.0, (rows[-1][0] - rows[0][0]).days / 7)
    reasons = {}
    for t in trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1

    def row(name, val, bar, ok):
        print(f"  {name:<26}{val:<14}{bar:<10}{'PASS' if ok else 'FAIL'}")

    pf = gross_w / gross_l if gross_l else float("inf")
    wr = len(wins) / n
    exp_r = sum(rs) / n
    top = max(wins) / gross_w if wins else 0
    print(f"\nNet P&L ${sum(pnls):,.0f}  ({sum(pnls) / START_EQUITY:+.1%})   end equity ${equity:,.0f}")
    print(f"Exits  {reasons}   trades/week {n / weeks:.1f}\n")
    print(f"  {'Metric':<26}{'Value':<14}{'Bar':<10}Result")
    row("Trades", n, ">100", n > 100)
    row("Win rate", f"{wr:.1%}", ">50%", wr > 0.5)
    row("Profit factor", f"{pf:.2f}", ">1.5", pf > 1.5)
    row("Max drawdown", f"{mdd:.1%}", "<15%", mdd < 0.15)
    row("Expectancy", f"{exp_r:+.2f}R", ">0.3R", exp_r > 0.3)
    row("Largest win / gross profit", f"{top:.1%}", "<20%", top < 0.2)


def main():
    import os
    strategy_name = os.environ.get("STRATEGY", "cbe").lower()
    s = config.load()
    rows = load_bars(s.bar_minutes)
    trades, equity = run(s, rows, strategy_name)
    summarize(trades, equity, rows, s, strategy_name)
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "forward_trades.csv")
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["entry_time", "exit_time", "side", "qty", "entry", "exit", "stop", "target", "reason", "pnl", "r"])
        for t in trades:
            w.writerow([f"{t.entry_time:%Y-%m-%d %H:%M}", f"{t.exit_time:%Y-%m-%d %H:%M}", "L" if t.side > 0 else "S",
                        t.qty, t.entry, t.exit, t.stop, t.target, t.reason, round(t.pnl(), 2), round(t.pnl() / t.risk_usd, 2)])
    print(f"\nTrades -> {out}")


if __name__ == "__main__":
    main()
