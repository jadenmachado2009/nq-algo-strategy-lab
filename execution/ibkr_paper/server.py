"""FastAPI wrapper: runs the bot and exposes status / kill switch / TradingView webhook.

    uvicorn server:app --host 127.0.0.1 --port 8000
"""

import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

import config
from bot import CBEBot

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
settings = config.load()
bot = CBEBot(settings)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bot.start()
    yield
    await bot.stop()


app = FastAPI(title="CBE MNQ paper bot", lifespan=lifespan)


def _check(secret: str | None):
    # With no secret configured, only localhost can reach the server (see bind address).
    if settings.webhook_secret and not hmac.compare_digest(secret or "", settings.webhook_secret):
        raise HTTPException(status_code=401, detail="bad secret")


class Alert(BaseModel):
    secret: str
    action: str   # "long" | "short" | "flat"


@app.get("/status")
async def status():
    return bot.status()


@app.post("/kill")
async def kill(x_secret: str | None = Header(default=None)):
    _check(x_secret)
    return {"result": await bot.kill()}


@app.post("/webhook")
async def webhook(alert: Alert):
    if settings.signal_source != "webhook":
        raise HTTPException(status_code=409, detail="SIGNAL_SOURCE is 'local'; webhooks are ignored")
    _check(alert.secret)
    action = alert.action.lower()
    if action == "flat":
        return {"result": await bot.flatten("webhook")}
    if action not in ("long", "short"):
        raise HTTPException(status_code=422, detail="action must be long, short or flat")
    return {"result": await bot.enter(1 if action == "long" else -1, source="webhook")}
