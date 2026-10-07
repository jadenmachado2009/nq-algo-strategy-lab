"""Search over RISK POLICIES, not entry signals.

Everything we measured says the entry edge is not the lever: three searches found
nothing above noise, while moving risk from 2% to 0.75% changed the pass rate from
5% to 29%. So this searches the thing that actually moves the number.

The structural feature being exploited: a real futures trailing drawdown stops
trailing once you are far enough ahead. Topstep's trail freezes at the starting
balance; Apex's freezes just above it. So the drawdown line is

    dd_line = min(peak - D, CAP)

Before the floor binds, every dollar of profit drags the liquidation level up
behind you and a pullback kills you. After it binds, profit is pure buffer and
variance becomes cheap. That asymmetry is a free option, and no fixed-risk plan
uses it: the right play is to trade small until the floor binds, then escalate.

Policy space (all applied to a ZERO-EDGE trade distribution, so nothing here
depends on finding an edge):
    f_base      risk per trade before the floor binds
    mult_locked risk multiplier once the floor binds
    mult_near   risk multiplier once equity is within reach of the target
    rr          reward:risk of the bracket
    tpd         trades per day

Scoring is net EV per attempt, with pass rate reported alongside. A consistency
check (largest single day as a share of total profit) is computed on passing
paths, because that is the rule most likely to invalidate an aggressive policy.

    .venv/bin/python ../research/geometry_search.py
"""

import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prop_mc import funded_ev, r_synthetic  # noqa: E402


@dataclass(frozen=True)
class Firm:
    name: str
    account: float
    target: float
    dd: float
    cap: float            # profit level at which the trailing line stops rising
    daily_loss: float
    min_days: int
    fee: float
    activation: float
    split: float
    payout_threshold: float
    funded_max_dd: float
    consistency: float    # max share of total profit allowed from one day (0 = no rule)


FIRMS = {
    # Trail freezes at the starting balance once you are +$2,000.
    "topstep_50k": Firm("Topstep-like 50k", 50_000, 3_000, 2_000, 0.0, 1_000, 5, 165, 149, 0.90, 1_000, 2_000, 0.50),
    # Trail freezes just above breakeven once you are +$2,600.
    "apex_50k": Firm("Apex-like 50k", 50_000, 3_000, 2_500, 100.0, 0.0, 7, 167, 0, 0.90, 1_000, 2_500, 0.30),
}


@dataclass(frozen=True)
class Policy:
    f_base: float
    mult_locked: float
    mult_near: float
    rr: float
    tpd: int

    def label(self):
        return (f"risk {self.f_base:.2%} | x{self.mult_locked:g} locked | x{self.mult_near:g} near "
                f"| RR {self.rr:g} | {self.tpd}/day")


def simulate(pool, firm, pol, paths=20_000, max_days=60, seed=1):
    """Vectorised challenge simulation. Returns (pass_rate, consistency_ok_rate)."""
    rng = np.random.default_rng(seed)
    n_trades = pol.tpd * max_days
    draws = rng.choice(pool, size=(paths, n_trades), replace=True)

    equity = np.zeros(paths)
    peak = np.zeros(paths)
    day_pnl = np.zeros(paths)
    best_day = np.zeros(paths)          # largest single-day profit, for the consistency rule
    alive = np.ones(paths, bool)
    passed = np.zeros(paths, bool)
    days = np.zeros(paths, int)
    near = firm.target * 0.6

    for i in range(n_trades):
        # risk escalates once the trailing line has frozen, and again near the target
        # the trail has frozen once peak - D has risen to the cap
        locked = (peak - firm.dd) >= firm.cap
        f = np.where(locked, pol.f_base * pol.mult_locked, pol.f_base)
        f = np.where(equity >= near, f * pol.mult_near, f)
        step = draws[:, i] * f * firm.account

        equity = np.where(alive, equity + step, equity)
        day_pnl = np.where(alive, day_pnl + step, day_pnl)
        peak = np.maximum(peak, equity)

        alive &= (equity - np.minimum(peak - firm.dd, firm.cap)) > 0
        if firm.daily_loss:
            alive &= day_pnl > -firm.daily_loss

        if (i + 1) % pol.tpd == 0:
            days += alive
            best_day = np.maximum(best_day, np.where(alive, day_pnl, 0.0))
            day_pnl = np.zeros(paths)
            newly = alive & ~passed & (equity >= firm.target) & (days >= firm.min_days)
            passed |= newly
            alive &= ~newly

    if not passed.any():
        return 0.0, 0.0
    share = np.where(passed, best_day / np.maximum(equity, 1e-9), 0.0)
    ok = (share[passed] <= firm.consistency).mean() if firm.consistency else 1.0
    return float(passed.mean()), float(ok)


def score(pool, firm, pol, paths=20_000):
    p, ok = simulate(pool, firm, pol, paths=paths)
    if p == 0:
        return dict(pol=pol, p=0.0, ok=0.0, payout=0.0, ev=-firm.fee, ev_strict=-firm.fee)
    payout = funded_ev(pool, firm, pol.f_base * pol.mult_locked, paths=paths, trades_per_day=pol.tpd)
    ev = p * (payout - firm.activation) - firm.fee
    ev_strict = p * ok * (payout - firm.activation) - firm.fee   # consistency failures forfeit
    return dict(pol=pol, p=p, ok=ok, payout=payout, ev=ev, ev_strict=ev_strict)


def main():
    edge = float(sys.argv[1]) if len(sys.argv) > 1 else -0.02      # zero-edge baseline we measured
    firm_key = sys.argv[2] if len(sys.argv) > 2 else "topstep_50k"
    firm = FIRMS[firm_key]

    print(f"{firm.name}: target ${firm.target:,.0f}, trail ${firm.dd:,.0f} freezing at "
          f"+${firm.cap:,.0f}, fees ${firm.fee + firm.activation:,.0f}, "
          f"consistency {firm.consistency:.0%}")
    print(f"Trade distribution: zero-edge, mean {edge:+.3f}R (what random entries actually measured)\n")

    results = []
    for rr in (1.0, 1.5, 2.0, 3.0):
        pool = r_synthetic((edge + 1.0) / (rr + 1.0), rr, 1.0, n=20_000, seed=5)
        for f_base in (0.004, 0.006, 0.0075, 0.01):
            for mult_locked in (1.0, 1.5, 2.0, 3.0):
                for mult_near in (1.0, 0.5):
                    for tpd in (1, 2):
                        results.append(score(pool, firm, Policy(f_base, mult_locked, mult_near, rr, tpd)))
    results.sort(key=lambda r: -r["ev_strict"])

    print(f"  {'EV(strict)':>11} {'EV':>8} {'pass%':>7} {'consist.ok':>11}  policy")
    for r in results[:12]:
        print(f"  {r['ev_strict']:+11,.0f} {r['ev']:+8,.0f} {r['p']:7.1%} {r['ok']:11.1%}  {r['pol'].label()}")

    base = max((r for r in results if r["pol"].mult_locked == 1.0 and r["pol"].mult_near == 1.0),
               key=lambda r: r["ev_strict"])
    best = results[0]
    print(f"\n  best FIXED-risk policy:    EV {base['ev_strict']:+,.0f}  pass {base['p']:.1%}  ({base['pol'].label()})")
    print(f"  best ADAPTIVE policy:      EV {best['ev_strict']:+,.0f}  pass {best['p']:.1%}  ({best['pol'].label()})")
    gain = best["ev_strict"] - base["ev_strict"]
    print(f"  gain from using the frozen-trail structure: {gain:+,.0f} per attempt")


if __name__ == "__main__":
    main()
