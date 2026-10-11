"""Download free Dukascopy data for instruments tradeable on a prop account.

FIDELITY IS MEASURED, NOT ASSUMED
---------------------------------
Every instrument here is checked against the real futures contract before use:
5-minute return correlation and bar-range ratio over ~55 days of Yahoo futures
data. Measured 2026-10-12:

| source                   | -> future | 5m return corr | bar-range ratio |
|--------------------------|-----------|----------------|-----------------|
| INSTRUMENT_IDX_AMERICA_E_NQ_100 | NQ |    0.9840      |     0.977       |
| INSTRUMENT_FX_METALS_XAU_USD    | GC |    0.9835      |     0.996       |
| INSTRUMENT_FX_MAJORS_GBP_USD    | 6B |    0.9679      |     1.140       |
| INSTRUMENT_FX_MAJORS_EUR_USD    | 6E |    0.9673      |     1.050       |
| INSTRUMENT_US_TECH_US_USD       | NQ |    0.0077      |     0.000       |

The last row is the trap. `US_TECH` is a US-listed stock quoted around $72, not
an index -- it is what the first NQ study accidentally used, making every
strategy look catastrophic. `IDX_AMERICA_E_NQ_100` is the real Nasdaq-100 and
is the HIGHEST-fidelity source in this table.

NOTE ON A CORRECTED CLAIM: an earlier version of this file argued that
cash-index data misstates the opening range, because the index is built from
100 constituents that open staggered. That was measured on 2026-10-12 against
38 sessions of real NQ=F and found to be FALSE -- width ratio 0.97-1.00 and
signal agreement 87-89% at every window from 10m to 60m, with no trend toward
the short windows the hypothesis predicted. See
backtests/2026-10-12_cash_vs_futures_ORB.md. Free NQ data is fine.

GBP spot bars run 14% wider than the futures', which would fake extra stop-outs.
That is the only entry here with a real fidelity problem.

    .venv/bin/python research/fetch_data.py nq   2019 2026
    .venv/bin/python research/fetch_data.py gold 2019 2026
"""

import sys
import time
from datetime import datetime
from pathlib import Path

INSTRUMENTS = {
    "nq":     ("INSTRUMENT_IDX_AMERICA_E_NQ_100", "nq", "NQ / MNQ"),
    "gold":   ("INSTRUMENT_FX_METALS_XAU_USD", "xauusd", "GC / MGC"),
    "silver": ("INSTRUMENT_FX_METALS_XAG_USD", "xagusd", "SI / SIL"),
    "eurusd": ("INSTRUMENT_FX_MAJORS_EUR_USD", "eurusd", "6E / M6E"),
    "gbpusd": ("INSTRUMENT_FX_MAJORS_GBP_USD", "gbpusd", "6B"),
    "audusd": ("INSTRUMENT_FX_MAJORS_AUD_USD", "audusd", "6A / M6A"),
    "usdjpy": ("INSTRUMENT_FX_MAJORS_USD_JPY", "usdjpy", "6J"),
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in INSTRUMENTS:
        print(__doc__)
        print("instruments:")
        for k, (_, _, fut) in INSTRUMENTS.items():
            print(f"  {k:<8} -> trades as {fut}")
        raise SystemExit(1)

    import dukascopy_python as dk
    from dukascopy_python import instruments as I

    key = sys.argv[1]
    y0 = int(sys.argv[2]) if len(sys.argv) > 2 else 2019
    y1 = int(sys.argv[3]) if len(sys.argv) > 3 else datetime.now().year
    const, slug, fut = INSTRUMENTS[key]
    inst = getattr(I, const)

    out = Path(__file__).resolve().parent.parent / "data" / f"{slug}_5m"
    out.mkdir(parents=True, exist_ok=True)
    print(f"{key} ({slug}) -> trades as {fut}")
    print(f"writing to {out}\n")

    total = 0
    for year in range(y0, y1 + 1):
        path = out / f"{slug}_5m_{year}.csv"
        if path.exists():
            print(f"  {year}: already present, skipping")
            continue
        t0 = time.time()
        end = datetime(year + 1, 1, 1) if year < datetime.now().year else datetime.now()
        try:
            df = dk.fetch(inst, dk.INTERVAL_MIN_5, dk.OFFER_SIDE_BID,
                          datetime(year, 1, 1), end)
        except Exception as e:
            print(f"  {year}: FAILED {type(e).__name__}: {str(e)[:80]}")
            continue
        if df is None or not len(df):
            print(f"  {year}: no data")
            continue
        df = df[df["close"] > 0]
        df.index.name = "timestamp"
        df.to_csv(path)
        total += len(df)
        print(f"  {year}: {len(df):>7,} bars  "
              f"{df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}  "
              f"({time.time() - t0:.0f}s)")

    print(f"\ntotal {total:,} new bars in {out}")
    print(f"run a search with:  .venv/bin/python research/search_5m.py {out}")


if __name__ == "__main__":
    main()
