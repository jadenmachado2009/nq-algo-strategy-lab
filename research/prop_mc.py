"""Prop-firm challenge as a structured product: Monte Carlo over risk geometry.

Premise (DeltaTrend Trading, "stop trading like an idiot"): a prop account has a
CONVEX payoff. Downside is capped at the challenge + activation fees; upside is
uncapped payouts. So the question is not "is my strategy +EV?" but:

    given this trade distribution, which risk-per-trade maximises
    NET expected value after fees — and what is the probability of passing?

There is no analytic answer (path-dependent: daily loss limits, trailing
drawdown, min trading days), so we simulate.

What this does NOT do: pretend a negative-EV strategy is a good business. It
prices the lottery ticket honestly, fees included, and reports the EV per
attempt. If that number is negative at every risk setting, the answer is no.

    .venv/bin/python ../research/prop_mc.py                      # built-in toy + CBE
    .venv/bin/python ../research/prop_mc.py trades.csv           # your own R column
"""

import sys
from dataclasses import dataclass

import numpy as np


# ── firm profiles ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Firm:
    name: str
    account: float
    profit_target: float      # $ to pass the evaluation
    max_drawdown: float       # $ total loss allowed
    trailing: bool            # drawdown trails the high-water mark
    daily_loss: float         # $ loss in one day that fails you (0 = none)
    min_days: int             # minimum trading days before passing counts
    fee: float                # evaluation fee (sunk on failure)
    activation: float         # paid once on passing, before funded trading
    split: float              # trader's share of funded profits
    payout_threshold: float   # $ profit in the funded account before a payout
    funded_max_dd: float      # $ drawdown allowed in the funded account


FIRMS = {
    # Futures-style single-phase evaluation, trailing drawdown (Topstep/Apex-like).
    "futures_50k": Firm("Futures 50k eval", 50_000, 3_000, 2_000, True, 0, 5, 165, 149, 0.90, 1_000, 2_000),
    # Two-step FX/CFD style, static drawdown (FTMO-like), modelled as one combined target.
    "cfd_50k": Firm("CFD 50k 2-step", 50_000, 4_000, 5_000, False, 2_500, 4, 345, 0, 0.80, 1_000, 5_000),
}


# ── trade distributions ──────────────────────────────────────────────────────
def r_from_csv(path):
    import csv
    with open(path) as f:
        rows = list(csv.DictReader(f))
    key = next(k for k in rows[0] if k.strip().lower() in ("r", "r_multiple", "rmultiple"))
    return np.array([float(r[key]) for r in rows if r[key] not in ("", None)])


def r_synthetic(win_rate, win_r, loss_r, n=5000, seed=0):
    rng = np.random.default_rng(seed)
    return np.where(rng.random(n) < win_rate, win_r, -loss_r)


# ── simulation ───────────────────────────────────────────────────────────────
def simulate(r_pool, firm, risk_frac, paths=20_000, trades_per_day=2, max_days=60, seed=1):
    """Returns (pass_rate, funded_outcomes) for one risk setting.

    risk_frac: fraction of the STARTING account risked per trade (fixed-fractional
    on starting balance — how prop traders actually size, and it keeps the daily
    loss limit meaningful).
    """
    rng = np.random.default_rng(seed)
    risk = firm.account * risk_frac
    n_trades = trades_per_day * max_days
    draws = rng.choice(r_pool, size=(paths, n_trades), replace=True) * risk

    equity = np.zeros(paths)
    peak = np.zeros(paths)
    day_pnl = np.zeros(paths)
    alive = np.ones(paths, bool)
    passed = np.zeros(paths, bool)
    days_traded = np.zeros(paths, int)

    for i in range(n_trades):
        equity = np.where(alive, equity + draws[:, i], equity)
        day_pnl = np.where(alive, day_pnl + draws[:, i], day_pnl)
        peak = np.maximum(peak, equity)

        dd = (peak - equity) if firm.trailing else -equity
        alive &= dd < firm.max_drawdown
        if firm.daily_loss:
            alive &= day_pnl > -firm.daily_loss

        if (i + 1) % trades_per_day == 0:          # end of day
            days_traded += alive
            day_pnl = np.zeros(paths)
            newly = alive & ~passed & (equity >= firm.profit_target) & (days_traded >= firm.min_days)
            passed |= newly
            alive &= ~newly                        # stop trading once passed

    return passed.mean()


