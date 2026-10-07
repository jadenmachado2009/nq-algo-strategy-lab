"""Settings, read from environment / .env. Paper-only by construction."""

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

PAPER_PORTS = {7497, 4002}   # TWS paper, IB Gateway paper. Live ports (7496, 4001) are refused.


def _load_dotenv():
    env = Path(__file__).with_name(".env")
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    client_id: int

    symbol: str
    exchange: str
    tick_size: float
    roll_days_before_expiry: int
    bar_minutes: int

    seq_len: int
    min_body_atr: float
    atr_len: int
    atr_sl: float
    atr_tp: float

    risk_pct: float
    max_contracts: int
    max_daily_loss: float
    max_trades_per_day: int

    session_start: time
    session_end: time
    flatten_at: time

    webhook_secret: str
    signal_source: str   # "local" (bot computes CBE) or "webhook" (TradingView alerts)


def load() -> Settings:
    _load_dotenv()
    e = os.environ.get
    s = Settings(
        host=e("IB_HOST", "127.0.0.1"),
        port=int(e("IB_PORT", "7497")),
        client_id=int(e("IB_CLIENT_ID", "17")),
        symbol=e("SYMBOL", "MNQ"),
        exchange=e("EXCHANGE", "CME"),
        tick_size=float(e("TICK_SIZE", "0.25")),
        roll_days_before_expiry=int(e("ROLL_DAYS", "8")),
        bar_minutes=int(e("BAR_MINUTES", "5")),
        seq_len=int(e("SEQ_LEN", "3")),
        min_body_atr=float(e("MIN_BODY_ATR", "0.1")),
        atr_len=int(e("ATR_LEN", "14")),
        atr_sl=float(e("ATR_SL", "1.7")),
        atr_tp=float(e("ATR_TP", "2.5")),
        risk_pct=float(e("RISK_PCT", "0.01")),
        max_contracts=int(e("MAX_CONTRACTS", "5")),
        max_daily_loss=float(e("MAX_DAILY_LOSS", "1000")),
        max_trades_per_day=int(e("MAX_TRADES_PER_DAY", "4")),
        session_start=_hhmm(e("SESSION_START", "09:30")),
        session_end=_hhmm(e("SESSION_END", "11:30")),
        flatten_at=_hhmm(e("FLATTEN_AT", "15:50")),
        webhook_secret=e("WEBHOOK_SECRET", ""),
        signal_source=e("SIGNAL_SOURCE", "local"),
    )
    if s.port not in PAPER_PORTS:
        raise SystemExit(f"IB_PORT={s.port} is not a paper port {sorted(PAPER_PORTS)}. Refusing to start.")
    if s.signal_source not in {"local", "webhook"}:
        raise SystemExit("SIGNAL_SOURCE must be 'local' or 'webhook'")
    if s.signal_source == "webhook" and len(s.webhook_secret) < 16:
        raise SystemExit("WEBHOOK_SECRET must be set (16+ chars) when SIGNAL_SOURCE=webhook")
    return s
