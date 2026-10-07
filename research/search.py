"""Bounded strategy search on NQ with a null test.

The point is NOT to find the best-looking combo — with 450 combos, the best one
looks good even on noise. The point is to ask whether the best combo on REAL data
beats the best combo on FAKE data drawn from the same price process. If it
doesn't, the honest answer is "nothing found", and we stop.

Method:
  1. Build 450 combos from 5 blocks (trend filter x entry trigger x session x
     exit x volatility filter). Small and motivated, not a kitchen sink.
  2. Simulate each on 2 years of free hourly NQ data, costs included:
     $0.62/contract/side commission + 1 tick slippage per side, expressed in
     MNQ points. Entry at the NEXT bar open (signals are on bar close).
  3. Rank by expectancy in R, requiring a minimum trade count.
  4. NULL TEST: block-bootstrap the returns into synthetic price paths (same
     volatility clustering, no real structure), rerun the whole grid on each,
     and record the best expectancy found. That distribution is what luck alone
     produces. A real edge has to sit outside it.

Survivors get validated on QuantConnect over 2019-2023 — data this search has
never seen, in a different regime.

    .venv/bin/python ../research/search.py            # search + null test
    NULL_REPS=0 .venv/bin/python ../research/search.py # search only (fast)
"""

import os
import sys
from datetime import timedelta
from zoneinfo import ZoneInfo

import numpy as np

NY = ZoneInfo("America/New_York")

TICK = 0.25
MULTIPLIER = 2.0                      # MNQ
COMMISSION_PTS = 0.62 / MULTIPLIER    # $/contract/side -> points
SLIP_PTS = TICK                       # per side
MIN_TRADES = 100
ATR_LEN = 14


# ── data ─────────────────────────────────────────────────────────────────────
def load_hourly():
    import yfinance as yf
    df = yf.download("NQ=F", interval="60m", period="730d", progress=False, prepost=True)
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    df = df.dropna(subset=["Open", "High", "Low", "Close"])
    idx = df.index.tz_convert(NY)
    return dict(
        t=idx,
        o=df["Open"].to_numpy(float), h=df["High"].to_numpy(float),
        l=df["Low"].to_numpy(float), c=df["Close"].to_numpy(float),
        hour=np.array([x.hour for x in idx]), day=np.array([x.date() for x in idx]),
        dow=np.array([x.weekday() for x in idx]),
    )


# ── indicators (numpy) ───────────────────────────────────────────────────────
def ema(x, n):
    a = 2 / (n + 1)
    out = np.empty_like(x)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rma(x, n):
    out = np.empty_like(x)
    out[:n] = np.nan
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n
    return out


def atr(h, l, c, n=ATR_LEN):
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return rma(tr, n)


def rsi(c, n=14):
    d = np.diff(c, prepend=c[0])
    up = rma(np.where(d > 0, d, 0.0), n)
    dn = rma(np.where(d < 0, -d, 0.0), n)
    rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
    return 100 - 100 / (1 + rs)


def rolling_max(x, n):
    out = np.full_like(x, np.nan)
    for i in range(n, len(x)):
        out[i] = x[i - n:i].max()
    return out


def rolling_min(x, n):
    out = np.full_like(x, np.nan)
    for i in range(n, len(x)):
        out[i] = x[i - n:i].min()
    return out


def sma(x, n):
    out = np.full_like(x, np.nan)
    cs = np.cumsum(np.insert(x, 0, 0.0))
    out[n - 1:] = (cs[n:] - cs[:-n]) / n
    return out


def rolling_std(x, n):
    out = np.full_like(x, np.nan)
    for i in range(n - 1, len(x)):
        out[i] = x[i - n + 1:i + 1].std()
    return out