def funded_ev(r_pool, firm, risk_frac, paths=20_000, trades_per_day=2, max_days=120, seed=2):
    """Expected trader profit from a funded account: payouts until breach."""
    rng = np.random.default_rng(seed)
    risk = firm.account * risk_frac
    n_trades = trades_per_day * max_days
    draws = rng.choice(r_pool, size=(paths, n_trades), replace=True) * risk

    equity = np.zeros(paths)
    peak = np.zeros(paths)
    alive = np.ones(paths, bool)
    paid = np.zeros(paths)

    for i in range(n_trades):
        equity = np.where(alive, equity + draws[:, i], equity)
        peak = np.maximum(peak, equity)
        alive &= (peak - equity) < firm.funded_max_dd
        hit = alive & (equity >= firm.payout_threshold)
        if hit.any():
            paid += np.where(hit, equity * firm.split, 0.0)
            # Withdraw profit: equity returns to baseline, but the trailing
            # drawdown line does NOT reset -- the high-water mark stays where it
            # was, so each payout permanently shrinks the remaining buffer.
            # (Resetting peak here would hand the trader unlimited lives and
            # roughly doubles E[payout]; real futures accounts do not do that.)
            equity = np.where(hit, 0.0, equity)
    return paid.mean()


def evaluate(name, r_pool, firm, risk_grid, **kw):
    print(f"\n{name}  |  {firm.name}")
    print(f"  trade sample: n={len(r_pool)}  mean={r_pool.mean():+.3f}R  "
          f"win rate={np.mean(r_pool > 0):.1%}  fees=${firm.fee + firm.activation:,.0f}")
    print(f"  {'risk/trade':>10} {'pass %':>8} {'E[payout]':>11} {'net EV':>10}")
    best = None
    for f in risk_grid:
        p = simulate(r_pool, firm, f, **kw)
        payout = funded_ev(r_pool, firm, f) if p > 0 else 0.0
        # Expected cost: fee always; activation only if you pass.
        ev = p * (payout - firm.activation) - firm.fee
        print(f"  {f:10.2%} {p:8.1%} {payout:11,.0f} {ev:+10,.0f}")
        if best is None or ev > best[1]:
            best = (f, ev, p)
    print(f"  -> best: risk {best[0]:.2%}/trade, net EV {best[1]:+,.0f} per attempt, pass rate {best[2]:.1%}")
    return best


def main():
    risk_grid = [0.002, 0.005, 0.01, 0.02, 0.03, 0.05]
    firm = FIRMS["futures_50k"]

    # 1. Coin-flip strategy with a 2:1 payoff and NEGATIVE edge (the video's claim:
    #    convexity can still make the account +EV at the right risk).
    zero_ev = r_synthetic(win_rate=0.30, win_r=2.0, loss_r=1.0, seed=3)   # mean -0.10R
    evaluate("Negative-EV toy (30% WR, 2:1)", zero_ev, firm, risk_grid)

    # 2. A genuinely break-even strategy.
    flat = r_synthetic(win_rate=0.3334, win_r=2.0, loss_r=1.0, seed=4)
    evaluate("Break-even toy (33.3% WR, 2:1)", flat, firm, risk_grid)

    # 3. Our own measured CBE distribution, if the forward replay CSV is present.
    for path in sys.argv[1:]:
        evaluate(f"From {path}", r_from_csv(path), firm, risk_grid)


if __name__ == "__main__":
    main()
