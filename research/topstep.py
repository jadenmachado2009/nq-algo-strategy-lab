"""Topstep 50K, modelled on its actual published rules (checked 2026-10-09).

Rules implemented (sources in backtests/2026-10-09_topstep_50k.md):

COMBINE ($49/month, $149 activation on passing)
  - start $50,000, profit target +$3,000
  - Maximum Loss Limit $2,000, which:
      * trails from END-OF-DAY balance only (intraday highs do NOT raise it)
      * never moves down
      * LOCKS once it reaches the starting balance
    -> mll_profit_level = min(max(end_of_day_profit) - 2000, 0)
  - breach is checked in real time including open P&L -> we check per trade
  - optional Daily Loss Limit $1,000. Hitting it is NOT a violation: it stops you
    trading for the rest of that day. Modelled as a lockout, not a failure.
  - consistency: best day must be <= 50% of the profit target ($1,500).
    Exceeding it does NOT fail you — it raises the target to best_day / 0.5

EXPRESS FUNDED ACCOUNT
  - trailing drawdown starts $2,000 below and locks at $0 (breakeven)
  - 90/10 profit split
  - payout requires 5 winning days of >= $150 (the Standard path)

Everything else (scaling plan tiers, payout caps, reset pricing) is not modelled
and can only reduce the result.

    .venv/bin/python ../research/topstep.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search as S  # noqa: E402
from video_model import coinflip_pool  # noqa: E402

PATHS = 40_000
V0 = 50_000.0
TARGET = 3_000.0
MLL = 2_000.0
DLL = 1_000.0
CONSISTENCY = 0.50          # best day <= 50% of target
MONTHLY = 49.0
ACTIVATION = 149.0
SPLIT = 0.90
WIN_DAY = 150.0             # a "winning day" for payout eligibility
WIN_DAYS_NEEDED = 5
TRADING_DAYS_PER_MONTH = 21


def combine(pool, risk_frac, trades_per_day=1, max_days=120, use_dll=True, seed=1):
    """Returns (pass_rate, mean_days_to_pass, mean_days_used)."""
    rng = np.random.default_rng(seed)
    eq = np.zeros(PATHS)                 # profit relative to start
    eod_peak = np.zeros(PATHS)           # highest END-OF-DAY profit
    best_day = np.zeros(PATHS)
    alive = np.ones(PATHS, bool)
    passed = np.zeros(PATHS, bool)
    days_to_pass = np.zeros(PATHS)
    days_used = np.zeros(PATHS)

    for day in range(max_days):
        day_start = eq.copy()
        day_pnl = np.zeros(PATHS)
        can_trade = alive.copy()
        for _ in range(trades_per_day):
            step = rng.choice(pool, size=PATHS) * (V0 + eq) * risk_frac
            eq = np.where(can_trade, eq + step, eq)
            day_pnl = np.where(can_trade, day_pnl + step, day_pnl)
            # MLL is checked in real time, including open P&L
            alive &= eq > np.minimum(eod_peak - MLL, 0.0)
            # DLL is a lockout for the rest of the day, not a failure
            can_trade = alive & (day_pnl > -DLL if use_dll else alive)

        days_used += alive
        eod_peak = np.maximum(eod_peak, np.where(alive, eq, eod_peak))   # end-of-day only
        best_day = np.maximum(best_day, np.where(alive, eq - day_start, 0.0))

        # consistency: exceeding the cap raises the target rather than failing you
        required = np.maximum(TARGET, best_day / CONSISTENCY)
        newly = alive & ~passed & (eq >= required)
        days_to_pass = np.where(newly, day + 1, days_to_pass)
        passed |= newly
        alive &= ~newly

    return (float(passed.mean()),
            float(days_to_pass[passed].mean()) if passed.any() else 0.0,
            float(np.where(passed, days_to_pass, days_used).mean()))


def funded(pool, risk_frac, trades_per_day=1, max_days=250, seed=4):
    """Trader's withdrawn profit. DD starts $2,000 below, locks at breakeven."""
    rng = np.random.default_rng(seed)
    eq = np.zeros(PATHS)
    eod_peak = np.zeros(PATHS)
    alive = np.ones(PATHS, bool)
    paid = np.zeros(PATHS)
    win_days = np.zeros(PATHS)

    for _ in range(max_days):
        day_start = eq.copy()
        for _t in range(trades_per_day):
            step = rng.choice(pool, size=PATHS) * (V0 + eq) * risk_frac
            eq = np.where(alive, eq + step, eq)
            alive &= eq > np.minimum(eod_peak - MLL, 0.0)

        day_pnl = eq - day_start
        win_days += alive & (day_pnl >= WIN_DAY)
        eod_peak = np.maximum(eod_peak, np.where(alive, eq, eod_peak))

        # withdraw once eligible and in profit; the drawdown line does not reset
        can_pay = alive & (win_days >= WIN_DAYS_NEEDED) & (eq > 0)
        paid += np.where(can_pay, eq * SPLIT, 0.0)
        eq = np.where(can_pay, 0.0, eq)
    return paid


def main():
    d = S.load_hourly()
    a, *_ = S.build_blocks(d)
    pool = coinflip_pool(d, a, 3.0, 1.5)    # coin flip, 3xATR stop, 0.5:1 target
    print(f"Topstep 50K | coin-flip entries, 3xATR stop (~{3*np.nanmedian(a):.0f} pts), 0.5:1 target")
    print(f"  input trades: n={len(pool):,}  win rate {np.mean(pool>0):.1%}  expectancy {pool.mean():+.3f}R")
    print(f"  fees: ${MONTHLY:.0f}/month + ${ACTIVATION:.0f} activation | MLL ${MLL:,.0f} locking at start")
    print(f"  consistency: best day <= {CONSISTENCY:.0%} of target | payout needs {WIN_DAYS_NEEDED} days >= ${WIN_DAY:.0f}\n")

    print(f"  {'risk':>6} {'$/trade':>8} {'pass':>7} {'days to pass':>13} {'months paid':>12} {'E[payout]':>10} {'EV/attempt':>11}")
    best = None
    for f in (0.005, 0.01, 0.015, 0.02, 0.03, 0.04):
        p, dtp, dused = combine(pool, f)
        pay = funded(pool, f).mean()
        months = max(1.0, np.ceil(dused / TRADING_DAYS_PER_MONTH))
        ev = p * (pay - ACTIVATION) - months * MONTHLY
        print(f"  {f:>5.1%} {V0*f:>8,.0f} {p:>6.1%} {dtp:>13.0f} {months:>12.0f} {pay:>10,.0f} {ev:>+11,.0f}")
        if best is None or ev > best[1]:
            best = (f, ev, p, pay, months)
    f, ev, p, pay, months = best
    print(f"\n  best: {f:.1%} risk -> EV {ev:+,.0f}/attempt (pass {p:.1%}, payout ${pay:,.0f}, {months:.0f} month(s) of fees)")
    print(f"  10 attempts: spend ~${10*months*MONTHLY:,.0f} in subscriptions, expect {10*ev:+,.0f}")


if __name__ == "__main__":
    main()
