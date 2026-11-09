"""Monte Carlo on the Topstep challenge, with the edge itself treated as unknown.

WHAT WAS ALREADY MONTE CARLO
----------------------------
Everything. topstep.py runs 40,000 paths; the null tests block-bootstrap synthetic
price paths; every confidence interval in this repo is a day-clustered bootstrap
at 2,000-20,000 reps. The sims are not the gap.

WHAT WAS MISSING
----------------
All of them condition on a KNOWN edge. The pass rate is reported as a single
number for "ORB's +0.0514R", when the day-clustered 95% interval on that edge runs
from about -0.02R to +0.08R -- and the edge-sensitivity table says pass rate
across that span moves from 26% to 60%. Fixing the edge at its point estimate
reports the precision of an input nobody has.

Three things are added here:

  1. PARAMETER UNCERTAINTY. Each path draws its own true edge from the
     day-clustered bootstrap distribution of the pool mean (bootstrap-as-posterior),
     so the output integrates over what is not known rather than conditioning on
     one value.
  2. REGIME PERSISTENCE. Sessions are resampled in multi-day BLOCKS, not
     independently. 2026Q3 showed bad conditions last for months; i.i.d. session
     draws cannot produce a two-month hole and so understate ruin.
  3. MONTE CARLO ERROR. Every figure is reported with its own sampling error, so
     a 0.4-point difference is not read as a finding.

The challenge model is the session-replay one: sessions resampled whole, trades
applied in order within the day, MLL checked in real time including open P&L, DLL
as a lockout, consistency raising the target rather than failing you.

    .venv/bin/python research/montecarlo.py [paths]
"""

import csv
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orb_rescue as RS  # noqa: E402
import search_5m as S5   # noqa: E402
import topstep as TS     # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PATHS = 40_000
MAX_DAYS = 120


def session_matrix(rows):
    """Sessions as a padded (n_sessions x max_trades) array of R-multiples."""
    days = np.array([str(t["day"]) for t in rows])
    r = RS.apply_target(rows, 0.50)
    uq, inv = np.unique(days, return_inverse=True)
    groups = [r[inv == k] for k in range(len(uq))]
    w = max(len(g) for g in groups)
    M = np.full((len(groups), w), np.nan)
    for i, g in enumerate(groups):
        M[i, :len(g)] = g
    return M, r, days


def edge_posterior(r, days, reps=20_000, seed=11):
    """Day-clustered bootstrap distribution of the pool mean."""
    uq, inv = np.unique(days, return_inverse=True)
    bk = [np.where(inv == k)[0] for k in range(len(uq))]
    rng = np.random.default_rng(seed)
    out = np.empty(reps)
    for b in range(reps):
        out[b] = r[np.concatenate([bk[p] for p in rng.integers(0, len(bk), len(bk))])].mean()
    return out


