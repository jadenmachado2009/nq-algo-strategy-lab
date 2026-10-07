"""What the EV per attempt actually means for someone paying the fees.

A positive EV per attempt is not the same as "you will make money". The payoff is
a lottery: most attempts lose the fee, a minority pay out a few thousand. This
prices the repeated game — how much capital, how many attempts, and what the
chance of being in profit is at each stage.

    .venv/bin/python ../research/bankroll.py [firm_key]
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_search import FIRMS, Policy, simulate  # noqa: E402
from prop_mc import r_synthetic  # noqa: E402

EDGE = -0.02          # zero-edge baseline measured from random entries on real NQ
PATHS = 20_000
FUNDED_TRADES = 240   # ~1 year at 1 trade/day


def payout_distribution(pool, firm, risk_frac, seed=3):
    """Per-path trader profit from a funded account — the full distribution, not the mean."""
    rng = np.random.default_rng(seed)
    draws = rng.choice(pool, size=(PATHS, FUNDED_TRADES), replace=True) * firm.account * risk_frac
    eq = np.zeros(PATHS)
    peak = np.zeros(PATHS)
    alive = np.ones(PATHS, bool)
    paid = np.zeros(PATHS)
    for i in range(FUNDED_TRADES):
        eq = np.where(alive, eq + draws[:, i], eq)
        peak = np.maximum(peak, eq)
        alive &= (peak - eq) < firm.funded_max_dd
        hit = alive & (eq >= firm.payout_threshold)
        paid += np.where(hit, eq * firm.split, 0.0)
        eq = np.where(hit, 0.0, eq)   # withdraw; the drawdown line does not reset
    return paid


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else "apex_50k"
    firm = FIRMS[key]
    pol = Policy(0.01, 2.0, 1.0, 1.0, 1)      # EV-best policy from geometry_search
    pool = r_synthetic((EDGE + 1.0) / (pol.rr + 1.0), pol.rr, 1.0, n=20_000, seed=5)

    p_pass, _ = simulate(pool, firm, pol, paths=PATHS)
    paid = payout_distribution(pool, firm, pol.f_base * pol.mult_locked)
    fee = firm.fee + firm.activation

    print(f"{firm.name} | policy: {pol.label()} | zero-edge ({EDGE:+.2f}R)")
    print(f"  pass rate {p_pass:.1%} | fee per attempt ${fee:,.0f}")
    print(f"  payout if funded: mean ${paid.mean():,.0f} | median ${np.median(paid):,.0f} | "
          f"p10 ${np.percentile(paid, 10):,.0f} | p90 ${np.percentile(paid, 90):,.0f} | "
          f"{np.mean(paid < 1):.0%} of funded accounts never pay out\n")

    rng = np.random.default_rng(9)
    sims = 200_000
    print(f"  {'attempts':>9} {'capital':>9} {'P(profit>0)':>12} {'median':>10} {'mean':>10}")
    for k in (1, 5, 10, 20, 50):
        passes = rng.random((sims, k)) < p_pass
        pay = np.where(passes, rng.choice(paid, size=(sims, k)), 0.0)
        r = pay.sum(1) - fee * k
        print(f"  {k:9d} {fee * k:9,.0f} {np.mean(r > 0):12.1%} {np.median(r):+10,.0f} {r.mean():+10,.0f}")

    print("\n  Read this as: the EV is an average over MANY attempts. A single attempt is a losing")
    print("  bet most of the time. Treat the fee as spent money, not as an investment.")
    print("\n  Not modelled, all of which reduce EV: monthly (not one-off) subscription fees,")
    print("  scaling plans, payout waiting periods, news-trading restrictions, platform fees,")
    print("  and execution worse than the simulated fills.")


if __name__ == "__main__":
    main()
