"""ORB paper tracker — run this daily. It answers one question: fund, or wait?

WHY THIS EXISTS
---------------
The forward test on 2026-10-13 found ORB in the worst drawdown of its recorded
history: win rate 48.6% in 2026Q3 against a 65.7% seven-year baseline, confirmed
on two independent data sources. A permutation test gives p = 0.0001, so it is a
genuine structural break rather than a bad draw.

What broke is FOLLOW-THROUGH, not the setup. Opening ranges are normal (0.55%
width, 3.92x ATR, both at their historical average), but median MFE fell from
0.52R to 0.43R -- below the 0.50R target, so the median trade can no longer
reach its own target. MAE deepened from -0.35 to -0.57.

THE DECISION RULE
-----------------
Monitor the WIN RATE on a rolling 150-trade window. Power analysis: the win-rate
gap (65.7% vs 48.6%) needs ~127 trades per group for 80% power; median MFE needs
~270 for the same confidence. So win rate is the monitor and MFE is the
explanation, not the other way round.

    HEALTHY   win rate >= 65%   -> the mechanism is working, funding is justified
    MARGINAL  60-65%            -> keep waiting
    IMPAIRED  < 60%             -> do not fund

MFE >= 0.50 is the confirming signal: it means follow-through has returned.

This costs nothing to run and requires no broker. It tracks the SIGNAL, which is
what decides funding. Live fills are a separate question, answered by the IBKR
paper bot once TWS is running.

    .venv/bin/python execution/orb_tracker.py            # update and report
    .venv/bin/python execution/orb_tracker.py --report   # report only, no fetch
"""

import csv
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

LOG = ROOT / "execution" / "orb_paper_log.csv"
WINDOWS = (10, 20, 30, 45, 60)
RR = 0.5
COMMISSION_PTS = 0.62 / 2.0      # MNQ
SLIP = 0.25
TICK = 0.25
ROLLING = 150

HEALTHY, MARGINAL = 0.65, 0.60
BASELINE_WR = 0.657              # seven-year baseline, 2019 - 2026Q2
BASELINE_MFE = 0.52              # median
FIELDS = ["date", "window", "R", "outcome", "mfe", "mae", "range_pts", "entry"]


def fetch():
    """Real NQ futures, 5m, last 60 days. Free, no account."""
    import warnings
    warnings.filterwarnings("ignore")
    import yfinance as yf
    y = yf.download("NQ=F", interval="5m", period="60d", progress=False, auto_adjust=False)
    if not len(y):
        raise SystemExit("no data returned from Yahoo")
    y.index = y.index.tz_convert("America/New_York")
    arr = lambda c: np.asarray(y[c].values).ravel()  # noqa: E731
    d = dict(o=arr("Open"), h=arr("High"), l=arr("Low"), c=arr("Close"),
             hour=np.array([x.hour for x in y.index]),
             minute=np.array([x.minute for x in y.index]),
             day=np.array([x.date() for x in y.index]))
    ok = ~np.isnan(d["c"])
    return {k: v[ok] for k, v in d.items()}


