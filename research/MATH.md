# The maths behind the algorithms

Everything in `research/` and `execution/ibkr_paper/`, written out. Notation: `c_t, o_t, h_t, l_t`
are the close/open/high/low of bar `t`; all money is USD; all prices are index points.

---

## 1. Units: points, dollars, and R

MNQ has a tick of **0.25 points** and a multiplier of **$2 per point**, so one tick = $0.50.

Costs are converted to points so they can be subtracted inside the price domain:

```
commission_pts = 0.62 $/contract/side ÷ 2 $/point = 0.31 points per side
                                                  = 0.62 points round trip
slippage_pts   = 1 tick = 0.25 points per side
```

**R-multiple.** With entry `E`, stop `S`, exit `X` and direction `d ∈ {+1, −1}`:

```
risk      = |E − S|                        (points)
pnl_pts   = d·(X − E) − 2·commission_pts   (slippage is already inside E and X)
R         = pnl_pts / risk
```

R makes trades comparable across volatility regimes: a 1R loss costs the same fraction of equity
whether the stop was 20 points or 90.

**Position size.** Risking a fraction `f` of equity `V` with stop distance `s` points:

```
qty = min( qty_max , floor( f·V / (s · multiplier) ) )
```

The `floor` matters on small accounts: at V = $50,000, f = 1% and s = 120 points,
`f·V / (s·2) = 500/240 = 2.08 → 2 contracts`, so realised risk is $480, not $500.

---

## 2. Indicators

