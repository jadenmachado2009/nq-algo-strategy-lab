"""The same bounded search and null test as search_5m.py, on gold instead of NQ.

WHY GOLD
--------
The NQ studies ran on Dukascopy data that tracks the CASH Nasdaq-100 index, whose
opening prints are stale because its 100 constituents open staggered. Gold has no
such problem: spot gold trades continuously with no opening auction, and it
arbitrages against its future in ONE trade rather than 100.

Measured fidelity of XAUUSD spot against GC futures (5m bars, ~55 days):
    5m return correlation 0.9835 | bar-range ratio 0.996
versus EURUSD->6E at 0.9673/1.050 and GBPUSD->6B at 0.9679/1.140. Gold's bars are
effectively the futures' bars, so a backtest here means what it says.

Gold is tradeable on Topstep as GC (full) or MGC (micro), both liquid.

COSTS, AND THE ONE RESTRICTION THIS APPLIES
-------------------------------------------
MGC: 10 oz, tick 0.10 pts = $1, $10/point. Commission $0.62/side, 1 tick slippage
per side -> 0.324 pts round trip ($3.24).

Gold is MORE expensive than NQ relative to its own volatility, which was not the
expectation going in:

    session (NY)             median 5m ATR    drag @1xATR   @3xATR
    all hours                     1.35            0.241       0.080
    NY morning 08:00-11:30        2.21            0.147       0.049
    NY RTH 09:30-16:00            1.85            0.175       0.058
    Asia 19:00-02:00              0.99            0.326       0.109
    (NQ for reference              11.6            0.097       0.032)

So ONE restriction is applied, fixed before looking at any result: **stops of at
least 1.5xATR**. At 1.5x in the NY session the drag is about 0.098R, which matches
NQ's 1xATR baseline. A 1xATR stop on gold costs 0.147R per trade, which is past
the prop break-even line before the strategy does anything at all.

The grid's sessions are already NY-only, so Asia is excluded automatically.
Grid: 3 trends x 5 triggers x 3 sessions x 2 vol filters x 4 exits = 360 combos.

Protocol is identical to search_5m.py and fixed in advance:
  1. Split 70/30 by time. The grid only sees the IN-SAMPLE half.
  2. Rank in-sample by expectancy, requiring >= 150 trades.
  3. Null test: rerun the whole grid on block-bootstrapped synthetic paths.
  4. Only if p <= 0.05, carry the single winner to OUT-OF-SAMPLE, once.

    .venv/bin/python research/search_gold.py [data_dir] [null_reps]
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search as S  # noqa: E402
import search_5m as S5  # noqa: E402

# ── MGC cost model ───────────────────────────────────────────────────────────
S.MULTIPLIER = 10.0                 # $/point on MGC
S.COMMISSION_PTS = 0.62 / 10.0      # $/contract/side -> points
S.SLIP_PTS = 0.10                   # one tick per side

MIN_STOP_ATR = 1.5                  # pre-committed, see docstring
MIN_TRADES = S5.MIN_TRADES

_orig_build = S.build_blocks


def build_blocks_gold(d):
    """build_blocks, with stops below MIN_STOP_ATR removed."""
    a, trends, triggers, sessions, vols, exits = _orig_build(d)
    exits = {k: v for k, v in exits.items() if v[0] >= MIN_STOP_ATR}
    return a, trends, triggers, sessions, vols, exits


S.build_blocks = build_blocks_gold


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/xauusd_5m"
    reps = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    d = S5.load_dir(data_dir)
    n = len(d["c"])
    cut = int(n * S5.IS_FRACTION)
    is_d, oos_d = S5.slice_data(d, 0, cut), S5.slice_data(d, cut, n)

    a = S.atr(d["h"], d["l"], d["c"])
    med = float(np.nanmedian(a))
    rt = 2 * S.COMMISSION_PTS + 2 * S.SLIP_PTS

    print(f"GOLD (XAUUSD -> GC/MGC)  {d['t'][0]:%Y-%m-%d} -> {d['t'][-1]:%Y-%m-%d}  {n:,} 5m bars")
    print(f"  IN-SAMPLE  {is_d['t'][0]:%Y-%m} -> {is_d['t'][-1]:%Y-%m}  ({cut:,} bars)")
    print(f"  OUT-SAMPLE {oos_d['t'][0]:%Y-%m} -> {oos_d['t'][-1]:%Y-%m}  ({n - cut:,} bars)")
    print(f"  cost {rt:.3f} pts round trip (${rt * 10:.2f} MGC) | median ATR {med:.2f} pts")
    print(f"  stops restricted to >= {MIN_STOP_ATR}xATR  -> drag <= {rt / (MIN_STOP_ATR * med):.3f}R")
    print(f"  min trades to qualify: {MIN_TRADES}\n")

    rows = [r for r in S5.run_grid_5m(is_d) if r["n"] >= MIN_TRADES]
    rows.sort(key=lambda r: -r["exp"])
    print(f"{len(rows)} combos qualified in-sample\n")
    print(f"  {'exp(R)':>7} {'PF':>5} {'WR':>6} {'n':>6} {'CI95':>17}  strategy")
    for r in rows[:10]:
        half = 1.96 * 1.4 / np.sqrt(r["n"])
        print(f"  {r['exp']:+7.3f} {r['pf']:5.2f} {r['wr']:6.1%} {r['n']:6d} "
              f"[{r['exp'] - half:+.3f},{r['exp'] + half:+.3f}]  {S5.describe(r)}")
    if not rows:
        print("  nothing qualified.")
        return
    best = rows[0]

    print(f"\nNULL TEST on the in-sample half ({reps} synthetic paths)")
    rng = np.random.default_rng(7)
    nulls = []
    for i in range(reps):
        fake = S.bootstrap(is_d, rng)
        frows = [r for r in S5.run_grid_5m(fake) if r["n"] >= MIN_TRADES]
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
    a2, trends, triggers, _, vols, exits = S.build_blocks(oos_d)
    sess = S5.sessions_5m(oos_d)
    tl, ts = trends[best["trend"]]
    gl, gs = triggers[best["trigger"]]
    sm, vm = sess[best["session"]], vols[best["vol"]]
    sl_m, tp_m = exits[best["exit"]]
    st = S.stats(S.simulate(oos_d, a2, tl & gl & sm & vm, ts & gs & sm & vm, sl_m, tp_m))
    half = 1.96 * 1.4 / np.sqrt(max(st["n"], 1))
    print(f"  OOS: exp {st['exp']:+.3f}R  PF {st['pf']:.2f}  WR {st['wr']:.1%}  n {st['n']}  "
          f"CI95 [{st['exp'] - half:+.3f},{st['exp'] + half:+.3f}]")
    print(f"  prop break-even is about -0.075R; zero-edge baseline about -0.02R")


if __name__ == "__main__":
    main()
