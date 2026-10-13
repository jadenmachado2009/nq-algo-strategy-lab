"""Conditional close momentum on NQ — testing J. Machado's hypothesis (2026-10-13).

HYPOTHESIS
----------
Forced hedging flow into the 16:00 ET cash close extends the day's move over the
final 30 minutes, but ONLY in high-volatility regimes.

Mechanism: dealers who are net short gamma must buy rallies and sell declines to
stay delta-neutral (Baltussen, Da, Lammers & Martens, JFE 2021); leveraged and
inverse ETFs must trade AUM x L(L-1) x r at the close, and L(L-1) > 0 for every
such fund. Both groups trade WITH the day's move regardless of price. Dealer
gamma is short after sell-offs (put demand) and long in calm uptrends (covered
calls), so the effect is conditional on the regime.

The hypothesis is pre-registered with FIVE predictions, all of which must hold:

  1. DIRECTION    sign(ROD) x ret(15:30->16:00) > 0 in the high-vol regime
  2. DOSE         continuation rises monotonically across |z| terciles
  3. REGIME       the effect is ~0 or negative in the low-vol regime
  4. PLACEBO      the same construction does not predict 13:00-13:30
  5. REVERSAL     sign(ROD) x ret over the next 1-3 sessions is <= 0

CALIBRATION, stated in advance: the published R^2 implies a directional hit rate
of only 54-56%. Gao, Han, Li & Zhou's own timing strategy was right 54.4% of the
time. **A backtest showing >= 60% is a bug or a fit, not a discovery.**

DEFINITIONS (computed at 15:30:00 ET)
    ROD    = P(15:30) / P(prev 16:00) - 1
    sigma20 = sd of the previous 20 sessions' 16:00-to-16:00 returns
    z      = ROD / sigma20
    high-vol regime: sigma20 above its trailing 252-session median

RULES
    eligible day: full cash session, not excluded, high-vol regime, |z| >= 0.5
    entry : first price after 15:30:00, in the direction of sign(ROD)
    exit  : last price at or before 16:00:00
    stop  : catastrophe only, at sigma20 x entry price
    target: none -- the flow completes at the close

EXCLUSIONS (each doubles as a test; they are run separately)
    - third Friday of Mar/Jun/Sep/Dec (expiry and index rebalances)
    - last trading day of the month (pension rebalancing trades the MONTH's move)
    - early closes / short sessions (no real 16:00 cash close)
    - low-vol regime, |z| < 0.5

    .venv/bin/python research/close_momentum.py [data_dir]
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import search as S  # noqa: E402
import search_5m as S5  # noqa: E402

COMMISSION_PTS = 0.62 / 2.0      # MNQ, $/contract/side -> points
SLIP_PTS = 0.25                  # one tick per side
Z_MIN = 0.5
VOL_LOOKBACK = 20
MEDIAN_LOOKBACK = 252
FULL_SESSION_BARS = 70           # 09:30-16:00 on 5m is 78; allow some slack


def build_days(d):
    """One record per session with the prices the hypothesis needs."""
    hm = d["hour"] * 100 + d["minute"]
    day = d["day"]
    o, c = d["o"], d["c"]
    out = []
    i, n = 0, len(c)
    while i < n:
        t = day[i]
        j = i
        while j < n and day[j] == t:
            j += 1
        idx = np.arange(i, j)
        i = j
        rth = idx[(hm[idx] >= 930) & (hm[idx] <= 1555)]
        if len(rth) < FULL_SESSION_BARS:
            short = True
        else:
            short = False
        def at(target, field):
            m = idx[hm[idx] == target]
            return (o[m[0]] if field == "o" else c[m[0]]) if len(m) else np.nan
        rec = dict(day=t,
                   p1530_open=at(1530, "o"),     # entry: first price after 15:30:00
                   p1555_close=at(1555, "c"),    # exit: last price at or before 16:00
                   p1300_open=at(1300, "o"),     # placebo window
                   p1325_close=at(1325, "c"),
                   p1230_open=at(1230, "o"),     # placebo needs its OWN run-of-day
                   short=short)
        out.append(rec)
    return out


def main():
    data_dir = sys.argv[1] if len(sys.argv) > 1 else "data/nq_5m"
    d = S5.load_dir(data_dir)
    days = build_days(d)
    days = [r for r in days if not np.isnan(r["p1530_open"]) and not np.isnan(r["p1555_close"])]

    close = np.array([r["p1555_close"] for r in days])      # the 16:00 cash close
    p1530 = np.array([r["p1530_open"] for r in days])
    dates = [r["day"] for r in days]
    short = np.array([r["short"] for r in days])

    # close-to-close returns, sigma20, regime
    cc = np.full(len(days), np.nan)
    cc[1:] = close[1:] / close[:-1] - 1
    sig = np.full(len(days), np.nan)
    for k in range(VOL_LOOKBACK + 1, len(days)):
        sig[k] = np.nanstd(cc[k - VOL_LOOKBACK:k])
    med = np.full(len(days), np.nan)
    for k in range(MEDIAN_LOOKBACK, len(days)):
        med[k] = np.nanmedian(sig[k - MEDIAN_LOOKBACK:k])
    highvol = sig > med

    # ROD and z, both known at 15:30
    rod = np.full(len(days), np.nan)
    rod[1:] = p1530[1:] / close[:-1] - 1
    z = rod / sig

    # the thing being predicted: the last 30 minutes
    ret_close = np.full(len(days), np.nan)
    ret_close = (close - p1530) / p1530
    # Placebo window. It needs its OWN run-of-day: using sign(ROD) measured at
    # 15:30 to predict the 13:00-13:30 return is LOOK-AHEAD, because that return
    # is part of the path from the prior close to 15:30. The placebo must be the
    # same construction evaluated at 13:00.
    p1300 = np.array([r["p1300_open"] for r in days])
    p1325 = np.array([r["p1325_close"] for r in days])
    ret_placebo = (p1325 - p1300) / p1300
    rod_pl = np.full(len(days), np.nan)
    rod_pl[1:] = p1300[1:] / close[:-1] - 1
    sgn_pl = np.sign(rod_pl)
    z_pl = rod_pl / sig

    # cost in return terms, applied to every trade
    cost = (2 * COMMISSION_PTS + 2 * SLIP_PTS) / p1530

    # calendar exclusions
    def third_friday_quarter(dt):
        return dt.month in (3, 6, 9, 12) and dt.weekday() == 4 and 15 <= dt.day <= 21
    months = np.array([dt.year * 100 + dt.month for dt in dates])
    is_month_end = np.zeros(len(days), bool)
    for k in range(len(days) - 1):
        if months[k] != months[k + 1]:
            is_month_end[k] = True
    is_month_end[-1] = True
    excl_cal = np.array([third_friday_quarter(dt) for dt in dates]) | is_month_end | short

    valid = ~np.isnan(z) & ~np.isnan(ret_close) & ~np.isnan(sig)
    sgn = np.sign(rod)
    # signed return net of costs: this is the strategy's P&L per trade
    pnl = sgn * ret_close - cost

    print(f"NQ CONDITIONAL CLOSE MOMENTUM — {dates[0]} -> {dates[-1]}, {len(days):,} sessions")
    print(f"  usable after warm-up: {valid.sum():,}  |  calendar exclusions: {excl_cal.sum():,}")
    print(f"  cost per round trip: {2*COMMISSION_PTS + 2*SLIP_PTS:.2f} pts "
          f"({np.nanmedian(cost)*1e4:.2f} bp)\n")

    elig = valid & highvol & (np.abs(z) >= Z_MIN) & ~excl_cal
    print(f"ELIGIBLE DAYS: {elig.sum():,}  "
          f"({elig.sum()/max((valid&~excl_cal).sum(),1):.1%} of clean sessions, "
          f"{elig.sum()/(len(days)/252):.0f}/year)")
    print(f"  hypothesis predicts 60-70/year\n")

    def stats(mask, label, arr=None):
        a = (pnl if arr is None else arr)[mask]
        if len(a) < 10:
            print(f"  {label:<34} n={len(a):<5} too few")
            return None
        hit = np.mean(a > 0)
        t = a.mean() / (a.std() / np.sqrt(len(a))) if a.std() > 0 else 0
        print(f"  {label:<34} n={len(a):<5} hit {hit:>5.1%}  mean {a.mean()*1e4:>+6.2f}bp  t={t:>+5.2f}")
        return dict(n=len(a), hit=hit, mean=a.mean(), t=t)

    print("PREDICTION 1 — direction (high-vol, |z|>=0.5, exclusions applied)")
    r1 = stats(elig, "eligible days")
    print()

    print("PREDICTION 2 — dose-response across |z| terciles")
    az = np.abs(z)
    q = np.nanquantile(az[elig], [1/3, 2/3])
    for lo, hi, lab in ((Z_MIN, q[0], f"|z| {Z_MIN:.2f}-{q[0]:.2f}"),
                        (q[0], q[1], f"|z| {q[0]:.2f}-{q[1]:.2f}"),
                        (q[1], 1e9, f"|z| > {q[1]:.2f}")):
        stats(elig & (az >= lo) & (az < hi), lab)
    print()

    print("PREDICTION 3 — regime split")
    stats(valid & highvol & (az >= Z_MIN) & ~excl_cal, "HIGH vol (the claim)")
    stats(valid & ~highvol & (az >= Z_MIN) & ~excl_cal, "LOW vol (should be ~0 or neg)")
    print()

    print("PREDICTION 4 — timing placebo (13:00-13:30, same construction)")
    pl = sgn_pl * ret_placebo - cost
    pl_elig = valid & highvol & (np.abs(z_pl) >= Z_MIN) & ~excl_cal & ~np.isnan(ret_placebo)
    stats(pl_elig, "13:00-13:30, own run-of-day", arr=pl)
    stats(elig & ~np.isnan(ret_placebo), "  (buggy version, look-ahead)",
          arr=sgn * ret_placebo - cost)
    print()

    print("PREDICTION 5 — reversal over the next 1-3 sessions")
    for h in (1, 2, 3):
        fwd = np.full(len(days), np.nan)
        if h < len(days):
            fwd[:-h] = close[h:] / close[:-h] - 1
        stats(elig & ~np.isnan(fwd), f"next {h} session(s)", arr=sgn * fwd)
    print()

    print("EXCLUDED DAYS — if these look the same, the filter is decoration")
    stats(valid & excl_cal & highvol & (az >= Z_MIN), "calendar-excluded, high vol")
    stats(valid & ~excl_cal & highvol & (az < Z_MIN), "|z| < 0.5, high vol")
    print()

    # in-sample / out-of-sample
    cut = len(days) * 70 // 100
    ins = np.zeros(len(days), bool); ins[:cut] = True
    print("IN-SAMPLE / OUT-OF-SAMPLE")
    stats(elig & ins, f"IS  {dates[0]} -> {dates[cut]}")
    stats(elig & ~ins, f"OOS {dates[cut]} -> {dates[-1]}")
    print()

    # block bootstrap by month, as the hypothesis requires
    if r1:
        print("BLOCK BOOTSTRAP by calendar month (regimes cluster)")
        em = months[elig]; ep = pnl[elig]
        um = np.unique(em)
        rng = np.random.default_rng(7)
        boot = np.empty(10000)
        idxm = {m: np.where(em == m)[0] for m in um}
        for b in range(10000):
            pick = rng.choice(um, size=len(um), replace=True)
            boot[b] = ep[np.concatenate([idxm[m] for m in pick])].mean()
        lo, hi = np.percentile(boot, [2.5, 97.5])
        print(f"  mean {ep.mean()*1e4:+.2f}bp  95% CI [{lo*1e4:+.2f}, {hi*1e4:+.2f}]bp  "
              f"P(>0) = {np.mean(boot > 0):.1%}")
        print(f"\n  CALIBRATION CHECK: hypothesis says 54-56% hit rate; >=60% means a bug.")
        print(f"  observed {r1['hit']:.1%} -> "
              f"{'PLAUSIBLE' if r1['hit'] < 0.60 else 'TOO HIGH — SUSPECT A BUG'}")


if __name__ == "__main__":
    main()
