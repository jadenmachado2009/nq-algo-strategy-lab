"""Five independent Topstep 50K attempts, end to end: Combine -> XFA -> payouts.

Strategy: coin flip, 1 NQ, 50pt stop / 25pt target, first trade of the day
only (09:30-11:00 NY, flat at 11:00). Daily P&L comes from real NQ 1m days
(topstep_half_r.day_sequences), re-centred to the theoretical cost drag
(-0.012R) because 20 sessions are too few to pin the mean.

Rules (third-party sources, 2026; verify on the dashboard):
  Combine: +$3,000, $2,000 EOD-trailing MLL locking at start, $1,000 DLL,
           50% consistency, $49/month, $149 activation on passing.
  XFA:     $2,000 EOD-trailing MLL locking at start; Standard payout path:
           5 winning days >= $150 since the last payout, request
           min(50% of profit balance, $2,000), >= $125, 90/10 split.
           Withdrawals lower the balance; the MLL does not move back down.
Each account gets HORIZON trading days in total. Accounts are independent
(separate coin flips) — copying one signal to all five would not be.

    python3 research/topstep_multi.py <dir with 1m csvs>
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import half_r as H  # noqa: E402
import topstep_half_r as T  # noqa: E402

N_ACC = 5
PATHS = 100_000          # simulated traders, each running N_ACC accounts
HORIZON = 126            # trading days (~6 months)
TARGET, MLL, DLL, CONS = 3_000.0, 2_000.0, 1_000.0, 0.50
MONTHLY, ACTIVATION, SPLIT = 49.0, 149.0, 0.90
WIN_DAY, WIN_DAYS, CAP, MIN_REQ = 150.0, 5, 2_000.0, 125.0


def daily_pool(df):
    T.STOP = 50.0
    pv, comm = H.CONTRACTS["NQ"]
    m = T.day_sequences(df, comm / pv)
    first = m[:, 0]
    cost = 0.25 + 0.25 / 3 + 2 * comm / pv
    return (first - first.mean() - cost) * pv       # $ per day, 1 NQ


def run(pool, n, seed=1):
    """n accounts in parallel. Returns net $ per account and event days."""
    rng = np.random.default_rng(seed)
    eq = np.zeros(n); peak = np.zeros(n); best = np.zeros(n)
    phase = np.zeros(n, int)            # 0 combine, 1 funded, 2 dead
    fees = np.full(n, MONTHLY)          # first month paid up front
    paid = np.zeros(n); wins = np.zeros(n)
    pass_day = np.full(n, np.nan); first_pay = np.full(n, np.nan); n_pay = np.zeros(n)
    combine_days = np.zeros(n)
    for d in range(HORIZON):
        pnl = rng.choice(pool, n)
        # DLL only matters intraday; with one trade a day it never changes the outcome
        live = phase < 2
        eq = np.where(live, eq + pnl, eq)
        dead = live & (eq <= np.minimum(peak - MLL, 0.0))
        phase[dead] = 2
        live = phase < 2
        peak = np.maximum(peak, np.where(live, eq, peak))

        c = phase == 0
        combine_days += c
        best = np.where(c, np.maximum(best, pnl), best)
        newly = c & (eq >= np.maximum(TARGET, best / CONS))
        # month boundary while still in the Combine -> another subscription
        fees += np.where(c & ~newly & (combine_days % 21 == 0), MONTHLY, 0.0)
        pass_day[newly] = d + 1
        fees[newly] += ACTIVATION
        phase[newly] = 1
        eq[newly] = 0.0; peak[newly] = 0.0   # XFA starts fresh

        f = (phase == 1) & ~newly
        wins += f & (pnl >= WIN_DAY)
        req = np.minimum(0.5 * eq, CAP)
        can = f & (wins >= WIN_DAYS) & (req >= MIN_REQ)
        paid += np.where(can, req * SPLIT, 0.0)
        eq = np.where(can, eq - req, eq)
        wins[can] = 0
        n_pay += can
        first_pay[can & np.isnan(first_pay)] = d + 1
    return paid - fees, paid, fees, pass_day, first_pay, n_pay


def main():
    df = H.load(sys.argv[1])
    pool = daily_pool(df)
    print(f"Daily pool: {len(pool):,} days, WR {np.mean(pool > 0):.1%}, mean ${pool.mean():+.1f}/day, "
          f"win ${pool[pool > 0].mean():.0f} / loss ${pool[pool < 0].mean():.0f}\n")

    net, paid, fees, pday, fpay, npay = run(pool, PATHS * N_ACC)
    shp = (PATHS, N_ACC)
    tot = net.reshape(shp).sum(1)
    tpaid = paid.reshape(shp).sum(1)
    tfees = fees.reshape(shp).sum(1)

    print(f"Per account ({HORIZON} trading days):")
    print(f"  pass {np.mean(~np.isnan(pday)):.1%}, median {np.nanmedian(pday):.0f} days to pass")
    print(f"  >=1 payout {np.mean(~np.isnan(fpay)):.1%}, median {np.nanmedian(fpay):.0f} days to first payout")
    print(f"  mean payouts ${paid.mean():,.0f}, mean fees ${fees.mean():,.0f}, mean net ${net.mean():+,.0f}\n")

    print(f"{N_ACC} accounts together:")
    print(f"  mean fees ${tfees.mean():,.0f}  mean payouts ${tpaid.mean():,.0f}  mean NET ${tot.mean():+,.0f}")
    print(f"  P(net > 0) {np.mean(tot > 0):.1%}")
    for q in (5, 25, 50, 75, 95):
        print(f"  p{q:<2} net ${np.percentile(tot, q):+,.0f}")
    print("  outcome buckets:")
    for lo, hi, lab in [(-1e9, -500, "lose > $500"), (-500, 0, "lose $0-500"), (0, 2000, "make $0-2k"),
                        (2000, 5000, "make $2-5k"), (5000, 1e9, "make > $5k")]:
        print(f"    {lab:12s} {np.mean((tot > lo) & (tot <= hi)):.1%}")
    anyp = (~np.isnan(fpay)).reshape(shp)
    fp = np.where(np.isnan(fpay), np.inf, fpay).reshape(shp).min(1)
    print(f"  P(at least one payout) {anyp.any(1).mean():.1%}, median first payout on day "
          f"{np.median(fp[np.isfinite(fp)]):.0f}")


if __name__ == "__main__":
    main()
