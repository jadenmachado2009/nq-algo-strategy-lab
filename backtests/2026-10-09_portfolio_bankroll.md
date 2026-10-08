# Portfolio / bankroll analysis — ORB on Topstep 50K — 2026-10-09

**Verdict:** EV-positive, median-negative. A lottery with a favourable price, not an income.

## Inputs
| | |
|---|---|
| Strategy | ORB long-only, 5 opening windows, 0.75% risk (`research/orb.py`) |
| Measured | 7,063 trades, 65.4% WR, +0.022R, null test p = 0.00 |
| Firm | Topstep 50K, $39/month (with DLL discount) + $149 activation on passing |
| Challenge | 39.2% pass; median 7 days to pass, 5 days to fail; 96% resolved by day 15 |
| Funded | 1 year at 0.75% risk: mean payout $1,598, **median $0, 51% never pay out**, p90 $4,350 |

## Sequential attempts (stop after the first pass)

| Attempts | Max outlay | Avg spent | P(≥1 pass) | P(profit) | Median | Mean | p10 | p90 |
|---|---|---|---|---|---|---|---|---|
| 1 | $188 | $97 | 39.1% | 19.0% | −$39 | +$525 | −$188 | +$2,805 |
| 2 | $227 | $156 | 62.9% | 30.6% | −$78 | +$843 | −$227 | +$3,556 |
| 3 | $266 | $193 | 77.6% | 37.7% | −$117 | +$1,045 | −$227 | +$3,833 |
| **5** | **$344** | **$228** | **91.7%** | **44.6%** | **−$188** | **+$1,235** | −$266 | +$4,023 |
| 8 | $461 | $244 | 98.1% | 47.8% | −$188 | +$1,327 | −$305 | +$4,103 |
| 10 | $539 | $247 | 99.3% | 48.4% | −$188 | +$1,344 | −$305 | +$4,121 |

Five attempts captures 92% of the available pass probability; going to ten adds ~$100 of expected
value for another ~$200 of exposure.

## Why P(profit) is so much lower than P(pass)

Passing is not being paid. Half of funded accounts breach their drawdown before producing the five
$150+ winning days that unlock a payout. So:

```
P(pass at least once, 5 attempts)  91.7%
P(actually end up in profit)       44.6%
```

The entire positive expectancy sits in the ~25% of cases that reach roughly +$4,000.

## Correlation warning
Copied parallel accounts are perfectly correlated — same trades, same size, same outcome. Three
copies cost 3x and still pass 39.2% of the time. Independence requires sequential attempts, or
genuinely different strategies/markets per account.

## Unmodelled, all EV-reducing
Funded scaling plan, payout waiting periods and caps, platform fees, reset pricing, execution worse
than one tick of slippage, and any change to Topstep's terms.

## Next action
Paper trade the exact spec for 4–8 weeks and compare realised R against +0.022R. The model's weakest
assumption is not the maths — it is that live execution reproduces the simulated fills.
