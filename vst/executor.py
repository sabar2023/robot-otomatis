import logging

import ccxt

import config
import market_data

log = logging.getLogger("brandbisnis_vst")


def build_trading_exchange():
    if not config.BINGX_API_KEY or not config.BINGX_SECRET_KEY:
        raise RuntimeError("BINGX_API_KEY / BINGX_SECRET_KEY kosong - mode live tidak dapat berjalan.")
    exchange = ccxt.bingx(
        {
            "apiKey": config.BINGX_API_KEY,
            "secret": config.BINGX_SECRET_KEY,
            "enableRateLimit": True,
            "timeout": 30000,
            "options": {"defaultType": "swap"},
        }
    )
    exchange.set_sandbox_mode(True)
    return exchange


def open_positions(exchange, symbol):
    positions = exchange.fetch_positions([symbol])
    return [
        p
        for p in positions
        if p["symbol"] == symbol and float(p.get("contracts") or 0) > 0
    ]


def prepare_order(exchange, levels):
    symbol = config.SYMBOL
    side = "buy" if levels["direction"] == "LONG" else "sell"
    amount = float(exchange.amount_to_precision(symbol, config.POSITION_SIZE_USDT / levels["entry"]))
    limits = exchange.market(symbol)["limits"]
    min_amount = float(limits["amount"].get("min") or 0)
    min_cost = float(limits["cost"].get("min") or 0)
    if min_amount and amount < min_amount:
        raise RuntimeError(f"Ukuran order {amount} di bawah minimum {min_amount} kontrak.")
    if min_cost and amount * levels["entry"] < min_cost:
        raise RuntimeError("Notional order di bawah minimum bursa.")
    params = {
        "marginCoin": config.MARGIN_COIN,
        "stopLoss": {
            "triggerPrice": float(exchange.price_to_precision(symbol, levels["stop_loss"])),
            "type": "STOP_MARKET",
        },
        "takeProfit": {
            "triggerPrice": float(exchange.price_to_precision(symbol, levels["take_profit"])),
            "type": "TAKE_PROFIT_MARKET",
        },
    }
    return side, amount, params


def _public_exchange_with_markets(preferred_id):
    candidate_ids = [preferred_id, "bingx"] + [e for e in config.DATA_EXCHANGES if e not in (preferred_id, "bingx")]
    last_error = None
    seen = set()
    for cid in candidate_ids:
        if not cid or cid in seen or cid not in ccxt.exchanges:
            continue
        seen.add(cid)
        try:
            exchange = market_data.build_exchange(cid)
            exchange.load_markets()
            return exchange
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Gagal memuat data pasar bursa publik: {str(last_error).splitlines()[0]}")


def _apply_leverage(exchange, symbol, leverage):
    try:
        exchange.set_leverage(leverage, symbol, params={"side": "BOTH"})
        return
    except Exception as exc:
        log.info("Leverage one-way tidak diterima, mencoba mode hedge: %s", str(exc).splitlines()[0][:120])
    for side in ("LONG", "SHORT"):
        try:
            exchange.set_leverage(leverage, symbol, params={"side": side})
        except Exception as exc:
            log.warning("Set leverage %s %dx gagal: %s", side, leverage, str(exc).splitlines()[0][:120])


def _place_entry_order(exchange, symbol, side, amount, params):
    last_error = None
    for hedged in (True, False):
        attempt = dict(params)
        if hedged:
            attempt["hedged"] = True
        try:
            return exchange.create_order(symbol, "market", side, amount, None, params=attempt)
        except Exception as exc:
            last_error = exc
            text = str(exc).lower()
            if "positionside" not in text and "hedge" not in text:
                raise
    raise last_error


def execute(levels, live, data_source_id=None):
    if not live:
        exchange = _public_exchange_with_markets(data_source_id)
        side, amount, _ = prepare_order(exchange, levels)
        return {
            "mode": "dry-run",
            "executed": False,
            "side": side,
            "amount": amount,
            "order_id": None,
            "detail": "Simulasi - tidak ada order dikirim ke bursa.",
        }

    exchange = build_trading_exchange()
    exchange.load_markets()
    existing = open_positions(exchange, config.SYMBOL)
    if existing:
        pos = existing[0]
        return {
            "mode": "live",
            "executed": False,
            "side": str(pos.get("side")),
            "amount": float(pos.get("contracts") or 0),
            "order_id": None,
            "detail": f"Sudah ada posisi terbuka ({pos['side']} {pos['contracts']} x{pos.get('leverage')}x) - entry baru dilewati.",
        }

    _apply_leverage(exchange, config.SYMBOL, config.LEVERAGE)

    side, amount, params = prepare_order(exchange, levels)
    order = _place_entry_order(exchange, config.SYMBOL, side, amount, params)
    return {
        "mode": "live",
        "executed": True,
        "side": side,
        "amount": amount,
        "order_id": str(order.get("id")),
        "detail": f"Bracket order VST terkirim, id {order.get('id')}.",
    }