def run(M, risk_frac, edges, block=1, paths=PATHS, max_days=MAX_DAYS, seed=1):
    """Session-replay challenge. `edges` is one true edge per path."""
    rng = np.random.default_rng(seed)
    nS, W = M.shape
    Mc = M - np.nanmean(M)                      # centre, then add each path's edge
    eq = np.zeros(paths); peak = np.zeros(paths); best = np.zeros(paths)
    alive = np.ones(paths, bool); passed = np.zeros(paths, bool)
    dtp = np.zeros(paths); used = np.zeros(paths)
    trough = np.zeros(paths)                    # worst equity-below-peak seen
    start_i = rng.integers(0, nS, paths); pos = np.zeros(paths, int)

    for day in range(max_days):
        # block resampling: a new block start only every `block` days
        if block > 1:
            fresh = pos == 0
            start_i = np.where(fresh, rng.integers(0, nS, paths), start_i)
            pick = (start_i + pos) % nS
            pos = (pos + 1) % block
        else:
            pick = rng.integers(0, nS, paths)

        day_start = eq.copy()
        day_pnl = np.zeros(paths)
        can = alive.copy()
        for t in range(W):
            raw = Mc[pick, t]
            ok = ~np.isnan(raw)
            step = np.where(ok, (np.nan_to_num(raw) + edges) * (TS.V0 + eq) * risk_frac, 0.0)
            go = can & ok
            eq = np.where(go, eq + step, eq)
            day_pnl = np.where(go, day_pnl + step, day_pnl)
            alive &= eq > np.minimum(peak - TS.MLL, 0.0)     # real time, open P&L included
            trough = np.minimum(trough, eq - peak)
            can = alive & (day_pnl > -TS.DLL)                # lockout, not failure

        used += alive
        peak = np.maximum(peak, np.where(alive, eq, peak))
        best = np.maximum(best, np.where(alive, eq - day_start, 0.0))
        req = np.maximum(TS.TARGET, best / TS.CONSISTENCY)
        new = alive & ~passed & (eq >= req)
        dtp = np.where(new, day + 1, dtp)
        passed |= new
        alive &= ~new

    return dict(passed=passed, dtp=dtp, used=used, eq=eq, trough=trough)


def report(tag, res, paths=PATHS):
    p = res["passed"].mean()
    se = np.sqrt(p * (1 - p) / paths)
    d = res["dtp"][res["passed"]]
    print(f"  {tag:<34} {p:>6.1%} +/- {se*100:>4.2f}   "
          f"days p50 {np.median(d) if len(d) else 0:>3.0f}  "
          f"p90 {np.percentile(d, 90) if len(d) else 0:>3.0f}   "
          f"worst DD p50 ${-np.median(res['trough']):>6,.0f}")
    return p, se


