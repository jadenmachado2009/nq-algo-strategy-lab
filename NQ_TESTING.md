# Testing CBE on NQ futures without real money

Three pieces, run in this order. All three use the same logic, instrument (MNQ, $2/pt) and risk rules, so the results can be compared.

| Step | File | Where it runs | Cost |
|---|---|---|---|
| 1. Backtest | `quantconnect/cbe_mnq.py` | QuantConnect cloud (browser) | Free |
| 2a. Paper trade | `ninjatrader/CBE_MNQ.cs` | NinjaTrader 8 Sim101 — **Windows only** | Free |
| 2b. Paper trade | `execution/ibkr_paper/` | Your Mac + IB paper account | IB account + CME data (~a few $/mo) |

Do 2a **or** 2b, not both. On a Mac, 2a needs a Windows VM (Parallels/UTM) or a Windows PC.

**Gate:** don't start step 2 until step 1 passes the README quality bar **out-of-sample**. If the out-of-sample run fails, stop there.

---

## 0. Quick forward replay (free, 2 minutes)

`execution/ibkr_paper/forward_replay.py` runs the bot's exact code bar-by-bar over the last ~60 days of free Yahoo NQ 5m data (all after the QC out-of-sample window). Use it for a fast kill/keep check before spending weeks on paper trading:

```bash
cd execution/ibkr_paper && .venv/bin/pip install yfinance && .venv/bin/python forward_replay.py
```

First run (2026-09-17): **rejected**, PF 0.89 over 38 trades. See `backtests/2026-09-17_CBE_MNQ_forward-replay.md`.

**QuantConnect IS + OOS (2026-09-17): rejected.** PF 0.90 in-sample (931 trades), 0.80 out-of-sample (528 trades), drawdown ~50%. CBE is retired on NQ — see `backtests/2026-09-17_CBE_MNQ_quantconnect_IS-OOS.md`. The rest of this guide stays valid for the next strategy.

## 1. QuantConnect backtest

1. quantconnect.com → sign up → **Create project** (Python).
2. Paste `quantconnect/cbe_mnq.py` into `main.py`.
3. Run with `PERIOD = IN_SAMPLE`. Tune only here, and not much: SEQ_LEN, ATR_SL, ATR_TP.
4. Set `PERIOD = OUT_OF_SAMPLE`, change nothing else, and run again.
5. Record both runs in `backtests/` using `TEMPLATE.md`. Read the summary block at the bottom of the Logs tab.
6. Robustness: rerun in-sample with ATR_SL at 1.4 / 2.0 and ATR_TP at 2.0 / 3.0. If PF collapses, the edge is fragile.

Costs used: $0.62/contract/side commission and 1 tick/side slippage. Contracts roll by open interest; any position is flattened at the roll and at 15:50 NY.

## 2a. NinjaTrader sim (free)

1. Download NinjaTrader 8 → sign up (free), then connect to the free sim data feed.
2. **New → NinjaScript Editor → Strategies**. Right-click → New Strategy named `CBE_MNQ`, paste the file in, and press **F5**.
3. First run it through the **Strategy Analyzer** (the current MNQ contract, e.g. MNQ 12-26, 5 Minute, include commission) and check it roughly matches QuantConnect.
4. Chart MNQ at 5 min → Strategies → add `CBE_MNQ` → **Account: Sim101** → Enabled.
5. Leave it running during the NY morning (21:30–23:30 Singapore time, or 22:30–00:30 when US daylight saving ends).

## 2b. IBKR paper bot (Mac, Python)

**Prerequisites:**
- An IBKR account with **paper trading** enabled.
- A CME real-time data subscription on the live account, shared with paper (Settings → Paper Trading Account → share market data). Without it you get delayed data or no bars.
- TWS or IB Gateway logged into the **paper** account, with API enabled on port 7497 (Gateway: 4002). In TWS: Settings → API → Enable ActiveX and Socket Clients.

**Run it:**
```bash
cd execution/ibkr_paper
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env
.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8000
```

- `GET  http://127.0.0.1:8000/status` shows position, P&L, trades today and recent events.
- `POST http://127.0.0.1:8000/kill` cancels everything, flattens and blocks new entries until restart.
- `.venv/bin/python -m unittest discover -s tests` runs the offline tests for signal, sizing and risk rules.

**Safety built in:**
- It refuses live ports (7496/4001) and any account that isn't a paper `DU…` account.
- Stop and target go in as an IB bracket, so they stay protected at IB even if the Mac sleeps.
- Daily loss limit (default $1,000) → flatten and halt for the day.
- Max 4 trades/day, 1 position at a time, entries 09:30–11:30 NY only, flatten at 15:50 NY.
- Reconnects automatically with backoff, and rolls to the next contract 8 days before expiry (only when flat).

**TradingView instead of local signals:** set `SIGNAL_SOURCE=webhook` and a `WEBHOOK_SECRET`. The alert body is `{"secret":"…","action":"long|short|flat"}`. This needs a paid TradingView plan and a public HTTPS URL (e.g. a tunnel).

---

## Judging the paper run

Run for at least **4–8 weeks / 50+ trades**, then compare to the out-of-sample backtest:

| | Backtest OOS | Paper | Acceptable gap |
|---|---|---|---|
| Win rate | | | within ~5 pts |
| Avg trade ($) | | | within ~30% |
| Profit factor | | | within ~30% |
| Trades/week | | | within ~25% |

A big gap in trade count means the signal code differs between platforms. A big gap in average trade with similar counts means fills and slippage are worse than modelled.
