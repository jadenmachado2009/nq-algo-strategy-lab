"""Hypothesis test: a coin-flip entry with a 0.5R target, NQ 1-minute, NY 09:30-11:00.

Claim being tested: at 1R stop / 0.5R target a 50/50 entry wins ~66.7% of the
time, which is exactly break-even, so restricting it to 1-minute bars in the
NY open might push it into profit.

Theory first: if price is a driftless random walk, the chance of touching +0.5R
before -1R is 1/(1+0.5) = 66.7%, so expectancy is 0R before costs for ANY
target. Costs are fixed in points, so they cost more R the tighter the stop.
This script measures whether real NQ deviates from that.

Rules (fixed before running):
  - Entries 09:30-10:59 NY, one position at a time, re-enter on the next bar's
    open after each exit. Anything open is flattened at 11:00.
  - Direction: random coin flip per trade, many seeds.
  - Stop: fixed points or k x ATR(14) on 1m. Target = 0.5 x stop.
  - Bracket is placed from the actual fill price.
  - Costs: entry is a market order (+1 tick), stop exit is a market order
    (-1 tick), target is a limit that only fills if price trades 1 tick
    THROUGH it. Commission per side as set below.
  - If one bar touches both stop and target, the standard bar path decides
    (green bar O-L-H-C, red bar O-H-L-C). Stop-first (pessimistic) and
    target-first (optimistic) bounds are reported alongside.

    python3 research/half_r.py <dir with dukascopy m1 csvs> [seeds]
"""

import glob
import os
import sys

import numpy as np
import pandas as pd

TICK = 0.25
CONTRACTS = {  # $/point, commission $/side all-in
    "NQ": (20.0, 2.50),
    "MNQ": (2.0, 0.62),
}
FIXED_STOPS = [5, 10, 15, 20, 30, 40]
ATR_MULTS = [1.0, 2.0, 4.0]
RR = 0.5