def main():
    paths = int(sys.argv[1]) if len(sys.argv) > 1 else PATHS
    d = S5.load_dir("data/nq_5m")
    dates = np.array([str(x) for x in d["day"]])
    n = len(dates); cut70 = int(n * 0.70)
    cutbrk = int(np.searchsorted(dates, RS.BREAK_START))
    OOS = RS.collect(S5.slice_data(d, cut70, cutbrk))
    M, r, days = session_matrix(OOS)
    post = edge_posterior(r, days)

    print(f"POOL: ORB long-only, 0.50R, out-of-sample half (2024-06 -> 2026-06)")
    print(f"  {len(r):,} trades on {M.shape[0]:,} sessions, up to {M.shape[1]} per session")
    print(f"  point-estimate edge {r.mean():+.4f}R")
    print(f"  day-clustered 95% interval [{np.percentile(post,2.5):+.4f}, "
          f"{np.percentile(post,97.5):+.4f}]  P(edge>0) {np.mean(post>0):.1%}")
    print(f"  paths {paths:,} | horizon {MAX_DAYS} days | risk 0.50% of equity\n")

    fixed = np.full(paths, r.mean())
    rng = np.random.default_rng(77)
    drawn = rng.choice(post, size=paths)

    print("PASS RATE — what each layer of honesty costs")
    print(f"  {'model':<34} {'pass':>6}   {'MC se':>4}   {'days to pass':>18}   {'drawdown':>14}")
    a = report("1. fixed edge, i.i.d. sessions", run(M, .005, fixed, 1, paths), paths)
    b = report("2. + edge uncertainty", run(M, .005, drawn, 1, paths), paths)
    c = report("3. + 5-day blocks", run(M, .005, drawn, 5, paths), paths)
    e = report("4. + 21-day blocks", run(M, .005, drawn, 21, paths), paths)

    print(f"\n  edge uncertainty alone: {(b[0]-a[0])*100:+.1f} pts "
          f"({np.sqrt(a[1]**2+b[1]**2)*100:.2f} se)")
    print(f"  regime persistence:     {(e[0]-b[0])*100:+.1f} pts "
          f"({np.sqrt(b[1]**2+e[1]**2)*100:.2f} se)")
    print(f"  combined:               {(e[0]-a[0])*100:+.1f} pts")

    print("\nOUTCOME DISTRIBUTION — model 4, the honest one")
    res = run(M, .005, drawn, 21, paths)
    dd = -res["trough"]
    print(f"  passed                     {res['passed'].mean():.1%}")
    print(f"  failed on drawdown         {(~res['passed'] & (res['used'] < MAX_DAYS)).mean():.1%}")
    print(f"  ran out of horizon         {(~res['passed'] & (res['used'] >= MAX_DAYS)).mean():.1%}")
    print(f"  days to pass   p10/p50/p90 "
          f"{np.percentile(res['dtp'][res['passed']],[10,50,90]).round(0)}")
    print(f"  worst drawdown p50/p90/p99 ${np.percentile(dd,50):,.0f} / "
          f"${np.percentile(dd,90):,.0f} / ${np.percentile(dd,99):,.0f}")

    print("\nCONDITIONAL ON THE TRUE EDGE — where the uncertainty actually lives")
    qs = np.percentile(post, [5, 25, 50, 75, 95])
    print(f"  {'true edge':>11} {'pass':>7}")
    for q in qs:
        res = run(M, .005, np.full(paths // 4, q), 21, paths // 4, seed=3)
        print(f"  {q:>+11.4f} {res['passed'].mean():>7.1%}")
    print(f"\n  The spread across that column is the real uncertainty. A single")
    print(f"  pass-rate number hides it.")


if __name__ == "__main__":
    main()


def run_paths(M, risk_frac, edge, block=21, paths=400, max_days=45, seed=4):
    """Same rules, but keep every path's daily equity so the sim can be drawn.

    Returns (eq_history, resolved_day, passed). eq_history is (paths, days+1);
    a resolved path is held flat after it passes or dies so the line stops moving.
    """
    rng = np.random.default_rng(seed)
    nS, W = M.shape
    Mc = M - np.nanmean(M)
    eq = np.zeros(paths); peak = np.zeros(paths); best = np.zeros(paths)
    alive = np.ones(paths, bool); passed = np.zeros(paths, bool)
    resolved = np.full(paths, max_days)
    hist = np.zeros((paths, max_days + 1))
    start_i = rng.integers(0, nS, paths); pos = np.zeros(paths, int)
    edges = np.full(paths, edge)

    for day in range(max_days):
        if block > 1:
            start_i = np.where(pos == 0, rng.integers(0, nS, paths), start_i)
            pick = (start_i + pos) % nS
            pos = (pos + 1) % block
        else:
            pick = rng.integers(0, nS, paths)
        day_start = eq.copy(); day_pnl = np.zeros(paths); can = alive.copy()
        for t in range(W):
            raw = Mc[pick, t]
            ok = ~np.isnan(raw)
            step = np.where(ok, (np.nan_to_num(raw) + edges) * (TS.V0 + eq) * risk_frac, 0.0)
            go = can & ok
            eq = np.where(go, eq + step, eq)
            day_pnl = np.where(go, day_pnl + step, day_pnl)
            died = alive & ~(eq > np.minimum(peak - TS.MLL, 0.0))
            resolved = np.where(died, day + 1, resolved)
            alive &= ~died
            can = alive & (day_pnl > -TS.DLL)
        peak = np.maximum(peak, np.where(alive, eq, peak))
        best = np.maximum(best, np.where(alive, eq - day_start, 0.0))
        req = np.maximum(TS.TARGET, best / TS.CONSISTENCY)
        new = alive & ~passed & (eq >= req)
        resolved = np.where(new, day + 1, resolved)
        passed |= new
        alive &= ~new
        hist[:, day + 1] = eq
    # hold resolved paths flat from the day they resolved
    for i in range(paths):
        r = int(resolved[i])
        if r < max_days:
            hist[i, r + 1:] = hist[i, r]
    return hist, resolved, passed