def trades(d, w):
    """ORB trades for one window, with the diagnostics the decision rule needs."""
    hm = d["hour"] * 100 + d["minute"]
    day = d["day"]
    o, h, l, c = d["o"], d["h"], d["l"], d["c"]
    n = len(c)
    out, i = [], 0
    while i < n:
        t = day[i]
        j = i
        while j < n and day[j] == t:
            j += 1
        idx = np.arange(i, j)
        i = j
        s = idx[hm[idx] >= 930]
        if len(s) < 10:
            continue
        sm = (hm[s] // 100) * 60 + (hm[s] % 100)
        rb = s[sm < 9 * 60 + 30 + w]
        rest = s[sm >= 9 * 60 + 30 + w]
        if len(rb) < 1 or len(rest) < 3:
            continue
        hi, lo = h[rb].max(), l[rb].min()
        if hi - lo < 2 * TICK:
            continue
        trig = next((rest[k] for k in range(len(rest) - 1) if c[rest[k]] > hi), None)
        if trig is None:
            continue
        ei = trig + 1
        if ei >= n or day[ei] != t:
            continue
        entry = o[ei] + SLIP
        risk = entry - lo
        if risk < TICK:
            continue
        tgt = entry + risk * RR
        ex, how, mfe, mae = None, "eod", 0.0, 0.0
        for m in range(ei, j):
            mfe = max(mfe, (h[m] - entry) / risk)
            mae = min(mae, (l[m] - entry) / risk)
            if l[m] <= lo:
                ex, how = min(o[m], lo) - SLIP, "stop"
                break
            if h[m] >= tgt:
                ex, how = tgt, "target"
                break
        if ex is None:
            ex = c[j - 1] - SLIP
        out.append(dict(date=t.isoformat(), window=w, outcome=how,
                        R=round(((ex - entry) - 2 * COMMISSION_PTS) / risk, 5),
                        mfe=round(mfe, 4), mae=round(mae, 4),
                        range_pts=round(hi - lo, 2), entry=round(entry, 2)))
    return out


def load_log():
    if not LOG.exists():
        return []
    with open(LOG) as f:
        return list(csv.DictReader(f))


def update():
    rows = load_log()
    seen = {(r["date"], str(r["window"])) for r in rows}
    fresh = []
    d = fetch()
    for w in WINDOWS:
        for t in trades(d, w):
            if (t["date"], str(t["window"])) not in seen:
                fresh.append(t)
    if fresh:
        rows += fresh
        rows.sort(key=lambda r: (r["date"], int(r["window"])))
        with open(LOG, "w", newline="") as f:
            wr = csv.DictWriter(f, fieldnames=FIELDS)
            wr.writeheader()
            wr.writerows(rows)
    return rows, len(fresh)


def report(rows):
    if not rows:
        print("no trades logged yet")
        return
    rows = sorted(rows, key=lambda r: (r["date"], int(r["window"])))
    R = np.array([float(r["R"]) for r in rows])
    mfe = np.array([float(r["mfe"]) for r in rows])
    dates = [r["date"] for r in rows]

    print(f"ORB PAPER TRACKER     {dates[0]} -> {dates[-1]}")
    print(f"  {len(rows):,} trades logged across {len(set(dates)):,} sessions\n")

    def block(lab, m):
        if m.sum() < 5:
            print(f"  {lab:<22} n={m.sum():<4} too few")
            return None
        wr_, mf = np.mean(R[m] > 0), np.median(mfe[m])
        print(f"  {lab:<22} n={m.sum():<4} win rate {wr_:>5.1%}   median MFE {mf:>5.3f}   "
              f"exp {R[m].mean():>+7.4f}R")
        return wr_, mf

    all_m = np.ones(len(rows), bool)
    block("all logged", all_m)
    last = np.zeros(len(rows), bool)
    last[-ROLLING:] = True
    cur = block(f"last {ROLLING} trades", last)
    last50 = np.zeros(len(rows), bool)
    last50[-50:] = True
    block("last 50 trades", last50)

    print(f"\n  benchmarks: baseline win rate {BASELINE_WR:.1%}, median MFE {BASELINE_MFE:.2f}")
    print(f"              2026Q3 break: 48.6% win rate, MFE 0.43\n")

    if cur is None:
        return
    wr_, mf = cur
    if wr_ >= HEALTHY:
        verdict, note = "HEALTHY", "win rate has recovered — funding is justified"
    elif wr_ >= MARGINAL:
        verdict, note = "MARGINAL", "recovering but not yet at the 65% threshold — keep waiting"
    else:
        verdict, note = "IMPAIRED", "do NOT fund an account"
    print(f"  VERDICT: {verdict}  ({wr_:.1%} on the last {min(len(rows), ROLLING)} trades)")
    print(f"           {note}")
    conf = "confirms" if mf >= 0.50 else "does not confirm"
    print(f"           median MFE {mf:.3f} {conf} follow-through has returned (need >= 0.50)")
    if len(rows) < ROLLING:
        print(f"\n  NOTE: only {len(rows)} trades logged; {ROLLING} needed for a full window.")
        print(f"        ~127 trades gives 80% power to distinguish recovery from noise.")


if __name__ == "__main__":
    if "--report" in sys.argv:
        report(load_log())
    else:
        rows, n = update()
        print(f"fetched: {n} new trades appended to {LOG.name}\n")
        report(rows)