# ── signal blocks ────────────────────────────────────────────────────────────
def build_blocks(d):
    c, h, l = d["c"], d["h"], d["l"]
    a = atr(h, l, c)
    r = rsi(c)
    e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
    dc_hi, dc_lo = rolling_max(h, 20), rolling_min(l, 20)
    m = ema(c, 12) - ema(c, 26)
    msig = ema(m, 9)
    mid, sd = sma(c, 20), rolling_std(c, 20)
    bb_up, bb_dn = mid + 2 * sd, mid - 2 * sd
    prev = lambda x: np.concatenate([[np.nan], x[:-1]])  # noqa: E731

    trends = {
        "none": (np.ones(len(c), bool), np.ones(len(c), bool)),
        "ema20>50": (e20 > e50, e20 < e50),
        "ema50>200": (e50 > e200, e50 < e200),
    }
    triggers = {
        "rsi_meanrev": (r < 30, r > 70),
        "rsi_mom": ((r > 55) & (prev(r) <= 55), (r < 45) & (prev(r) >= 45)),
        "donchian20": (c > dc_hi, c < dc_lo),
        "bb_fade": (c < bb_dn, c > bb_up),
        "macd_cross": ((m > msig) & (prev(m) <= prev(msig)), (m < msig) & (prev(m) >= prev(msig))),
    }
    sessions = {
        "morning": (d["hour"] >= 9) & (d["hour"] <= 11),
        "rth": (d["hour"] >= 9) & (d["hour"] <= 15),
        "all": np.ones(len(c), bool),
    }
    med_atr = np.nanmedian(a)
    vol_filters = {"none": np.ones(len(c), bool), "atr>median": a > med_atr}
    exits = {"1.0/2.0": (1.0, 2.0), "1.5/2.25": (1.5, 2.25), "2.0/3.0": (2.0, 3.0),
             "2.0/1.0": (2.0, 1.0), "1.5/3.0": (1.5, 3.0)}
    return a, trends, triggers, sessions, vol_filters, exits


# ── one simulation ───────────────────────────────────────────────────────────
def simulate(d, a, long_sig, short_sig, sl_mult, tp_mult):
    """Entry next bar open, bracket from fill, stop-first inside a bar, flat at day end."""
    o, h, l, c, day = d["o"], d["h"], d["l"], d["c"], d["day"]
    n = len(c)
    rs = []
    pos = 0
    entry = stop = target = risk = 0.0
    pending = 0

    for i in range(ATR_LEN + 200, n):
        if pending and pos == 0:
            entry = o[i] + pending * SLIP_PTS
            risk = a[i - 1] * sl_mult
            if risk > 0:
                stop = entry - pending * risk
                target = entry + pending * a[i - 1] * tp_mult
                pos = pending
            pending = 0

        if pos:
            exit_px = None
            if pos > 0:
                if l[i] <= stop:
                    exit_px = min(o[i], stop) - SLIP_PTS
                elif h[i] >= target:
                    exit_px = target
            else:
                if h[i] >= stop:
                    exit_px = max(o[i], stop) + SLIP_PTS
                elif l[i] <= target:
                    exit_px = target
            if exit_px is None and (i + 1 >= n or day[i + 1] != day[i]):
                exit_px = c[i] - pos * SLIP_PTS
            if exit_px is not None:
                pnl = (exit_px - entry) * pos - 2 * COMMISSION_PTS
                rs.append(pnl / risk)
                pos = 0

        if pos == 0 and not pending and i + 1 < n and day[i + 1] == day[i]:
            if long_sig[i]:
                pending = 1
            elif short_sig[i]:
                pending = -1

    return np.array(rs)


def stats(rs):
    n = len(rs)
    if n == 0:
        return dict(n=0, exp=0.0, pf=0.0, wr=0.0, total=0.0, mdd=0.0)
    wins, losses = rs[rs > 0], rs[rs <= 0]
    gl = -losses.sum()
    eq = np.cumsum(rs)
    peak = np.maximum.accumulate(np.concatenate([[0.0], eq]))[1:]
    return dict(n=n, exp=float(rs.mean()), pf=float(wins.sum() / gl) if gl > 0 else float("inf"),
                wr=float((rs > 0).mean()), total=float(rs.sum()), mdd=float((peak - eq).max()))