**True range and Wilder ATR** (`rma` is Wilder's smoothing, equivalent to an EMA with α = 1/n):

```
TR_t  = max( h_t − l_t , |h_t − c_{t−1}| , |l_t − c_{t−1}| )

ATR_n = (1/n)·Σ_{i=1..n} TR_i                        (seed)
ATR_t = ( ATR_{t−1}·(n−1) + TR_t ) / n               (recursion)
```

**EMA** with α = 2/(n+1):  `EMA_t = α·c_t + (1−α)·EMA_{t−1}`

**RSI(n)**, Wilder-smoothed. With `Δ_t = c_t − c_{t−1}`:

```
U_t = max(Δ_t, 0),  D_t = max(−Δ_t, 0)
RS_t = rma(U, n)_t / rma(D, n)_t
RSI_t = 100 − 100/(1 + RS_t)
```

**Donchian(n):** `upper_t = max(h_{t−n..t−1})`, `lower_t = min(l_{t−n..t−1})` — the window
**excludes** bar `t`, otherwise the breakout test `c_t > upper_t` could never fire.

**Bollinger(n, k):** `mid_t = SMA(c, n)_t`, `σ_t = stdev(c_{t−n+1..t})`, bands `mid_t ± k·σ_t`.

**MACD:** `m_t = EMA(c,12)_t − EMA(c,26)_t`, signal `s_t = EMA(m,9)_t`, cross when
`m_t > s_t ∧ m_{t−1} ≤ s_{t−1}`.

---

## 3. Trade simulation (`search.py`, `forward_replay.py`)

Signals are evaluated on **closed** bars; the fill happens on the **next** bar's open. This is the
single most important anti-look-ahead rule — using `c_t` to enter at `c_t` inflates every result.

```
entry:   E = o_{t+1} + d·slippage_pts
stop:    S = E − d·(ATR_t · m_sl)
target:  T = E + d·(ATR_t · m_tp)
```

Exit resolution inside bar `t`, for a long (short is symmetric):

```
if l_t ≤ S:        X = min(o_t, S) − slippage_pts     # gap-through fills at the open
elif h_t ≥ T:      X = T                              # resting limit, no slippage
elif day ends:     X = c_t − d·slippage_pts
```

**Stop-first rule.** If both `l_t ≤ S` and `h_t ≥ T` within the same bar, the stop is assumed to
have hit first. Bar data cannot tell us the order, and assuming the target would bias results
upward. With a 1:2 bracket this makes the simulation pessimistic by construction.

**Statistics** over the resulting R-vector `r_1..r_N`:

```
win rate      WR = #{r_i > 0} / N
profit factor PF = Σ_{r_i>0} r_i / |Σ_{r_i≤0} r_i|
expectancy    E[R] = (1/N)·Σ r_i = WR·avg_win − (1−WR)·avg_loss
equity curve  eq_k = Σ_{i≤k} r_i
max drawdown  MDD = max_k ( max_{j≤k} eq_j − eq_k )        (in R)
```

**Break-even win rate** for a payoff ratio `b = avg_win / avg_loss`:

```
WR* = 1 / (1 + b)
```

CBE measured `b ≈ 1.46/1.01 = 1.45`, so `WR* ≈ 40.9%`. It won 39.5% — just below the line, which
is exactly how a PF slightly under 1 shows up.

---

## 4. The null test: why a backtest winner isn't evidence

Searching `K` strategies and keeping the best is a **maximum of K random variables**. Even with no
edge anywhere, that maximum is positive and grows with K. If each combo's expectancy estimate is
roughly `N(0, σ²/n)`, the expected best of K independent draws is approximately

```
E[max of K] ≈ (σ/√n) · √(2·ln K)
```

For K = 450 and the hourly sample, √(2·ln 450) ≈ 3.5, so the best combo sits ~3.5 standard errors
above zero **by construction**. Reporting that as "PF 1.42" would be meaningless.

Instead of trusting that approximation (the combos aren't independent — they share triggers and
data), `search.py` measures the null empirically.

**Block bootstrap.** Let `ρ_t = ln(c_t / c_{t−1})`. Draw index blocks of length `L = 24` bars
uniformly with replacement, concatenate to length T, and rebuild a synthetic path:

```
c*_k = c_0 · exp( Σ_{j≤k} ρ_{idx(j)} )
scale_k = c*_k / c_{idx(k)}
o*_k = o_{idx(k)}·scale_k      (same for h*, l*)
```

Blocks (not individual returns) preserve volatility clustering and short-horizon autocorrelation,
so the synthetic series is as "tradeable-looking" as the real one, but any structure the strategies
could exploit across block boundaries is destroyed.

**The test.** Run the entire grid on each of `B` synthetic paths, record `M*_b = max_k E[R]_k`.
With `M` the best on real data:

```
p = #{ b : M*_b ≥ M } / B
```

This is a grid-level (family-wise) test — the multiple-comparison correction is built in, because
the null statistic is itself the maximum over the same 450 combos. It's the permutation-test
version of White's Reality Check.

**Measured, 2026-10-07:** `M = +0.227R`, `mean(M*) = +0.194R`, `max(M*) = +0.330R`, **p = 0.27**.
Nothing found.

---

## 5. Prop account as a structured product (`prop_mc.py`)

### 5.1 Payoff

Let `F` be the evaluation fee, `A` the activation fee, `π` the trader's split, and `P` the payouts
received if funded. The per-attempt payoff is

```
payoff = −F                      if the challenge fails
       = −F − A + π·(profits)    if it passes
```

Downside is capped at `F` (+`A`), upside is not. That asymmetry is the whole thesis: the account is
a **call option on the strategy** bought for `F`, so the strategy does not need positive EV — the
option can still be worth more than its premium.

### 5.2 The simulated process

Trades are drawn i.i.d. from the measured R-pool, scaled by the risk fraction `f` of the
**starting** balance (fixed-fractional on the initial account, which is how prop rules are written):

```
Δ_i = R_i · f · V_0
equity_i = equity_{i−1} + Δ_i
peak_i   = max(peak_{i−1}, equity_i)
```

Failure conditions, checked after every trade:

```
trailing drawdown:  peak_i − equity_i ≥ D         (futures-style)
static drawdown:    −equity_i ≥ D                 (CFD-style)
daily loss:         Σ_{i in day} Δ_i ≤ −D_day
```

Pass condition, checked at the end of each day:

```
equity_i ≥ G  (profit target)  ∧  days_traded ≥ d_min
```

### 5.3 Why EV peaks at an interior risk

Pass probability is a **ruin problem**: starting at 0, reach `+G` before losing `D`. For a random
walk with step `±f·V_0` and up-probability `p` (`q = 1−p`), the classical gambler's ruin result is

```
P(hit +a before −b) = (1 − (q/p)^b) / (1 − (q/p)^(a+b))        for p ≠ q
                    = b / (a + b)                              for p = q
```

with `a = G/(f·V_0)` and `b = D/(f·V_0)` steps. Two opposing effects follow:

- **f too small** → `a` is huge, the target is unreachable before the time limit (and for p < 1/2
  the negative drift compounds over many steps). Pass rate → 0.
- **f too large** → `b` is only a few steps, so ordinary variance ends the attempt. At f = 5%,
  `D = $2,000` and `V_0 = $50,000` give `b = 0.8` steps: a single losing trade can breach.

The maximum sits where `a` and `b` are both small integers — measured at **f ≈ 0.75%**, where
`a = 8` and `b = 5.3` steps. This is why the risk setting matters more than the edge over the
range tested.

### 5.4 Net EV

With `p̂` the simulated pass rate and `Ê[P]` the simulated expected payout from the funded phase:

```
EV(f) = p̂(f) · ( Ê[P | passed, f] − A ) − F
f* = argmax_f EV(f)
```

Monte Carlo error on the pass rate with `N = 20,000` paths:

```
SE(p̂) = √( p̂(1−p̂)/N ) ≈ 0.3 percentage points at p̂ ≈ 0.2
```

so EV differences smaller than roughly ±$10 are noise.

**Measured, 50k futures evaluation** (G = $3,000, D = $2,000 trailing, F+A = $314, π = 0.9):

| true edge | f* | pass rate | EV |
|---|---|---|---|
| −0.20R | 1.50% | 6.1% | −$110 |
| −0.10R | 0.75% | 14.4% | −$41 |
| −0.02R | 0.75% | 22.1% | +$119 |
| 0.00R | 0.75% | 24.3% | +$180 |
| +0.05R | 0.75% | 30.2% | +$373 |

Linear interpolation puts the **break-even edge at ≈ −0.075R per trade**.

### 5.5 The binding constraint: sample size

To act on that threshold you must know which side of it your strategy sits on. For a mean estimate
with standard deviation `σ` in R, the trades needed to resolve a difference `Δ` at 95% confidence:

```
n = ( z_{0.975} · σ / Δ )² = (1.96 σ / Δ)²
```

With the measured `σ ≈ 1.4R` on 1:2 bracket trades:

| Δ (edge to resolve) | trades needed |
|---|---|
| 0.05R | ~3,000 |
| **0.075R** (the break-even line) | **~1,340** |
| 0.10R | ~750 |

Our samples: CBE ≈ 1,500 trades (enough — and it measured −0.15R, clearly below the line);
the search winners 154–320 trades (95% CI ≈ ±0.15R, which spans the entire decision);
PB 46 trades (CI ≈ ±0.4R, meaningless).

**Conclusion:** the prop-convexity play is a sample-size problem before it is a strategy problem.
A simple high-frequency rule set with 1,500+ measured trades is worth more here than a selective
model with a better-looking backtest.

---

## 6. Known model limitations

1. Trades are resampled i.i.d.; real losing streaks cluster, so pass rates are optimistic.
2. Consistency rules, scaling plans and payout waiting periods are not modelled — all reduce EV.
3. The funded phase assumes profits are withdrawn at a fixed threshold and the account resets to
   baseline; real payout cycles are slower.
4. `σ = 1.4R` is measured on our own bracket trades; a strategy with different exits needs its own σ
   before the sample-size table applies.
5. Hourly search data covers 2024-05 → 2026-10 only (free Yahoo limit). Any survivor must be
   validated on QuantConnect 2019–2023, which the search has never seen.
