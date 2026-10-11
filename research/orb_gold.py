"""Replicate the ORB study on gold, with the null test ORB passed on NQ.

WHY
---
ORB is the only strategy in this repo to beat its null test (p = 0.00 on NQ 5m,
7,063 trades, +0.022R). But it was measured on Dukascopy data that tracks the
CASH Nasdaq-100 index, whose opening prints are stale because its 100
constituents open staggered -- exactly where an opening-range strategy reads.
It then FAILED to replicate on ES (-0.042R) and YM (-0.003R).

Gold is the honest retest: free data, verified fidelity (XAUUSD vs GC futures,
0.9835 5m return correlation, 0.996 bar-range ratio), and no opening auction to
produce stale prints.

Gold has no single unambiguous "open", so three are tested and the null test is
run over the WHOLE grid, which is what prices the extra multiple comparisons:
  09:30 NY  -- equity cash open, which drives macro flow into gold
  08:20 NY  -- COMEX gold floor open
  03:00 NY  -- London open

Grid: 6 windows x 3 directions x 3 session opens = 54 configs.

Protocol, fixed before any result is seen (same as search_5m.py):
  1. Split 70/30 by time. The grid only sees the IN-SAMPLE half.
  2. Rank in-sample by expectancy, requiring >= 150 trades.
  3. Null test: rerun the ENTIRE grid on block-bootstrapped synthetic paths.
  4. Only if p <= 0.05, carry the single winner to OUT-OF-SAMPLE, once.

    .venv/bin/python research/orb_gold.py [data_dir] [null_reps]
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orb as O  # noqa: E402
import search as S  # noqa: E402
import search_5m as S5  # noqa: E402

# ── MGC cost model ───────────────────────────────────────────────────────────
S.MULTIPLIER = 10.0
S.COMMISSION_PTS = 0.62 / 10.0
S.SLIP_PTS = 0.10
O.COMMISSION_PTS = S.COMMISSION_PTS
O.SLIP = S.SLIP_PTS
O.TICK = 0.10

WINDOWS = (10, 15, 20, 30, 45, 60)
DIRECTIONS = ("both", "long", "short")
OPENS = {"09:30 NY equity": 930, "08:20 COMEX gold": 820, "03:00 London": 300}
MIN_TRADES = 150
MIN_RANGE_PTS = 0.5          # gold ranges are points, not NQ-sized


def grid(d):
    """Every (open, window, direction) config. Returns list of dicts."""
    rows = []
    for oname, ohm in OPENS.items():
        O.RTH_OPEN = ohm
        for w in WINDOWS:
            for dirn in DIRECTIONS:
                rs = O.orb_trades(d, w, 0.5, dirn, min_range_pts=MIN_RANGE_PTS)
                st = O.stats(rs)
                st.update(open=oname, window=w, dirn=dirn)
                rows.append(st)
    return rows


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/xauusd_5m"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    d = S5.load_dir(data_dir)
    n = len(d["c"])
    cut = int(n * 0.70)
    is_d, oos_d = S5.slice_data(d, 0, cut), S5.slice_data(d, cut, n)
    rt = 2 * S.COMMISSION_PTS + 2 * S.SLIP_PTS

    print(f"ORB on GOLD (XAUUSD -> GC/MGC)  {d['t'][0]:%Y-%m-%d} -> {d['t'][-1]:%Y-%m-%d}  {n:,} 5m bars")
    print(f"  IN-SAMPLE  {is_d['t'][0]:%Y-%m} -> {is_d['t'][-1]:%Y-%m}")
    print(f"  OUT-SAMPLE {oos_d['t'][0]:%Y-%m} -> {oos_d['t'][-1]:%Y-%m}")
    print(f"  cost {rt:.3f} pts round trip (${rt * 10:.2f} MGC) | bracket 0.5:1")
    print(f"  grid: {len(OPENS)} opens x {len(WINDOWS)} windows x {len(DIRECTIONS)} directions "
          f"= {len(OPENS) * len(WINDOWS) * len(DIRECTIONS)} configs\n")

    rows = [r for r in grid(is_d) if r["n"] >= MIN_TRADES]
    rows.sort(key=lambda r: -r["exp"])
    print(f"{len(rows)} configs qualified in-sample (>= {MIN_TRADES} trades)\n")
    print(f"  {'open':<17} {'win':>4} {'dir':>6} {'n':>6} {'WR':>6} {'exp(R)':>8} {'+/-95%':>8} {'PF':>5}")
    for r in rows[:12]:
        print(f"  {r['open']:<17} {r['window']:>3}m {r['dirn']:>6} {r['n']:>6} {r['wr']:>5.1%} "
              f"{r['exp']:>+8.3f} {r['ci']:>8.3f} {r['pf']:>5.2f}")
    if not rows:
        print("  nothing qualified.")
        return
    best = rows[0]

    print(f"\nNULL TEST on the in-sample half ({reps} synthetic paths, whole grid each time)")
    rng = np.random.default_rng(7)
    nulls = []
    for i in range(reps):
        fake = S.bootstrap(is_d, rng)
        frows = [r for r in grid(fake) if r["n"] >= MIN_TRADES]
        if frows:
            nulls.append(max(r["exp"] for r in frows))
            print(f"  rep {i + 1:2d}/{reps}: best on noise {nulls[-1]:+.3f}R", flush=True)
    nulls = np.array(nulls)
    p = float((nulls >= best["exp"]).mean())
    print(f"\n  best real {best['exp']:+.3f}R  ({best['open']} {best['window']}m {best['dirn']})")
    print(f"  noise mean {nulls.mean():+.3f}R  max {nulls.max():+.3f}R  |  p = {p:.3f}")
    print(f"  NQ reference: best real +0.034R, noise mean -0.031R, p = 0.00")

    if p > 0.05:
        print("\n  VERDICT: not distinguishable from data mining. Stop here.")
        return

    print("\n  Survived. Running ONCE on out-of-sample data:")
    O.RTH_OPEN = OPENS[best["open"]]
    st = O.stats(O.orb_trades(oos_d, best["window"], 0.5, best["dirn"],
                              min_range_pts=MIN_RANGE_PTS))
    print(f"  OOS: exp {st['exp']:+.3f}R +/- {st['ci']:.3f} over {st['n']} trades, "
          f"WR {st['wr']:.1%}, PF {st['pf']:.2f}")


if __name__ == "__main__":
    main()
