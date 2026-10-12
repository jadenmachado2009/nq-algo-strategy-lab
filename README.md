# NQ Algo Strategy Lab

A testing pipeline for futures strategies on NQ/MNQ, built around one rule: **a strategy is assumed
worthless until evidence says otherwise, and the evidence has to survive a test designed to fail it.**

The lab has retired one strategy, failed to validate a second, rejected its own best search result
three times, and — in v5 — found four errors in its own published numbers. Those are the results.
The point of the pipeline is to produce them cheaply, before money is involved.

---

## Versions

**[v5 — four corrections, and the number that actually matters](https://github.com/jadenmachado2009/nq-algo-strategy-lab/releases/tag/v5)** ← current

v4 reported ORB as validated at **+0.022R** with a **39.2%** pass rate and concluded the economics
were *"EV-positive, median-negative — a lottery, not an income."* Re-verifying every input on
freshly downloaded, reproducible data found **four errors**, two of which were too pessimistic and
two of which were unfounded. Corrected:

| | v4 | v5 |
|---|---|---|
| Out-of-sample edge | +0.011R | **+0.0316R** over ~2,100 trades |
| Optimal risk | 0.75% | **0.50%** |
| Pass rate | 39.2% | **39.1%** — flat at ~40% at *every* risk level |
| Median days to pass | 7 | **14** |
| EV per attempt | +$502 | **+$466** |
| Break-even pass rate | — | **3.7%** |
| 5 attempts, P(profit) | 44.6% | **56.3%** |

v4's conclusion — *"EV-positive, median-negative"* — turns out to be **right**, but for a different
reason than it gave. The firm-mismatch bug it contained was real; so is the negative median.

ORB's edge is **87.5% likely positive** on a day-clustered bootstrap — probably real, not
established at 95%. See [why the numbers changed](#why-the-numbers-changed) below.

<details>
<summary><b>v4 — ORB: a measured edge, and what it's worth</b></summary>

The first strategy here to pass its null test. Superseded by v5, which corrects its pass rate, its
EV, its out-of-sample edge, and its conclusion. The strategy spec itself is unchanged.
</details>

<details>
<summary><b>v3 — prop convexity: risk geometry over edge</b></summary>

A real futures trailing drawdown freezes once you're far enough ahead (`dd_line = min(peak − D, cap)`),
so variance is expensive before the freeze and cheap after it. Trading small then escalating is worth
+$49–73 per attempt over any fixed-risk plan. Still stands.
</details>

<details>
<summary><b>v2 — evidence-first validation suite</b></summary>

The searches that found nothing, and the machinery that proved it: QuantConnect backtests, the IBKR
paper bot, the 450-combo search with its null test, and `research/MATH.md`.
</details>

---

## Why the numbers changed

Four errors, found by re-verifying every input from scratch. Each is recorded in `backtests/`.

### 1. The wrong firm's payout rules (the big one)

`backtests/2026-10-09_portfolio_bankroll.md` is titled *"ORB on Topstep 50K"*. But `bankroll.py`
defaults to `apex_50k`, so it computed **Topstep's** pass rate and then applied **Apex's**
funded-account rules to it.

```
Apex profile:     payout threshold $1,000, funded DD $2,500  ->  51% never pay out, median $0
Topstep profile:  5 winning days >= $150, DD locks at breakeven -> 16.5% never pay out, median $1,499
```

That single mismatch produced the "median −$188, a lottery not an income" conclusion. Under
Topstep's actual published rules the median at five attempts is **+$969**.

### 2. The wrong out-of-sample number

v4 quoted **+0.011R** as ORB's out-of-sample edge. That is the *single best config* — 60m long alone,
379 trades. The spec the analysis actually uses is **five windows pooled**, whose out-of-sample edge
is **+0.0297R over 2,105 trades** — higher than the full-period +0.0227R.

The edge did not decay out of sample. Two different measurements were being compared.

### 3. A data-quality claim that was never tested

From 2026-10-10 this repo asserted that Dukascopy's NQ feed was unfit because it tracks the cash
index, whose constituents open staggered and make the first prints stale — "exactly where ORB looks."
Plausible, repeated in three files, never measured.

Measured against 60 days of real `NQ=F` over 38 shared sessions: **width ratio 0.97–1.00, width
correlation 0.997+, signal agreement 87–89% at every window from 10m to 60m.** The hypothesis
predicts the distortion is worst at the shortest window. There is no trend at all. The effect is
absent, and `IDX_AMERICA_E_NQ_100` has **0.9840** return correlation with real NQ futures — the
highest-fidelity free source tested, better than gold.

*(Not to be confused with `US_TECH_US_USD`, a US stock quoted around $72, which scores 0.0077. That
one is a genuine trap and is documented in `research/fetch_data.py`.)*

### 4. The null test's bar is lower than it reads

ORB passed its null test on gold (p = 0.000) **and lost money out of sample**. Both are true because
they ask different questions. All 15 noise runs came back negative (mean −0.061R) because noise pays
the toll and gold's toll is heavy — so the bar to clear was **−0.027R**. A mediocre +0.011R clears it.

**A null test asks "better than noise after costs", not "profitable."** On a high-cost instrument
that bar sits below zero. This applies retroactively to NQ's p = 0.00, where noise averaged −0.031R.
It rules out one failure mode — data mining — and establishes nothing else.

---

## ORB — the current state

Opening Range Breakout on NQ. Range = first N minutes after 09:30 NY; enter on the first 5m close
beyond it at the *next* bar's open; stop at the opposite side; target = 0.5 × the stop; long only;
one trade per day per window; flat by the close. Five windows (10/20/30/45/60) run in parallel.

| | |
|---|---|
| Full period | 6,995 trades, 65.2% WR, **+0.0246R** |
| Out-of-sample | ~2,100 trades, **+0.0316R** |
| Day-clustered 95% CI | **[−0.0202, +0.0768]**, P(edge > 0) = **87.5%** |
| Null test | p = 0.00 — see correction 4 for what that does and doesn't mean |

**Direction selection survives out-of-sample.** Long-only was chosen in-sample; on unseen data long
gives +0.0297R against short's +0.0052R and both at +0.0035R.

### Year by year

| 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|
| +0.032 | **−0.036** | +0.039 | +0.040 | +0.034 | +0.030 | +0.060 | **−0.018** |

Two negative years. **2020 was twice as bad as 2026 and the edge recovered completely** (+0.039,
+0.040, +0.034 in the three years after). A permutation test on whether 2026 differs from earlier
years gives **p = 0.184** — not distinguishable from an ordinary bad draw. Year-to-year SD is
0.0302R, so a negative year is a normal feature of this series.

Honest caveat: with noise that size, power to *detect* real decay is poor. The correct statement is
"no detectable decay", not "proven stable".

### Topstep 50K economics

Each session is replayed in true **exit order**, with a leg taken only if its entry preceded the
moment the daily lockout fired. No assumed parameters — the overlap is read from the data (measured:
1.36 positions in-flight on average when the limit is hit, 3.83 open simultaneously at peak).

| Risk | $/trade | Pass | Median days | 1% worst day | Floor (no lockout) |
|---|---|---|---|---|---|
| **0.50%** | **$250** | **39.4%** | **14** | **−$1,455** | 39.0% |
| 0.75% | $375 | 40.4% | 8 | −$2,018 | 39.6% |
| 1.00% | $500 | 40.2% | 5 | −$2,626 | 39.1% |
| 1.25% | $625 | 40.3% | 4 | −$3,273 | 39.2% |

**Pass rate is flat at ~40% at every risk level** (gambler's-ruin scale invariance), and **the daily
lockout is worth essentially nothing** — 40.2% against a 39.1% floor. By the time it fires your
positions are already open, and a lockout cannot close them. Risk changes how *fast* you resolve and
how bad your worst day is, not *whether* you pass.

### Sequential attempts at 0.50%

| Tries | Spend | P(≥1 pass) | P(profit) | Median | Mean |
|---|---|---|---|---|---|
| 1 | $49 | 39.1% | 24.5% | −$49 | +$468 |
| 3 | $97 | 77.4% | 47.9% | −$147 | +$924 |
| **5** | **$115** | **91.6%** | **56.3%** | **+$461** | **+$1,085** |
| 10 | $125 | 99.3% | 61.0% | +$695 | +$1,187 |

**0.50% is chosen over faster settings** because pass rate is identical across risk, so the decision
is made downstream: only **36.7%** of funded accounts never pay out at 0.50% against **60.3%** at
1.00%, which flips the five-attempt median from −$198 to **+$461**. It is also the only setting whose
worst day (−$1,455) stays inside the $2,000 limit. 1.00% has a higher *mean* (+$584) and a worse
*median* — for a small bankroll the median is what matters.

---|---|---|---|---|---|
| 0.50% | $250 | 39.3% | 14 | −$1,455 | no |
| 0.75% | $375 | 39.9% | 8 | −$2,018 | yes |
| **1.00%** | **$500** | **41.7%** | **5** | −$2,184 | yes |
| 1.25% | $625 | 40.7% | 4 | −$2,653 | yes |

**The pass rate is flat at ~40% at every risk level** — gambler's-ruin scale invariance. With a fixed
edge, pass probability does not depend on bet size. Risk changes how *fast* you resolve, not
*whether* you pass.

### Sequential attempts at 1.00%

| Tries | Spend | P(≥1 pass) | P(profit) | Median | Mean |
|---|---|---|---|---|---|
| 1 | $49 | 41.7% | 17.3% | −$49 | +$649 |
| 3 | $94 | 80.2% | 33.1% | −$147 | +$1,240 |
| **5** | **$109** | **93.2%** | **38.6%** | **−$198** | **+$1,447** |
| 10 | $117 | 99.5% | 41.5% | −$198 | +$1,553 |

**Positive EV, negative median.** Break-even is **2.9%** against an actual 41.7% — a 14× margin — but
most single attempts lose the fee, because **58% of funded accounts never pay out**. The expectancy
sits in the ~25% of runs reaching several thousand. This is a well-priced bet you will probably lose
on any one try.

---|---|---|---|---|
| **0.50%** | $250 | **43.9%** | **39.0%** | **15** |
| 0.75% | $375 | 49.8% | 39.6% | 8 |
| 1.00% | $500 | 56.7% | 39.1% | 6 |
| 1.50% | $750 | 54.3% | 36.4% | 5 |

Higher risk looks better only because the daily lockout clips losing days while winning days run.
**At 0.50% the result barely depends on it (43.9% vs 39.0%), which is why that is the recommended
setting.** Adding more opening-range windows amplifies the same effect — 11 windows appears to give
61.8%, but 21.8 points of that is the lockout, and with that many overlapping positions it cannot
intervene between simultaneous losses. Rejected for that reason.

Break-even pass rate is **8.2%**. Sequential attempts at 0.50%, stopping after the first pass:

| Tries | Spend | P(≥1 pass) | P(profit) | Median | Mean |
|---|---|---|---|---|---|
| 1 | $147 | 43.5% | 35.0% | −$147 | +$637 |
| 3 | $277 | 82.0% | 64.7% | +$778 | +$1,197 |
| **5** | **$318** | **94.2%** | **73.4%** | **+$969** | **+$1,373** |
| 10 | $338 | 99.7% | 76.7% | +$1,022 | +$1,454 |

Note the trade-off: 0.50% risk means roughly **54 days to pass**, so each attempt is a two-to-three
month commitment, not a week.

---

## What the searches found: nothing, three times

| Study | Instrument | Grid | Best real | Noise mean | p |
|---|---|---|---|---|---|
| NQ hourly | 450 | 450 | +0.227R | +0.194R | 0.27 |
| NQ 5m | 450 | — | — | — | 0.72 |
| Gold 5m | 360 | +0.019R | **+0.063R** | | **0.733** |

On gold, **noise beat the real data**. Searching 450 strategies and keeping the winner is a *maximum
of 450 random variables*; it is positive even when nothing works. Without the null test, a PF 1.42
combo would have been reported as a strategy.

ORB was not found by a grid search. It was built from a published specification and then tested,
which is the only reason it survived.

## Data

All free, all reproducible, fidelity **measured** before use via `research/fetch_data.py`:

| Source | Trades as | 5m return corr | Bar-range ratio |
|---|---|---|---|
| `IDX_AMERICA_E_NQ_100` | NQ / MNQ | **0.9840** | 0.977 |
| `FX_METALS_XAU_USD` | GC / MGC | 0.9835 | 0.996 |
| `FX_MAJORS_GBP_USD` | 6B | 0.9679 | 1.140 |
| `US_TECH_US_USD` | — | **0.0077** | 0.000 ← trap, a $72 stock |

```bash
.venv/bin/python research/fetch_data.py nq 2019 2026
```

## Layout

```
strategies/     Pine Script signal logic
quantconnect/   LEAN ports — multi-year IS/OOS backtests on MNQ continuous contracts
execution/      IBKR paper-trading bot (paper-only by construction) + forward replay
ninjatrader/    NinjaScript port for free sim paper trading (Windows)
research/       Data fetcher, strategy search with null test, prop-account Monte Carlo, MATH.md
backtests/      One file per run, never overwritten — including the corrections
```

One strategy file feeds every stage, so backtest, replay and live bot cannot drift apart.

## Pipeline

1. **Fetch and verify fidelity** — `fetch_data.py`, measured against the real futures
2. **Forward replay** — ~60 days of free data, cheapest kill test
3. **IS/OOS** — tune on the first 70% only, run the rest once, untouched
4. **Record in `backtests/`** including the failures and the corrections
5. **Paper trade** 4–8 weeks — only for strategies that cleared step 3
6. **Live** — nothing has reached this step

## Safety

The paper bot cannot place a real order by misconfiguration:

- Refuses any IBKR port that isn't paper (7497/4002), and any account not prefixed `DU`
- Stop and target submitted as an IB bracket attached to the entry, so a crashed process leaves the
  position protected at the broker
- Daily loss limit, max trades per day, one position at a time, session window, EOD flatten
- Kill switch that cancels, flattens and blocks re-entry until restart
- 27 offline tests covering signal logic, sizing and every risk rule

## Quality bar

- [ ] Commission and slippage modelled
- [ ] **Data fidelity measured against the real contract before the study**
- [ ] Sample > 100 trades
- [ ] Out-of-sample run once, untouched
- [ ] **Confidence intervals clustered by session, not by trade**
- [ ] If selected from a search: beats a block-bootstrap null at p < 0.05 — *and note what that bar
      actually is on a high-cost instrument*
- [ ] No single trade contributes > 20% of net profit

## Strategy inventory

| File | Concept | Status |
|---|---|---|
| `ORB_MNQ.pine` | Opening range breakout, long only, 0.5:1 | **Probably real** — +0.0297R OOS, 87.5% likely positive. Not paper traded. |
| `CBE_v1.pine` | Fade shrinking candle bodies | **Retired** (PF 0.80 OOS) |
| `PB_StupidSimple_v1.pine` | ICT HTF FVG + 5m IFVG | **Too few trades to judge** (~6/yr) |
| `htf_bias_strategy.pine` | 4H bias + 15m breakout | **Broken** — compares a bar's close to its own high. See `AUDIT.md` |

## The open question

ORB has never been paper traded. Its edge is **+0.03R**, and this repo's own measurement says
**±0.6R of exit noise costs 6 points of pass rate**. An edge that thin has very little room before
real fills erase it.

Every remaining uncertainty — whether 2026 is decay or noise, whether simulated fills survive a live
book — is answered by forward data and by nothing else. More history will not settle either.

## Notes

Not investment advice. The positive expectancy here comes from the convex payoff structure of a prop
evaluation, not from a large or reliable trading edge. Code is provided as a record of method,
including the parts where the method caught its own errors.
