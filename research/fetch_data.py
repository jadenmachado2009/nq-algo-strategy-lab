"""Download free Dukascopy spot data for instruments tradeable on a prop account.

WHY THIS EXISTS
---------------
The NQ study was run on Dukascopy's "US_TECH" feed, which turned out to track the
CASH Nasdaq-100 index, not the futures contract (+5 pts vs ^NDX, -97 vs NQ=F).
Basis and roll do not affect an intraday strategy, but the cash index is computed
from 100 stocks that open STAGGERED over the first minutes of the session, so its
opening prints are stale -- precisely where an opening-range strategy looks.

The fix is not a better index feed. It is to research instruments whose free data
is genuinely faithful to the contract you would trade.

MEASURED FIDELITY (5m bars, ~55 days, vs the real futures on Yahoo)

| spot    -> future | 5m return corr | bar-range ratio |
|---------|----------|----------------|-----------------|
| XAUUSD  -> GC      | 0.9835         | 0.996           |
| GBPUSD  -> 6B      | 0.9679         | 1.140           |
| EURUSD  -> 6E      | 0.9673         | 1.050           |

Gold wins: its bars are effectively the futures' bars. GBP spot bars run 14%
wider than the futures', which would show stops being hit more often in a
backtest than in reality.

Spot FX and spot gold trade continuously with no opening auction, so there is
nothing to go stale. They also arbitrage against their futures in ONE trade,
unlike an index, which needs all 100 constituents -- which is why they track so
much more tightly.

    .venv/bin/python research/fetch_data.py gold 2019 2026
    .venv/bin/python research/fetch_data.py eurusd 2019 2026
"""

import sys
import time
from datetime import datetime
from pathlib import Path

INSTRUMENTS = {
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
