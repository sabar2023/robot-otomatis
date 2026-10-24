import csv
import io
import threading
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import database as db
from agents.orchestrator import MasterOrchestrator
from cloud_sync import sync
from execution import SUPPORTED_EXCHANGES, router
from market import HybridMarket, PAIRS

app = FastAPI(title="BrandBisnis Robot Trading API", version="4.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db.init_db()
market = HybridMarket()
orchestrator = MasterOrchestrator(market)
CYCLE_SECONDS = 15
_engine_lock = threading.Lock()


def engine_loop():
    while True:
        interval = CYCLE_SECONDS
        try:
            interval = db.get_secrets().get("cycle_seconds") or CYCLE_SECONDS
            with _engine_lock:
                if orchestrator.running:
                    orchestrator.cycle()
        except Exception as exc:
            db.insert_agent_log("ENGINE", f"Cycle error: {exc}", "ERROR")
        time.sleep(max(5, int(interval)))


threading.Thread(target=engine_loop, daemon=True).start()


class ConfigUpdate(BaseModel):
    execution_mode: str | None = None
    global_kill_switch: bool | None = None
    max_daily_drawdown: float | None = None
    exchange_id: str | None = None
    cycle_seconds: int | None = None
    worker_url: str | None = None
    worker_token: str | None = None
    cloud_sync_enabled: bool | None = None
    api_key: str | None = None
    api_secret: str | None = None


class EngineControl(BaseModel):
    running: bool


@app.get("/api/health")
def health():
    return {"status": "ok", "product": "Robot Trading BrandBisnis", "ts": db.utcnow()}


@app.get("/api/overview")
def overview():
    config = db.get_config()
    account = db.get_account()
    start = account["daily_start_equity"] or account["starting_balance"]
    daily_pnl = ((account["equity"] - start) / start) * 100 if start else 0
    total_pnl = ((account["equity"] - account["starting_balance"]) / account["starting_balance"]) * 100
    positions = db.open_positions()
    logs = db.list_trade_logs(8)
    return {
        "config": config,
        "account": {
            **account,
            "daily_pnl_pct": round(daily_pnl, 3),
            "total_pnl_pct": round(total_pnl, 3),
            "open_positions": len(positions),
        },
        "engine": {
            "running": orchestrator.running,
            "last_cycle": orchestrator.last_cycle,
            "interval_sec": config.get("cycle_seconds") or CYCLE_SECONDS,
        },
        "market": market.info(),
        "cloud": sync.status(),
        "tickers": market.ticker(),
        "recent_logs": logs,
    }


@app.get("/api/config")
def get_config():
    return db.get_config()


@app.get("/api/exchanges")
def exchanges():
    return {"supported": SUPPORTED_EXCHANGES, "status": router.connection_status()}


@app.get("/api/cloud/status")
def cloud_status():
    return {"sync": sync.status(), "config": {k: v for k, v in db.get_secrets().items() if k not in ("api_key", "api_secret", "worker_token")}}


@app.post("/api/config")
def set_config(body: ConfigUpdate):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    if "execution_mode" in payload and payload["execution_mode"] not in ("PAPER", "LIVE"):
        raise HTTPException(400, "execution_mode must be PAPER or LIVE")
    if "exchange_id" in payload and payload["exchange_id"] not in SUPPORTED_EXCHANGES:
        raise HTTPException(400, f"exchange_id must be one of {SUPPORTED_EXCHANGES}")
    if payload.get("execution_mode") == "LIVE":
        secrets = db.get_secrets()
        if not (secrets.get("api_key") and secrets.get("api_secret")):
            db.insert_agent_log(
                "RISK",
                "Mode LIVE aktif tanpa API key. Order Live akan DITOLAK sampai kredensial exchange diisi.",
                "WARN",
            )
    updated = db.update_config(**payload)
    db.insert_agent_log("ORCHESTRATOR", f"Config updated: {sorted(payload.keys())}")
    if db.get_secrets().get("cloud_sync_enabled"):
        sync.push_config()
    return updated


@app.post("/api/engine")
def set_engine(body: EngineControl):
    orchestrator.running = body.running
    db.insert_agent_log("ENGINE", "Engine started" if body.running else "Engine paused")
    return {"running": orchestrator.running}


@app.post("/api/cycle")
def force_cycle():
    with _engine_lock:
        signals = orchestrator.cycle()
    return {"ok": True, "signals": signals, "last_cycle": orchestrator.last_cycle}


@app.get("/api/market")
def market_data(pair: str = "BTC/USDT"):
    if pair not in PAIRS:
        raise HTTPException(400, "unknown pair")
    return {"pair": pair, "candles": market.ohlcv(pair), "ticker": market.ticker().get(pair)}


@app.get("/api/tickers")
def tickers():
    return market.ticker()


@app.get("/api/positions")
def positions():
    rows = db.open_positions()
    tickers = market.ticker()
    for row in rows:
        t = tickers.get(row["asset_pair"])
        price = t["price"] if t else row["avg_price"]
        row["mark_price"] = price
        row["unrealized_pnl"] = (price - row["avg_price"]) * row["quantity"]
        row["unrealized_pnl_pct"] = ((price - row["avg_price"]) / row["avg_price"]) * 100 if row["avg_price"] else 0
    return rows


@app.get("/api/trades")
def trades(limit: int = 80):
    return db.list_trade_logs(limit)


@app.get("/api/logs")
def logs(limit: int = 120):
    return db.list_agent_logs(limit)


@app.get("/api/equity")
def equity():
    return db.list_equity(120)


@app.get("/api/signals")
def signals():
    return {"last_cycle": orchestrator.last_cycle, "signals": orchestrator.last_signals}


@app.get("/api/export.csv")
def export_csv():
    rows = db.list_trade_logs(500)
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["log_id", "timestamp", "asset_pair", "action", "ai_reason", "mode", "profit_loss", "price", "quantity", "agent", "score"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    content = buf.getvalue()
    filename = f"brandbisnis-trades-{datetime.now(timezone.utc).strftime('%Y%m')}.csv"

    if db.get_secrets().get("cloud_sync_enabled"):
        sync.backup_csv(filename, content)

    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/api/export/r2")
def export_to_r2():
    rows = db.list_trade_logs(500)
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["log_id", "timestamp", "asset_pair", "action", "ai_reason", "mode", "profit_loss", "price", "quantity", "agent", "score"],
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    filename = f"brandbisnis-trades-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.csv"
    ok = sync.backup_csv(filename, buf.getvalue())
    if not ok:
        raise HTTPException(400, "Backup R2 gagal. Periksa worker_url, token, dan cloud sync.")
    return {"ok": True, "filename": filename}
