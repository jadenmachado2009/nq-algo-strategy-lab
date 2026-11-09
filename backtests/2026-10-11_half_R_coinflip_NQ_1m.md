# Coin-flip entry, 1R stop / 0.5R target — NQ 1m, NY 09:30–11:00 — 2026-10-11

**Verdict:** Reject. Zero edge before costs (exactly what the random-walk maths predicts), negative after.

## Setup
| | |
|---|---|
| Tool | `research/half_r.py` (validated on synthetic random walk: converges to 0R before costs) |
| Data | Yahoo `NQ=F` 1m, 2026-09-14 → 2026-10-09, 20 sessions (Dukascopy multi-year pull hit HTTP 429) |
| Rules | Random direction, one position at a time, re-enter next bar, flat at 11:00, bracket from the fill |
| Costs | Market entry +1 tick, stop exit −1 tick, TP limit needs 1-tick trade-through; NQ $2.50/side, MNQ $0.62/side |
| Seeds | 200 per config |

## Result (NQ)
| stop | trades | WR no-cost | exp no-cost | WR real | exp real | PF |
|---|---|---|---|---|---|---|
| 10pt | 1634 | 65.9% | −0.010R | 63.0% | −0.088R | 0.77 |
| 15pt | 1310 | 66.8% | +0.004R | 64.8% | −0.047R | 0.87 |
| 20pt | 1002 | 66.6% | +0.004R | 65.0% | −0.037R | 0.90 |
| 40pt | 392 | 66.2% | +0.003R | 65.6% | −0.013R | 0.97 |
| 1×ATR | 816 | 66.3% | −0.001R | 64.9% | −0.035R | 0.90 |

5pt stops are not measurable on 1m bars (median 1m ATR 22pt: stop-first −0.63R vs target-first +0.14R) — would need tick data.

## Why
P(hit +0.5R before −1R) = 1/1.5 = 66.7% on a driftless walk, so E = 0 for any timeframe/session.
Timeframe and session only change volatility, i.e. how many R the fixed costs eat. Tighter stop = worse.
Full table: `research/half_r_results.csv`.

---

## Topstep 50K Combine — pass probability (15pt spec)

Tool: `research/topstep_half_r.py`. Real per-day trade sequences (20 sessions × 500 seeds), days resampled,
20,000 paths, 60-day horizon. Rules as in `2026-10-09_topstep_50k.md`. Full grid: `research/topstep_half_r_results.csv`.

| Size | Risk/trade | Trades/day | Pass | Days to pass |
|---|---|---|---|---|
| 1 NQ | $300 | 1 | 0.8% | 44 |
| 1 NQ | $300 | all (~66) | 2.0% | 4.5 |
| 2 NQ | $600 | 1 | 9.7% | 28 |
| 3 NQ | $900 | 1 | 16.1% (±0.5 across seeds) | 16 |
| **5 NQ** | **$1,500** | **1** | **21.7%** | 8 |
| 10 MNQ | $300 | any | ≤1% | — |

Zero-cost reference (3/day): 3 NQ 19.6%, 2 NQ 14.1% — the trailing EOD MLL alone caps a no-edge strategy near ~20%.

Takeaways: taking every trade in the window (~66/day) fails ~98% at any size — the −0.047R cost drag
compounds per trade. Best pass = fewest trades at max size, i.e. a lottery ticket, and two losses kill it.
MNQ is worse (−0.071R: commission is 2.5× NQ's in points).

### $1,000 risk per trade (2% of 50K), 0.5R target, coin flip

Expectancy re-centred to the theoretical cost drag (the 20-session sample is ±0.06R noise at wide stops).

| Combo | exp | Pass @1/day | @2/day | @3/day | every signal |
|---|---|---|---|---|---|
| 1 NQ @ 50pt | −0.012R | **34.4%** | 30.1% | 26.0% | ~15% |
| 2 NQ @ 25pt | −0.023R | 33.1% | 28.9% | 31.5% | ~5% |
| 3 NQ @ 16.75pt | −0.035R | 20.4% | 15.8% | 20.8% | ~1% |
| 10 MNQ @ 50pt | −0.019R | 33.6% | 29.2% | 25.0% | ~14% |

One loss (~$1,010 with costs) trips the $1,000 DLL, two net losses breach the MLL. Zero-edge static
gambler's-ruin ceiling is 40% (2,000 / 5,000); the trailing MLL and costs take it to ~33%.
Stops ≤ 17pt on 1m bars are less reliable (opening-bar ambiguity).

### 5 independent Topstep 50K accounts, end to end (Combine → XFA → payouts), 126 trading days

Tool: `research/topstep_multi.py`. 1 NQ @ 50pt, first trade of day only, re-centred to −0.012R.
**Correction:** pass rate per account is **27.6%**, not 34%. The earlier figure re-centred across all trades, and the
day's first trades happened to be lucky in this sample.

| | |
|---|---|
| Pass per account | 27.6%, median 11 trading days |
| ≥1 payout per account | 15.2%, median day 19 |
| 5 accounts: mean net | +$830 (fees $466, payouts $1,296) |
| 5 accounts: median net | −$81 |
| P(net > 0) | 47% |
| p5 / p95 | −$543 / +$4,983 |
| P(≥1 payout across 5) | 56%, median first payout day 17 |

Sensitivity (mean / median / P>0): −0.04R → +$419 / −$245 / 38% · −0.08R → +$47 / −$245 / 23% · $0 activation → +$1,037 / +$217 / 52%.
Positive mean comes from capped downside (fees only) vs payouts — the firm absorbs the trading losses.