def load(path):
    files = sorted(glob.glob(os.path.join(path, "*.csv")))
    df = pd.concat([pd.read_csv(f) for f in files])
    df["t"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert("America/New_York")
    df = df.drop_duplicates("t").sort_values("t").set_index("t")
    df = df[df.index.dayofweek < 5]
    hm = df.index.hour * 100 + df.index.minute
    df = df[(hm >= 930) & (hm < 1100)].copy()
    df["day"] = df.index.date
    # drop half-days / holes: keep days with a near-complete session
    counts = df.groupby("day")["close"].transform("size")
    return df[counts >= 85]


def atr14(df):
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
    out = pd.Series(tr).ewm(alpha=1 / 14, adjust=False).mean().to_numpy()
    return np.r_[out[0], out[:-1]]  # known at the bar's open: no look-ahead


def outcomes(df, stop, d, comm_pts, costs=True, fill="path"):
    """For every entry bar i: exit bar index and R for direction d (+1/-1)."""
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    day = pd.factorize(df["day"])[0]
    n = len(o)
    slip = TICK if costs else 0.0
    through = TICK if costs else 0.0
    comm = comm_pts if costs else 0.0

    E = o + d * slip
    SL = E - d * stop
    TP = E + d * RR * stop
    exit_bar = np.full(n, -1)
    exit_px = np.full(n, np.nan)
    idx = np.arange(n)
    open_ = np.ones(n, bool)
    for k in range(95):
        j = idx + k
        ok = open_ & (j < n)
        ok[ok] &= day[j[ok]] == day[ok]
        if not ok.any():
            break
        jj = j[ok]
        if d > 0:
            hit_sl = l[jj] <= SL[ok]
            hit_tp = h[jj] >= TP[ok] + through
        else:
            hit_sl = h[jj] >= SL[ok]
            hit_tp = l[jj] <= TP[ok] - through
        both = hit_sl & hit_tp
        if fill == "pessimistic":
            sl_first = np.ones_like(both)
        elif fill == "optimistic":
            sl_first = np.zeros_like(both)
        else:  # standard bar path: green bar goes O-L-H-C, red bar O-H-L-C
            green = c[jj] >= o[jj]
            sl_first = green if d > 0 else ~green
        take_sl = hit_sl & (sl_first | ~both)
        take_tp = hit_tp & ~take_sl
        px = np.where(take_sl, SL[ok] - d * slip, np.where(take_tp, TP[ok], np.nan))
        done = take_sl | take_tp
        rows = np.flatnonzero(ok)[done]
        exit_bar[rows] = jj[done]
        exit_px[rows] = px[done]
        open_[rows] = False
    # still open at 11:00 -> flatten at the session's last close
    last = pd.Series(idx).groupby(day).transform("max").to_numpy()
    rest = exit_bar < 0
    exit_bar[rest] = last[rest]
    exit_px[rest] = c[last[rest]] - d * slip
    pnl = d * (exit_px - E) - 2 * comm
    return exit_bar, pnl / stop, pnl


def simulate(df, stop, comm_pts, seeds, **kw):
    xl, rl, pl = outcomes(df, stop, +1, comm_pts, **kw)
    xs, rs, ps = outcomes(df, stop, -1, comm_pts, **kw)
    rng = np.random.default_rng(7)
    n = len(df)
    ptr = np.zeros(seeds, int)
    sumR = np.zeros(seeds); sumP = np.zeros(seeds)
    wins = np.zeros(seeds); trades = np.zeros(seeds)
    gw = np.zeros(seeds); gl = np.zeros(seeds)
    while True:
        live = ptr < n
        if not live.any():
            break
        p = ptr[live]
        long_ = rng.random(p.size) < 0.5
        r = np.where(long_, rl[p], rs[p])
        pts = np.where(long_, pl[p], ps[p])
        x = np.where(long_, xl[p], xs[p])
        sumR[live] += r; sumP[live] += pts; trades[live] += 1
        wins[live] += r > 0
        gw[live] += np.where(r > 0, r, 0); gl[live] += np.where(r < 0, -r, 0)
        ptr[live] = x + 1
    exp = sumR / trades
    return dict(trades=trades.mean(), wr=(wins / trades).mean(),
                expR=exp.mean(), expR_p5=np.percentile(exp, 5), expR_p95=np.percentile(exp, 95),
                pf=(gw / gl).mean(), pts_per_trade=(sumP / trades).mean(),
                pct_seeds_profitable=(exp > 0).mean())


def main():
    path = sys.argv[1]
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    df = load(path)
    a = atr14(df)
    days = df["day"].nunique()
    print(f"Data: {df.index[0].date()} -> {df.index[-1].date()}, {days} sessions, {len(df):,} 1m bars")
    print(f"Median 1m ATR(14) in window: {np.median(a):.2f} pts\n")

    stops = [(f"{s}pt", float(s)) for s in FIXED_STOPS]
    stops += [(f"{m:g}xATR", m * a) for m in ATR_MULTS]
    rows = []
    for inst, (pv, comm) in CONTRACTS.items():
        comm_pts = comm / pv
        for name, s in stops:
            base = simulate(df, s, comm_pts, 50, costs=False)
            real = simulate(df, s, comm_pts, seeds)
            opt = simulate(df, s, comm_pts, 50, fill="optimistic")
            pes = simulate(df, s, comm_pts, 50, fill="pessimistic")
            med_stop = float(np.median(s))
            rows.append(dict(
                inst=inst, stop=name,
                cost_R=(3 * TICK + 2 * comm_pts) / med_stop,
                trades=round(real["trades"]),
                wr_nocost=base["wr"], expR_nocost=base["expR"],
                wr=real["wr"], expR=real["expR"],
                p5=real["expR_p5"], p95=real["expR_p95"],
                expR_pessimistic=pes["expR"], expR_optimistic=opt["expR"],
                pf=real["pf"], usd_per_trade=real["pts_per_trade"] * pv,
                seeds_green=real["pct_seeds_profitable"],
            ))
            print(f"{inst:4s} {name:7s} done", flush=True)
    out = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    pd.set_option("display.float_format", lambda v: f"{v:.3f}")
    print("\n", out.to_string(index=False))
    out.to_csv(os.path.join(os.path.dirname(__file__), "half_r_results.csv"), index=False)

    # per-year stability for NQ at a representative stop
    print("\nNQ, 2xATR, by year (costs on):")
    pv, comm = CONTRACTS["NQ"]
    for y, g in df.groupby(df.index.year):
        r = simulate(g, 2 * atr14(g), comm / pv, 100)
        print(f"  {y}: trades {r['trades']:.0f}  WR {r['wr']:.3f}  exp {r['expR']:+.3f}R")


if __name__ == "__main__":
    main()
