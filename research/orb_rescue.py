"""Can ORB be repaired? Target sweep via exact MFE reconstruction. 2026-10-17.

THE QUESTION
------------
ORB's 0.5:1 bracket needs ~67% of trades to reach target before stop. Since
2026Q3 the win rate is ~49-54% and median MFE fell 0.52 -> 0.40. The obvious
"fix" is to retarget. Does any target work?

METHOD -- no refitting
----------------------
Run each trade with NO target (rr = inf) so it exits only at stop or EOD, and
record its maximum favourable excursion. A trade with a target at rr wins iff
its MFE reaches rr BEFORE the stop -- and MFE is recorded path-wise up to the
stop, so that condition is exact. If MFE < rr the trade ends identically to the
no-target case. One pass therefore reconstructs EVERY target exactly, with no
extra data mining: the sweep adds no degrees of freedom the original study
did not already have.

Validated against orb.orb_trades(rr=0.5) -- must agree trade for trade.

PROTOCOL, fixed before any result is seen
  1. BASELINE = 2019-01-01 .. 2026-06-30. The sweep is read here only.
  2. BREAK    = 2026-07-01 .. end. Evaluated ONCE, after the baseline is read.
  3. A target chosen because it survives BREAK is a fit, and is reported as one.

    .venv/bin/python research/orb_rescue.py [data_dir]
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orb as O          # noqa: E402
import search_5m as S5   # noqa: E402

RR_GRID = (0.25, 0.30, 0.40, 0.50, 0.60, 0.75, 1.00, 1.25, 1.50, 2.00)
WINDOWS = (10, 20, 30, 45, 60)
BREAK_START = "2026-07-01"


def trades_no_target(d, window_min):
    """ORB long-only with no target. Returns one record per trade.

    Mirrors orb.orb_trades exactly except that the target is never placed, so
    the trade runs to its stop or to the session close.
    """
    hm = d["hour"] * 100 + d["minute"]
    day, o, h, l, c = d["day"], d["o"], d["h"], d["l"], d["c"]
    n = len(c)
    out, i = [], 0
    while i < n:
        today = day[i]
        j = i
        while j < n and day[j] == today:
            j += 1
        idx = np.arange(i, j)
        i = j
        session = idx[hm[idx] >= O.RTH_OPEN]
        if len(session) < 10:
            continue
        open_min = (O.RTH_OPEN // 100) * 60 + (O.RTH_OPEN % 100) + window_min
        sess_min = (hm[session] // 100) * 60 + (hm[session] % 100)
        rng_bars = session[sess_min < open_min]
        rest = session[sess_min >= open_min]
        if len(rng_bars) < 1 or len(rest) < 3:
            continue
        hi, lo = h[rng_bars].max(), l[rng_bars].min()
        if hi - lo < 2 * O.TICK:
            continue
        trig = next((rest[k] for k in range(len(rest) - 1) if c[rest[k]] > hi), None)
        if trig is None:
            continue
        ei = trig + 1
        if ei >= n or day[ei] != today:
            continue
        entry = o[ei] + O.SLIP
        risk = entry - lo
        if risk < O.TICK:
            continue
        mfe, stopped, exit_px = 0.0, False, None
        for m in range(ei, j):
            # Stop is checked FIRST, as orb.py does: a bar that touches both the
            # stop and the target is a loss, so its high must not reach MFE.
            if l[m] <= lo:
                exit_px, stopped = min(o[m], lo) - O.SLIP, True
                break
            mfe = max(mfe, (h[m] - entry) / risk)
        if exit_px is None:
            exit_px = c[j - 1] - O.SLIP
        out.append(dict(day=today, window=window_min, risk=risk, mfe=mfe,
                        stopped=stopped,
                        r_notarget=((exit_px - entry) - 2 * O.COMMISSION_PTS) / risk,
                        comm_r=2 * O.COMMISSION_PTS / risk,
                        cost_r=(2 * O.COMMISSION_PTS + 2 * O.SLIP) / risk))
    return out


def apply_target(rows, rr):
    """Exact R-multiple for each trade had a target been placed at rr."""
    r = np.empty(len(rows))
    for k, t in enumerate(rows):
        if t["mfe"] >= rr:
            r[k] = rr - t["comm_r"]          # limit fill: commission only
        else:
            r[k] = t["r_notarget"]           # path unchanged: stop or EOD
    return r


def clustered_ci(r, days, reps=2000, seed=7):
    """Resample whole sessions -- same-day trades share one price path."""
    uniq, inv = np.unique(days, return_inverse=True)
    buckets = [np.where(inv == k)[0] for k in range(len(uniq))]
    rng = np.random.default_rng(seed)
    boot = np.empty(reps)
    for b in range(reps):
        pick = rng.integers(0, len(buckets), len(buckets))
        boot[b] = r[np.concatenate([buckets[p] for p in pick])].mean()
    return np.percentile(boot, [2.5, 97.5]), float(np.mean(boot > 0))


def collect(d):
    rows = []
    for w in WINDOWS:
        rows += trades_no_target(d, w)
    return rows


def sweep(rows, label, show_ci=True):
    days = np.array([str(t["day"]) for t in rows])
    cost = float(np.median([t["cost_r"] for t in rows]))
    mfe = np.array([t["mfe"] for t in rows])
    print(f"\n{label}   n={len(rows):,} trades on {len(set(days)):,} sessions"
          f"   median cost {cost:.4f}R")
    print(f"  median MFE {np.median(mfe):.3f}   "
          f"P(MFE>=0.5) {np.mean(mfe >= 0.5):.1%}   P(MFE>=1.0) {np.mean(mfe >= 1.0):.1%}")
    print(f"\n  {'target':>7} {'WR':>7} {'need':>7} {'margin':>7} {'exp(R)':>9} "
          f"{'95% CI':>22} {'P(>0)':>7}")
    best = None
    for rr in RR_GRID:
        r = apply_target(rows, rr)
        wr = float(np.mean(r > 0))
        need = (1 + cost) / (1 + rr)          # break-even WR for this bracket
        exp = float(r.mean())
        if show_ci:
            (lo, hi), p = clustered_ci(r, days)
            ci = f"[{lo:+.4f}, {hi:+.4f}]"
            ps = f"{p:.1%}"
        else:
            ci, ps = "", ""
        star = " *" if rr == 0.50 else "  "
        print(f"  {rr:>6.2f}{star}{wr:>6.1%} {need:>6.1%} {wr - need:>+6.1%} "
              f"{exp:>+9.4f} {ci:>22} {ps:>7}")
        if best is None or exp > best[1]:
            best = (rr, exp)
    return best, cost


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/nq_5m"
    d = S5.load_dir(data_dir)
    dates = np.array([str(x) for x in d["day"]])

    # ---- self-check: reconstruction must equal the real engine at rr = 0.5
    chk = trades_no_target(S5.slice_data(d, 0, 60000), 30)
    ref = O.orb_trades(S5.slice_data(d, 0, 60000), 30, 0.5, "long")
    rec = apply_target(chk, 0.5)
    ok = len(ref) == len(rec) and np.allclose(ref, rec, atol=1e-9)
    print(f"RECONSTRUCTION CHECK  n_ref={len(ref)} n_rec={len(rec)}  "
          f"max|diff|={np.max(np.abs(ref - rec)) if ok or len(ref)==len(rec) else float('nan'):.2e}  "
          f"-> {'EXACT' if ok else 'MISMATCH — STOP'}")
    if not ok:
        raise SystemExit("reconstruction does not match the engine; results void")

    cut = int(np.searchsorted(dates, BREAK_START))
    base_d, brk_d = S5.slice_data(d, 0, cut), S5.slice_data(d, cut, len(dates))
    print(f"\ndata {dates[0]} -> {dates[-1]}  ({len(dates):,} 5m bars)")
    print(f"  BASELINE {dates[0]} -> {dates[cut-1]}")
    print(f"  BREAK    {dates[cut]} -> {dates[-1]}")

    base, brk = collect(base_d), collect(brk_d)
    b_best, _ = sweep(base, "BASELINE  (the sweep is read here only)")
    print(f"\n  baseline-optimal target: {b_best[0]:.2f} at {b_best[1]:+.4f}R")

    k_best, _ = sweep(brk, "BREAK  (evaluated once, after the baseline was read)")
    print(f"\n  break-optimal target: {k_best[0]:.2f} at {k_best[1]:+.4f}R  "
          f"<- choosing THIS would be a fit to the drawdown")


if __name__ == "__main__":
    main()


def decompose(rows, label):
    """Outcome mix and dispersion per target. Pass rate needs both moments."""
    days = np.array([str(t["day"]) for t in rows])
    mfe = np.array([t["mfe"] for t in rows])
    stopped = np.array([t["stopped"] for t in rows])
    print(f"\n{label}  outcome mix and dispersion")
    print(f"  {'target':>7} {'target%':>8} {'stop%':>7} {'eod%':>7} "
          f"{'mean':>8} {'sd':>7} {'mean/sd':>8} {'eodR':>8}")
    for rr in RR_GRID:
        r = apply_target(rows, rr)
        hit = mfe >= rr
        st = (~hit) & stopped
        eod = (~hit) & (~stopped)
        print(f"  {rr:>6.2f} {np.mean(hit):>8.1%} {np.mean(st):>7.1%} {np.mean(eod):>7.1%} "
              f"{r.mean():>+8.4f} {r.std():>7.3f} {r.mean()/r.std():>8.4f} "
              f"{(r[eod].mean() if eod.sum() else 0):>+8.3f}")
    print(f"  trades/session {len(rows)/len(set(days)):.2f}")
