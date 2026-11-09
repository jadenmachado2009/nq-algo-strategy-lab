"""Topstep 50K Combine pass probability for the half_r.py spec:
coin-flip entry, 15pt stop, 7.5pt target, NQ 1m, NY 09:30-11:00.

Inputs are real per-day trade sequences, not independent draws: for each
session and each random seed we replay the sequential coin-flip trades of that
day (same fills/costs as half_r.py). The Combine sim then samples whole days
with replacement, so intraday clustering and the number of trades per day are
kept.

Rules (same as research/topstep.py, checked 2026-10-09):
  - +$3,000 target; $2,000 MLL trailing end-of-day balance, locking at start
  - MLL checked after every trade (realised P&L; intratrade dips on trades
    that later win are not modelled, which flatters the result slightly)
  - $1,000 DLL = lockout for the rest of the day, not a failure
  - consistency: best day <= 50% of target, else target rises to best/0.5
  - $49/month subscription

    python3 research/topstep_half_r.py <dir with 1m csvs>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import half_r as H  # noqa: E402

STOP = 15.0
SEEDS = 500
PATHS = 20_000
MAX_DAYS = 60
TARGET, MLL, DLL, CONSISTENCY, MONTHLY = 3_000.0, 2_000.0, 1_000.0, 0.50, 49.0
TRADING_DAYS_PER_MONTH = 21


def day_sequences(df, comm_pts):
    """Padded (n_seq, L) matrix of per-contract pnl in points, NaN after the day ends."""
    xl, _, pl = H.outcomes(df, STOP, +1, comm_pts)
    xs, _, ps = H.outcomes(df, STOP, -1, comm_pts)
    day = pd.factorize(df["day"])[0]
    starts = np.flatnonzero(np.r_[True, day[1:] != day[:-1]])
    ends = np.r_[starts[1:], len(df)]
    rng = np.random.default_rng(11)
    seqs = []
    for a, b in zip(starts, ends):
        for _ in range(SEEDS):
            i, out = a, []
            while i < b:
                if rng.random() < 0.5:
                    out.append(pl[i]); i = xl[i] + 1
                else:
                    out.append(ps[i]); i = xs[i] + 1
            seqs.append(out)
    L = max(map(len, seqs))
    m = np.full((len(seqs), L), np.nan)
    for k, s in enumerate(seqs):
        m[k, :len(s)] = s
    return m


def combine(seq_usd, cap, seed=3):
    """seq_usd: per-day sequences in $ at the chosen size. cap: max trades/day."""
    rng = np.random.default_rng(seed)
    eq = np.zeros(PATHS); eod_peak = np.zeros(PATHS); best_day = np.zeros(PATHS)
    alive = np.ones(PATHS, bool); passed = np.zeros(PATHS, bool)
    days_to_pass = np.zeros(PATHS); days_used = np.zeros(PATHS)
    L = min(cap, seq_usd.shape[1])
    for d in range(MAX_DAYS):
        rows = seq_usd[rng.integers(0, len(seq_usd), PATHS), :L]
        day_pnl = np.zeros(PATHS)
        trading = alive.copy()
        for k in range(L):
            step = rows[:, k]
            on = trading & ~np.isnan(step)
            eq = np.where(on, eq + step, eq)
            day_pnl = np.where(on, day_pnl + step, day_pnl)
            alive &= eq > np.minimum(eod_peak - MLL, 0.0)
            # stop for the day on the DLL, or once the target is reached
            required = np.maximum(TARGET, np.maximum(best_day, day_pnl) / CONSISTENCY)
            trading = alive & (day_pnl > -DLL) & (eq < required)
        days_used += alive
        eod_peak = np.maximum(eod_peak, np.where(alive, eq, eod_peak))
        best_day = np.maximum(best_day, np.where(alive, day_pnl, 0.0))
        required = np.maximum(TARGET, best_day / CONSISTENCY)
        newly = alive & ~passed & (eq >= required)
        days_to_pass[newly] = d + 1
        passed |= newly
        alive &= ~newly
    failed = ~passed & (days_used < MAX_DAYS)
    months = np.ceil(np.maximum(np.where(passed, days_to_pass, days_used), 1) / TRADING_DAYS_PER_MONTH)
    return dict(pass_=passed.mean(), fail=failed.mean(), timeout=1 - passed.mean() - failed.mean(),
                days=days_to_pass[passed].mean() if passed.any() else np.nan,
                fees=(months * MONTHLY).mean())


def main():
    df = H.load(sys.argv[1])
    print(f"Data: {df['day'].nunique()} sessions, {df.index[0].date()} -> {df.index[-1].date()}")
    seqs = {inst: day_sequences(df, comm / pv) for inst, (pv, comm) in H.CONTRACTS.items()}
    for inst, m in seqs.items():
        pv = H.CONTRACTS[inst][0]
        flat = m[~np.isnan(m)]
        print(f"  {inst}: {np.mean(~np.isnan(m).all(1)):.0%} days traded, "
              f"{np.isnan(m).__invert__().sum(1).mean():.0f} trades/day, "
              f"WR {np.mean(flat > 0):.1%}, {flat.mean() / STOP:+.3f}R, ${flat.mean() * pv:+.2f}/contract/trade")

    sizes = [("MNQ", 5), ("MNQ", 10), ("NQ", 1), ("NQ", 2), ("NQ", 3)]
    caps = [1, 3, 5, 10, 999]
    print(f"\nTopstep 50K Combine, {PATHS:,} paths, {MAX_DAYS}-day horizon\n")
    print(f"{'size':>7} {'risk/trade':>10} {'trades/day':>10} {'PASS':>7} {'fail':>7} {'timeout':>8} {'days':>6} {'fees':>6}")
    rows = []
    for inst, n in sizes:
        pv = H.CONTRACTS[inst][0]
        usd = seqs[inst] * pv * n
        for cap in caps:
            r = combine(usd, cap)
            label = "all" if cap == 999 else str(cap)
            print(f"{n:>3} {inst:<3} {STOP * pv * n:>9,.0f}$ {label:>10} {r['pass_']:>6.1%} {r['fail']:>6.1%} "
                  f"{r['timeout']:>7.1%} {r['days']:>6.1f} {r['fees']:>5.0f}$")
            rows.append(dict(size=f"{n} {inst}", risk=STOP * pv * n, trades_per_day=label, **r))
    pd.DataFrame(rows).to_csv(Path(__file__).with_name("topstep_half_r_results.csv"), index=False)

    # reference: same paths with zero expectancy (costs removed by recentring)
    print("\nReference — same sizes with costs removed (pnl recentred to 0 mean), 3 trades/day:")
    for inst, n in sizes:
        pv = H.CONTRACTS[inst][0]
        m = seqs[inst] * pv * n
        m0 = m - np.nanmean(m)
        print(f"  {n} {inst}: pass {combine(m0, 3)['pass_']:.1%}")


if __name__ == "__main__":
    main()
