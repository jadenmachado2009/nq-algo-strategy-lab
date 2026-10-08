"""The video's challenge model, run on OUR measured coin-flip trades.

DeltaTrend's slides model a challenge as: start $50,000, pass at $53,000, fail at
a STATIC floor of $48,000, with an EV=0 strategy. Their result: pass rate ~40%
for every reward:risk (which is the gambler's-ruin value D/(G+D) = 2000/5000),
rising to ~48% with fixed-fractional sizing.

Two things this adds:

  1. Real trades instead of idealised ones. Their EV=0 strategies are clean
     two-outcome draws (+rr or -1). Ours come from coin-flip entries on real NQ
     data with commission, slippage, gap-through fills and an end-of-day flatten,
     so winners and losers are smeared across a range and the expectancy is
     slightly negative rather than exactly zero.

  2. Both floor types. A static floor is CFD/FX-style (FTMO and similar). Futures
     firms (Topstep, Apex) use a TRAILING floor that rises behind your profits and
     freezes once far enough ahead. The same strategy scores very differently
     under each, which is the single biggest fork in this whole analysis.

    .venv/bin/python ../research/video_model.py
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search as S  # noqa: E402

V0, G, D = 50_000.0, 3_000.0, 2_000.0      # start, target (+$3k), drawdown ($2k)
CAP = 0.0                                   # trailing floor freezes at breakeven
PATHS = 40_000
MAX_TRADES = 800
FEE = 314.0                                 # evaluation + activation


def coinflip_pool(d, a, sl_mult, tp_mult, seeds=12, rate=0.04):
    """Measured R-multiples from random entries with a given bracket."""
    out = []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        n = len(d["c"])
        sig = rng.random(n) < rate
        longs = sig & (rng.random(n) < 0.5)
        shorts = sig & ~longs
        out.append(S.simulate(d, a, longs, shorts, sl_mult, tp_mult))
    return np.concatenate(out)


def challenge(pool, risk_mode="frac", risk_param=0.02, trailing=False, seed=1):
    """Returns (pass_rate, avg_trades_to_pass)."""
    rng = np.random.default_rng(seed)
    eq = np.zeros(PATHS)
    peak = np.zeros(PATHS)
    alive = np.ones(PATHS, bool)
    passed = np.zeros(PATHS, bool)
    ttp = np.zeros(PATHS)

    for i in range(MAX_TRADES):
        risk = (V0 + eq) * risk_param if risk_mode == "frac" else np.full(PATHS, risk_param)
        step = rng.choice(pool, size=PATHS) * risk
        eq = np.where(alive, eq + step, eq)
        peak = np.maximum(peak, eq)

        floor = np.minimum(peak - D, CAP) if trailing else np.full(PATHS, -D)
        alive &= eq > floor

        newly = alive & ~passed & (eq >= G)
        ttp = np.where(newly, i + 1, ttp)
        passed |= newly
        alive &= ~newly

    return float(passed.mean()), float(ttp[passed].mean()) if passed.any() else 0.0


def main():
    d = S.load_hourly()
    a, *_ = S.build_blocks(d)
    print(f"Data: {d['t'][0]:%Y-%m-%d} -> {d['t'][-1]:%Y-%m-%d}, hourly NQ")
    print(f"Challenge: start ${V0:,.0f}, pass ${V0 + G:,.0f}, fail ${V0 - D:,.0f}")
    print(f"Gambler's-ruin value for a fair game: D/(G+D) = {D / (G + D):.1%}\n")

    # 3xATR stop keeps the toll small; target = half the stop -> the video's 0.5:1 profile
    setups = [("0.5:1  (3xATR stop, 1.5xATR target)", 3.0, 1.5),
              ("1:1    (3xATR stop, 3xATR target)", 3.0, 3.0),
              ("2:1    (3xATR stop, 6xATR target)", 3.0, 6.0),
              ("0.5:1 TIGHT (1xATR stop)", 1.0, 0.5)]

    print(f"  {'setup':<36} {'WR':>6} {'exp(R)':>8} {'static':>8} {'trailing':>9} {'trades':>7}")
    for label, sl, tp in setups:
        pool = coinflip_pool(d, a, sl, tp)
        p_static, ttp = challenge(pool, trailing=False)
        p_trail, _ = challenge(pool, trailing=True)
        print(f"  {label:<36} {np.mean(pool > 0):>5.1%} {pool.mean():>+8.3f} "
              f"{p_static:>7.1%} {p_trail:>8.1%} {ttp:>7.0f}")

    print("\nSizing rule, on the 0.5:1 setup (static floor):")
    pool = coinflip_pool(d, a, 3.0, 1.5)
    for mode, param, label in (("frac", 0.01, "1% of equity"), ("frac", 0.02, "2% of equity"),
                               ("frac", 0.04, "4% of equity"), ("fixed", 500.0, "$500 flat"),
                               ("fixed", 1000.0, "$1,000 flat")):
        p, ttp = challenge(pool, risk_mode=mode, risk_param=param)
        ev = p * 1_900 - FEE     # rough: average payout if funded, minus fees
        print(f"  {label:<16} pass {p:>5.1%}   avg trades to pass {ttp:>4.0f}   rough EV {ev:>+7,.0f}")


if __name__ == "__main__":
    main()
