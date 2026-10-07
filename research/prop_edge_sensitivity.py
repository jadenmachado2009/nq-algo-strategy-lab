"""How much true edge does the prop-firm convexity play actually need?

prop_mc.py prices one trade distribution. This sweeps the TRUE edge from clearly
negative to slightly positive, finds the best risk setting at each, and reports
net EV per attempt. It answers two questions the video's framing raises:

  1. Where does net EV cross zero? (i.e. how bad can the strategy be?)
  2. How many trades would we need to know which side of that line we're on?

(2) matters most: if EV flips from +$168 to -$111 between -0.00R and -0.16R,
and our best measured sample is ~150-300 trades with a standard deviation of
~1.4R, the confidence interval on our edge is wider than the whole decision.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prop_mc import FIRMS, funded_ev, r_synthetic, simulate  # noqa: E402

RISK_GRID = [0.003, 0.005, 0.0075, 0.01, 0.015, 0.02]


def best_ev(r_pool, firm):
    best = (None, -1e9, 0.0)
    for f in RISK_GRID:
        p = simulate(r_pool, firm, f, paths=20_000)
        payout = funded_ev(r_pool, firm, f, paths=20_000) if p > 0 else 0.0
        ev = p * (payout - firm.activation) - firm.fee
        if ev > best[1]:
            best = (f, ev, p)
    return best


def edge_pool(mean_r, win_r=2.0, loss_r=1.0, n=20_000, seed=0):
    """Win rate chosen so the pool's mean equals mean_r with a 2:1 payoff."""
    wr = (mean_r + loss_r) / (win_r + loss_r)
    return r_synthetic(wr, win_r, loss_r, n=n, seed=seed), wr


def main():
    firm = FIRMS["futures_50k"]
    print(f"{firm.name}: target ${firm.profit_target:,.0f}, trailing DD ${firm.max_drawdown:,.0f}, "
          f"fees ${firm.fee + firm.activation:,.0f}, split {firm.split:.0%}\n")
    print(f"  {'true edge':>10} {'win rate':>9} {'best risk':>10} {'pass %':>8} {'net EV':>10}")

    rows = []
    for mean_r in [-0.20, -0.15, -0.10, -0.05, -0.02, 0.00, 0.02, 0.05, 0.10]:
        pool, wr = edge_pool(mean_r)
        f, ev, p = best_ev(pool, firm)
        rows.append((mean_r, ev))
        print(f"  {mean_r:+10.2f}R {wr:9.1%} {f:10.2%} {p:8.1%} {ev:+10,.0f}")

    # linear interpolation for the break-even edge
    cross = None
    for (e0, v0), (e1, v1) in zip(rows, rows[1:]):
        if v0 < 0 <= v1:
            cross = e0 + (e1 - e0) * (0 - v0) / (v1 - v0)
            break
    if cross is not None:
        print(f"\n  Net EV crosses zero at a true edge of about {cross:+.3f}R per trade.")

    # How many trades to tell that edge apart from zero?
    sd = 1.4   # R standard deviation measured on our own 2:1 bracket trades
    for target in (0.05, 0.10):
        n = (1.96 * sd / target) ** 2
        print(f"  To measure an edge of {target:.2f}R to 95% confidence (sd {sd}R): ~{n:,.0f} trades.")


if __name__ == "__main__":
    main()
