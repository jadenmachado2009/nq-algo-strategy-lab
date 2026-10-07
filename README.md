# NQ Algo Strategy Lab

A testing pipeline for futures strategies on NQ/MNQ, built around one rule: **a strategy is assumed
worthless until evidence says otherwise, and the evidence has to survive a test designed to fail it.**

So far the lab has retired one strategy, failed to validate a second, and rejected its own best
search result. Those are the results, not a setback — the point of the pipeline is to produce them
cheaply, before money is involved.

---

## Results so far

| Strategy | Sample | In-sample | Out-of-sample | Verdict |
|---|---|---|---|---|
| **CBE** — fade shrinking-body runs | ~1,500 trades | PF 0.90 | **PF 0.80** | **Retired.** Loses in every window tested (2019–23, 2024–26, and a 10-week forward replay at PF 0.89). |
| **PB** — ICT FVG/IFVG model | 46 trades over 7 years | PF 0.87 | PF 1.83 | **Undecided, unusable.** ~6 trades/year. The out-of-sample 1.83 is noise at n=17, not an edge that appeared in 2024. |
| **450-combo search** | 2.4 years, hourly | best **+0.227R** | — | **Nothing found.** See below. |

### The search result is the interesting one

A bounded grid of 450 strategies (trend filter × entry trigger × session × volatility filter ×
exit) produced a top combo at +0.227R expectancy, profit factor 1.42 over 154 trades. That looks
like a discovery.

It isn't. Running the identical grid over 30 block-bootstrapped **noise** series — same volatility
clustering, no real structure — the best combo on noise averaged **+0.194R** and reached +0.330R.

```
best on REAL data       +0.227R
best on noise (mean)    +0.194R
best on noise (max)     +0.330R
p-value                  0.27     -> indistinguishable from data mining
```

Searching 450 strategies and keeping the winner is a *maximum of 450 random variables*; it is
positive even when nothing works. Without the null test, that PF 1.42 combo would have been
reported as a strategy.

### Prop-account maths: the real constraint is sample size

A prop challenge is a convex payoff — downside capped at the fee, upside uncapped — so a strategy
doesn't need to be profitable to make the account +EV. Monte Carlo over 20,000 paths per setting
(trailing drawdown, daily loss limit, minimum trading days, activation fee, funded phase):

| True edge per trade | Best risk/trade | Pass rate | Net EV per attempt |
|---|---|---|---|
| −0.20R | 1.50% | 6.1% | −$110 |
| −0.10R | 0.75% | 14.4% | −$41 |
| **−0.075R** | — | — | **break-even** |
| 0.00R | 0.75% | 24.3% | **+$180** |
| +0.05R | 0.75% | 30.2% | **+$373** |

Two findings:

1. **Risk size dominates edge.** At 5% risk the drawdown limit is 0.8 trades away — one loss ends
   the attempt regardless of how good the strategy is. The optimum sits near 0.75%.
2. **You can't tell which side of the line you're on.** Resolving −0.075R from 0 at 95% confidence
   needs **~1,340 trades** (σ ≈ 1.4R). The search winners had 154–320; PB had 46. Only CBE had
   enough — and it measured −0.15R, correctly below the line.

Full derivations, including the gambler's-ruin argument for the optimal risk fraction:
**[`research/MATH.md`](research/MATH.md)**.

---

## Layout

```
strategies/     Pine Script signal logic
quantconnect/   LEAN ports — multi-year IS/OOS backtests on MNQ continuous contracts
execution/      IBKR paper-trading bot (paper-only by construction) + forward replay
ninjatrader/    NinjaScript port for free sim paper trading (Windows)
research/       Strategy search with null test, prop-account Monte Carlo, MATH.md
backtests/      One file per run, never overwritten
```

One strategy file feeds every stage. `execution/ibkr_paper/pb_engine.py` is imported unchanged by
the QuantConnect backtest, the forward replay and the live bot, so the three cannot drift apart —
a backtest that doesn't match live behaviour is the most common way these projects lie to you.

## Pipeline

1. **Forward replay** (`research`-grade, 2 minutes, free) — replay the bot's exact logic over ~60
   days of free data. Cheapest possible kill test.
2. **QuantConnect IS/OOS** — tune on 2019–2023 only, then run 2024–2026 once, untouched.
3. **Record in `backtests/`** using `TEMPLATE.md`, including the parameters and the failures.
4. **Paper trade** 4–8 weeks on the IBKR bot — only for strategies that cleared step 2.
5. **Live** — nothing has reached this step.

Full setup instructions, including the free routes: **[`NQ_TESTING.md`](NQ_TESTING.md)**.

## Safety

The paper bot is built so that a configuration mistake cannot place a real order:

- Refuses any IBKR port that isn't paper (7497/4002), and any account not prefixed `DU`.
- Stop and target are submitted as an IB bracket attached to the entry, so a crashed process or a
  dropped connection leaves the position protected at the broker.
- Daily loss limit, max trades per day, one position at a time, session window, end-of-day flatten.
- Kill switch endpoint that cancels, flattens and blocks re-entry until restart.
- 27 offline tests (`python -m unittest discover -s tests`) covering signal logic, sizing and every
  risk rule.

## Quality bar

A strategy is validated only when all of these hold:

- [ ] Commission and slippage modelled (futures: cash per contract + 1–2 ticks)
- [ ] Sample > 100 trades — and > 1,340 if the prop-EV threshold is the decision
- [ ] Tested across trending *and* ranging regimes
- [ ] Out-of-sample run once, untouched; reject if it degrades > 30%
- [ ] No single trade contributes > 20% of net profit
- [ ] Profit factor holds when key parameters move ±20%
- [ ] If selected from a search: beats a block-bootstrap null at p < 0.05

Targets: PF > 1.5, win rate > 50%, max drawdown < 15%, expectancy > 0.3R.

## Strategy inventory

| File | Concept | Status |
|---|---|---|
| `CBE_v1.pine` | Candle body exhaustion — fade shrinking bodies | **Retired on NQ** (PF 0.80 OOS, 2026-09-17) |
| `PB_StupidSimple_v1.pine` | ICT — HTF FVG context + 5m FVG retrace + IFVG trigger | Audit bugs fixed in `pb_engine.py`; **too few trades to judge** (~6/yr) |
| `htf_bias_strategy.pine` | 4H bias + 15m breakout | **Broken** — compares a bar's close to its own high; can never trade. See `AUDIT.md` |
| `patty_swing_strategy.pine` | Swing model | Not yet audited |

## Notes

Not investment advice, and nothing here is profitable — that is the current finding. Code is
provided as a record of method.