def run_grid(d, verbose=False):
    a, trends, triggers, sessions, vols, exits = build_blocks(d)
    rows = []
    for tname, (tl, ts) in trends.items():
        for gname, (gl, gs) in triggers.items():
            for sname, smask in sessions.items():
                for vname, vmask in vols.items():
                    base_l = tl & gl & smask & vmask
                    base_s = ts & gs & smask & vmask
                    for ename, (sl_m, tp_m) in exits.items():
                        st = stats(simulate(d, a, base_l, base_s, sl_m, tp_m))
                        st.update(trend=tname, trigger=gname, session=sname, vol=vname, exit=ename)
                        rows.append(st)
    if verbose:
        print(f"  evaluated {len(rows)} combos")
    return rows


# ── null: block bootstrap ────────────────────────────────────────────────────
def bootstrap(d, rng, block=24):
    """Synthetic path with the same return distribution and volatility clustering,
    but no real structure. Bar shapes are carried along with their return."""
    c = d["c"]
    ret = np.diff(np.log(c), prepend=0.0)
    rng_idx = []
    while len(rng_idx) < len(c):
        s = rng.integers(0, max(1, len(c) - block))
        rng_idx.extend(range(s, s + block))
    idx = np.array(rng_idx[:len(c)])
    new_c = c[0] * np.exp(np.cumsum(ret[idx]))
    scale = new_c / c[idx]
    return dict(d, o=d["o"][idx] * scale, h=d["h"][idx] * scale,
                l=d["l"][idx] * scale, c=new_c)


def main():
    reps = int(os.environ.get("NULL_REPS", "20"))
    d = load_hourly()
    print(f"Data {d['t'][0]:%Y-%m-%d} -> {d['t'][-1]:%Y-%m-%d}  ({len(d['c'])} hourly bars, NQ=F, MNQ costs)")
    print(f"Costs: {COMMISSION_PTS * 2:.2f} pts round-trip commission + {SLIP_PTS} pt slippage per side\n")

    rows = run_grid(d, verbose=True)
    ok = [r for r in rows if r["n"] >= MIN_TRADES]
    ok.sort(key=lambda r: -r["exp"])
    print(f"  {len(ok)} of {len(rows)} combos had >= {MIN_TRADES} trades\n")

    print("TOP 10 ON REAL DATA")
    print(f"  {'exp(R)':>7} {'PF':>5} {'WR':>6} {'n':>5} {'totalR':>8}  strategy")
    for r in ok[:10]:
        print(f"  {r['exp']:+7.3f} {r['pf']:5.2f} {r['wr']:6.1%} {r['n']:5d} {r['total']:+8.1f}  "
              f"{r['trigger']} | {r['trend']} | {r['session']} | vol:{r['vol']} | SL/TP {r['exit']}")

    if reps <= 0 or not ok:
        return
    best_real = ok[0]["exp"]

    print(f"\nNULL TEST — same grid on {reps} synthetic price paths")
    rng = np.random.default_rng(42)
    null_best = []
    for i in range(reps):
        fake = bootstrap(d, rng)
        frows = [r for r in run_grid(fake) if r["n"] >= MIN_TRADES]
        if frows:
            b = max(r["exp"] for r in frows)
            null_best.append(b)
            print(f"  rep {i + 1:2d}/{reps}  best expectancy on noise: {b:+.3f}R")
        sys.stdout.flush()

    null_best = np.array(null_best)
    pct = float((null_best >= best_real).mean())
    print(f"\n  best on REAL data      {best_real:+.3f}R")
    print(f"  best on noise: mean    {null_best.mean():+.3f}R   max {null_best.max():+.3f}R")
    print(f"  p-value (noise >= real) {pct:.2f}")
    print("\n  VERDICT:", "real edge candidate — validate out-of-sample" if pct <= 0.05
          else "NOT distinguishable from data mining — do not trade this")


if __name__ == "__main__":
    main()
