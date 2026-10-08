"""Opening Range Breakout on NQ, swept the way the video's heatmap is laid out.

The video's funded-phase chart sweeps "opening minutes" (10/15/20/30/45/60) against
direction (both/long/short), with a 0.5:1 bracket. This reproduces that grid on
7.8 years of real 5-minute data, with costs, and splits in-sample / out-of-sample.

Rules per day:
  - build the opening range from the first W minutes after 09:30 NY
  - first 5m close beyond the range triggers an entry at the NEXT bar's open
  - stop at the opposite side of the range; target = RR x stop distance
  - one trade per day, flat by the close
  - costs: commission + 1 tick slippage per side, stop-first inside a bar

A positive expectancy here is what would lift a prop pass rate above the ~40%
zero-edge ceiling, so this is tested against the same null discipline as
everything else: in-sample first, out-of-sample once, untouched.

    .venv/bin/python ../research/orb.py <data_dir>
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search as S  # noqa: E402
import search_5m as S5  # noqa: E402

TICK = 0.25
COMMISSION_PTS = S.COMMISSION_PTS
SLIP = S.SLIP_PTS
RTH_OPEN = 930


def orb_trades(d, window_min, rr, direction="both", min_range_pts=0.0):
    """Returns R-multiples, one trade per day at most."""
    hm = d["hour"] * 100 + d["minute"]
    day = d["day"]
    o, h, l, c = d["o"], d["h"], d["l"], d["c"]
    n = len(c)
    rs = []

    i = 0
    while i < n:
        today = day[i]
        # indices for this day
        j = i
        while j < n and day[j] == today:
            j += 1
        idx = np.arange(i, j)
        i = j
        session = idx[(hm[idx] >= RTH_OPEN)]
        if len(session) < 10:
            continue
        open_end = RTH_OPEN + (window_min // 60) * 100 + (window_min % 60)
        rng_bars = session[hm[session] < open_end]
        rest = session[hm[session] >= open_end]
        if len(rng_bars) < 1 or len(rest) < 3:
            continue
        hi, lo = h[rng_bars].max(), l[rng_bars].min()
        width = hi - lo
        if width < max(min_range_pts, 2 * TICK):
            continue

        # first close beyond the range
        trig = None
        for k in range(len(rest) - 1):
            b = rest[k]
            if c[b] > hi and direction in ("both", "long"):
                trig = (b, 1)
                break
            if c[b] < lo and direction in ("both", "short"):
                trig = (b, -1)
                break
        if trig is None:
            continue
        b, dirn = trig
        entry_i = b + 1
        if entry_i >= n or day[entry_i] != today:
            continue
        entry = o[entry_i] + dirn * SLIP
        stop = lo if dirn > 0 else hi
        risk = abs(entry - stop)
        if risk < TICK:
            continue
        target = entry + dirn * risk * rr

        exit_px = None
        for m in range(entry_i, j):
            if dirn > 0:
                if l[m] <= stop:
                    exit_px = min(o[m], stop) - SLIP
                elif h[m] >= target:
                    exit_px = target
            else:
                if h[m] >= stop:
                    exit_px = max(o[m], stop) + SLIP
                elif l[m] <= target:
                    exit_px = target
            if exit_px is not None:
                break
        if exit_px is None:
            exit_px = c[j - 1] - dirn * SLIP
        rs.append(((exit_px - entry) * dirn - 2 * COMMISSION_PTS) / risk)
    return np.array(rs)


def stats(rs):
    if len(rs) == 0:
        return dict(n=0, wr=0, exp=0, pf=0, ci=0)
    w, l = rs[rs > 0], rs[rs <= 0]
    return dict(n=len(rs), wr=len(w) / len(rs), exp=rs.mean(),
                pf=w.sum() / -l.sum() if len(l) and l.sum() != 0 else float("inf"),
                ci=1.96 * rs.std() / np.sqrt(len(rs)))


def main():
    data_dir = sys.argv[1]
    d = S5.load_dir(data_dir)
    n = len(d["c"])
    cut = int(n * 0.70)
    is_d, oos_d = S5.slice_data(d, 0, cut), S5.slice_data(d, cut, n)
    print(f"ORB on 5m NQ | IS {is_d['t'][0]:%Y-%m} -> {is_d['t'][-1]:%Y-%m} | "
          f"OOS {oos_d['t'][0]:%Y-%m} -> {oos_d['t'][-1]:%Y-%m}")
    print("Bracket: stop at opposite side of the opening range, target = 0.5 x stop\n")
    print(f"  {'window':>7} {'dir':>6} {'n(IS)':>6} {'WR':>6} {'exp(R)':>8} {'+/-95%':>8} {'PF':>5}")
    rows = []
    for w in (10, 15, 20, 30, 45, 60):
        for dirn in ("both", "long", "short"):
            st = stats(orb_trades(is_d, w, 0.5, dirn))
            if st["n"] < 100:
                continue
            rows.append((w, dirn, st))
            print(f"  {w:>6}m {dirn:>6} {st['n']:>6} {st['wr']:>5.1%} {st['exp']:>+8.3f} "
                  f"{st['ci']:>8.3f} {st['pf']:>5.2f}")
    if not rows:
        return
    best = max(rows, key=lambda r: r[2]["exp"])
    w, dirn, st = best
    print(f"\n  best in-sample: {w}m {dirn}  exp {st['exp']:+.3f}R over {st['n']} trades")
    oos = stats(orb_trades(oos_d, w, 0.5, dirn))
    print(f"  OUT-OF-SAMPLE:  exp {oos['exp']:+.3f}R +/- {oos['ci']:.3f} over {oos['n']} trades, "
          f"WR {oos['wr']:.1%}, PF {oos['pf']:.2f}")
    print(f"\n  zero-edge reference: -0.02R | prop break-even: about -0.12R")


if __name__ == "__main__":
    main()
