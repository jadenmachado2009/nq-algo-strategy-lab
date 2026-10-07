"""The same bounded search as search.py, but on multi-year 5-minute data.

Why this run exists: on 2.4 years of hourly data each combo produced 150-320
trades, so the 95% confidence interval on its edge was about +/-0.15R — wider
than the whole decision (the prop break-even line sits at -0.075R). Detecting a
+0.10R edge needs ~750 trades; +0.05R needs ~3,000. Only 5-minute data over
several years gets us there.

Protocol, fixed before looking at any result:
  1. Split the data 70/30 by time. The grid only ever sees the IN-SAMPLE part.
  2. Rank in-sample by expectancy, requiring >= MIN_TRADES.
  3. Null test on the in-sample half: rerun the whole grid on block-bootstrapped
     synthetic paths. p = fraction of noise runs whose best combo beats ours.
  4. Only if p <= 0.05, carry the single in-sample winner to OUT-OF-SAMPLE,
     untouched, once. That number is the honest one.

Data: Dukascopy US_TECH (Nasdaq 100), 5-minute, RTH. Costs are MNQ's.

    .venv/bin/python ../research/search_5m.py <data_dir> [null_reps]
"""

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search as S  # noqa: E402

NY = S.NY
MIN_TRADES = 150
IS_FRACTION = 0.70


def load_dir(path):
    files = sorted(glob.glob(os.path.join(path, "*.csv")))
    if not files:
        raise SystemExit(f"no CSVs in {path}")
    df = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True) for f in files])
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[df["close"] > 0]
    idx = df.index.tz_convert(NY)
    return dict(
        t=idx,
        o=df["open"].to_numpy(float), h=df["high"].to_numpy(float),
        l=df["low"].to_numpy(float), c=df["close"].to_numpy(float),
        hour=np.array([x.hour for x in idx]), minute=np.array([x.minute for x in idx]),
        day=np.array([x.date() for x in idx]), dow=np.array([x.weekday() for x in idx]),
    )


def slice_data(d, lo, hi):
    sl = slice(lo, hi)
    return {k: (v[sl] if hasattr(v, "__len__") else v) for k, v in d.items()}


def sessions_5m(d):
    """Session masks on 5m bars, New York time."""
    hm = d["hour"] * 100 + d["minute"]
    return {
        "open30": (hm >= 930) & (hm < 1000),
        "morning": (hm >= 930) & (hm <= 1130),
        "rth": (hm >= 930) & (hm <= 1555),
    }


def run_grid_5m(d):
    a, trends, triggers, _, vols, exits = S.build_blocks(d)
    sessions = sessions_5m(d)
    rows = []
    for tname, (tl, ts) in trends.items():
        for gname, (gl, gs) in triggers.items():
            for sname, smask in sessions.items():
                for vname, vmask in vols.items():
                    bl, bs = tl & gl & smask & vmask, ts & gs & smask & vmask
                    for ename, (sl_m, tp_m) in exits.items():
                        st = S.stats(S.simulate(d, a, bl, bs, sl_m, tp_m))
                        st.update(trend=tname, trigger=gname, session=sname, vol=vname, exit=ename)
                        rows.append(st)
    return rows


def describe(r):
    return f"{r['trigger']} | {r['trend']} | {r['session']} | vol:{r['vol']} | SL/TP {r['exit']}"


def main():
    data_dir = sys.argv[1]
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 20

    d = load_dir(data_dir)
    n = len(d["c"])
    cut = int(n * IS_FRACTION)
    is_d, oos_d = slice_data(d, 0, cut), slice_data(d, cut, n)
    print(f"Data {d['t'][0]:%Y-%m-%d} -> {d['t'][-1]:%Y-%m-%d}  ({n:,} 5m bars)")
    print(f"  IN-SAMPLE  {is_d['t'][0]:%Y-%m-%d} -> {is_d['t'][-1]:%Y-%m-%d}  ({cut:,} bars)")
    print(f"  OUT-SAMPLE {oos_d['t'][0]:%Y-%m-%d} -> {oos_d['t'][-1]:%Y-%m-%d}  ({n - cut:,} bars)")
    print(f"  min trades to qualify: {MIN_TRADES}")

    # Sanity guard. The cost model is in MNQ points, so the data must be on the
    # same scale. A wrong instrument (e.g. a CFD quoted at 43-99 instead of
    # ~20,000) silently turns every trade into a multi-R loss, which looks like
    # "every strategy fails" rather than "wrong data".
    med_atr = float(np.nanmedian(S.atr(d["h"], d["l"], d["c"])))
    drag = (2 * S.COMMISSION_PTS + 2 * S.SLIP_PTS) / med_atr
    print(f"  price {d['c'].min():,.0f}-{d['c'].max():,.0f} | median 5m ATR {med_atr:.1f} pts "
          f"| cost drag at 1xATR stop {drag:.3f}R")
    if drag > 0.2:
        raise SystemExit("  ABORT: cost drag implausible — wrong instrument or wrong price scale.")
    print()

    rows = [r for r in run_grid_5m(is_d) if r["n"] >= MIN_TRADES]
    rows.sort(key=lambda r: -r["exp"])
    print(f"{len(rows)} combos qualified in-sample\n")
    print(f"  {'exp(R)':>7} {'PF':>5} {'WR':>6} {'n':>6} {'CI95':>16}  strategy")
    for r in rows[:10]:
        half = 1.96 * 1.4 / np.sqrt(r["n"])
        print(f"  {r['exp']:+7.3f} {r['pf']:5.2f} {r['wr']:6.1%} {r['n']:6d} "
              f"[{r['exp'] - half:+.3f},{r['exp'] + half:+.3f}]  {describe(r)}")
    if not rows:
        return
    best = rows[0]

    print(f"\nNULL TEST on the in-sample half ({reps} synthetic paths)")
    rng = np.random.default_rng(7)
    nulls = []
    for i in range(reps):
        fake = S.bootstrap(is_d, rng)
        frows = [r for r in run_grid_5m(fake) if r["n"] >= MIN_TRADES]
        if frows:
            nulls.append(max(r["exp"] for r in frows))
            print(f"  rep {i + 1:2d}/{reps}: best on noise {nulls[-1]:+.3f}R", flush=True)
    nulls = np.array(nulls)
    p = float((nulls >= best["exp"]).mean())
    print(f"\n  best real {best['exp']:+.3f}R | noise mean {nulls.mean():+.3f}R "
          f"max {nulls.max():+.3f}R | p = {p:.3f}")

    if p > 0.05:
        print("\n  VERDICT: not distinguishable from data mining. Stop here.")
        return

    print("\n  Survived the null test. Running it ONCE on out-of-sample data:")
    a, trends, triggers, _, vols, exits = S.build_blocks(oos_d)
    sess = sessions_5m(oos_d)
    tl, ts = trends[best["trend"]]
    gl, gs = triggers[best["trigger"]]
    sm, vm = sess[best["session"]], vols[best["vol"]]
    sl_m, tp_m = exits[best["exit"]]
    st = S.stats(S.simulate(oos_d, a, tl & gl & sm & vm, ts & gs & sm & vm, sl_m, tp_m))
    half = 1.96 * 1.4 / np.sqrt(max(st["n"], 1))
    print(f"  OOS: exp {st['exp']:+.3f}R  PF {st['pf']:.2f}  WR {st['wr']:.1%}  n {st['n']}  "
          f"CI95 [{st['exp'] - half:+.3f},{st['exp'] + half:+.3f}]")
    print(f"  prop break-even line is -0.075R; zero-edge baseline is about -0.02R")


if __name__ == "__main__":
    main()
