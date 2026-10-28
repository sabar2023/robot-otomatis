import logging

import ccxt

import config
import market_data

log = logging.getLogger("brandbisnis_vst")


def build_trading_exchange(api_key, secret_key):
    if not api_key or not secret_key:
        raise RuntimeError("API key / secret key BingX kosong - mode live tidak dapat berjalan.")
    exchange = ccxt.bingx(
        {
            "apiKey": api_key,
            "secret": secret_key,
            "enableRateLimit": True,
            "timeout": 30000,
            "options": {"defaultType": "swap"},
        }
    )
    exchange.set_sandbox_mode(config.EXEC_MODE != "real")
    return exchange


def execution_env_label():
    return "BingX USDT (akun real)" if config.EXEC_MODE == "real" else "BingX VST (demo)"


def free_balance(exchange):
    last_error = None
    for params in ({"type": "swap"}, None):
        try:
            balance = exchange.fetch_balance(params) if params else exchange.fetch_balance()
        except Exception as exc:
            last_error = exc
            continue
        coin = balance.get(config.MARGIN_COIN)
        if isinstance(coin, dict) and coin.get("free") is not None:
            return float(coin["free"] or 0.0)
        nested = balance.get("swap") or {}
        coin = nested.get(config.MARGIN_COIN)
        if isinstance(coin, dict) and coin.get("free") is not None:
            return float(coin["free"] or 0.0)
        total = balance.get("total") or {}
        if config.MARGIN_COIN in total and total[config.MARGIN_COIN] is not None:
            return float(total[config.MARGIN_COIN] or 0.0)
    if last_error:
        log.warning("fetch_balance gagal: %s", str(last_error).splitlines()[0][:120])
    return 0.0


def open_positions(exchange, symbol):
    positions = exchange.fetch_positions([symbol])
    return [
        p
        for p in positions
        if p["symbol"] == symbol and float(p.get("contracts") or 0) > 0
    ]


def compute_size(exchange, symbol, entry, levels):
    free = free_balance(exchange)
    if free <= 0:
        raise RuntimeError(f"Saldo free {config.MARGIN_COIN} = 0 - tidak ada margin untuk entry.")
    margin_used = free * levels["margin_pct"] / 100.0
    notional = margin_used * levels["leverage"]
    amount = float(exchange.amount_to_precision(symbol, notional / entry))
    limits = exchange.market(symbol)["limits"]
    min_amount = float(limits["amount"].get("min") or 0)
    min_cost = float(limits["cost"].get("min") or 0)
    if min_amount and amount < min_amount:
        raise RuntimeError(f"Ukuran order {amount} di bawah minimum Bursa {min_amount} (saldo {free:,.2f} {config.MARGIN_COIN}).")
    if min_cost and notional < min_cost:
        raise RuntimeError(f"Notional order {notional:,.2f} di bawah minimum Bursa {min_cost:,.2f} USDT.")
    if notional < config.MIN_ORDER_USDT:
        raise RuntimeError(f"Notional order {notional:,.2f} di bawah minimum {config.MIN_ORDER_USDT:g} USDT.")
    return amount, margin_used, notional


def prepare_order(exchange, symbol, levels, amount):
    side = "buy" if levels["direction"] == "LONG" else "sell"
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
    return side, params


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


def _set_isolated_margin(exchange, symbol):
    try:
        exchange.set_margin_mode("isolated", symbol)
        log.info("Margin mode isolated terpasang untuk %s.", symbol)
        return
    except Exception:
        pass
    try:
        exchange.set_cross_margin(False, symbol)
        log.info("Margin mode isolated terpasang (via set_cross_margin) untuk %s.", symbol)
    except Exception as exc:
        log.info("Margin mode isolated tidak dapat diset - lanjut margin mode default: %s", str(exc).splitlines()[0][:120])


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


def execute(levels, live, data_source_id=None, symbol=None, credentials=None):
    symbol = symbol or config.SYMBOL
    if not live:
        exchange = _public_exchange_with_markets(data_source_id)
        notional = config.SIMULATED_NOTIONAL_USDT
        margin_used = notional / levels["leverage"]
        amount = float(exchange.amount_to_precision(symbol, notional / levels["entry"]))
        side, _ = prepare_order(exchange, symbol, levels, amount)
        return {
            "mode": "dry-run",
            "executed": False,
            "side": side,
            "amount": amount,
            "order_id": None,
            "margin_used": margin_used,
            "notional": notional,
            "detail": "Simulasi - tidak ada order dikirim ke bursa.",
        }

    if credentials:
        exchange = build_trading_exchange(credentials["api_key"], credentials["secret_key"])
    else:
        exchange = build_trading_exchange(config.BINGX_API_KEY, config.BINGX_SECRET_KEY)
    exchange.load_markets()
    existing = open_positions(exchange, symbol)
    if existing:
        pos = existing[0]
        return {
            "mode": "live",
            "executed": False,
            "side": str(pos.get("side")),
            "amount": float(pos.get("contracts") or 0),
            "order_id": None,
            "margin_used": None,
            "notional": None,
            "detail": f"Sudah ada posisi terbuka ({pos['side']} {pos['contracts']} x{pos.get('leverage')}x) - entry baru dilewati.",
        }

    _set_isolated_margin(exchange, symbol)
    _apply_leverage(exchange, symbol, levels["leverage"])
    amount, margin_used, notional = compute_size(exchange, symbol, levels["entry"], levels)
    side, params = prepare_order(exchange, symbol, levels, amount)
    order = _place_entry_order(exchange, symbol, side, amount, params)
    return {
        "mode": "live",
        "executed": True,
        "side": side,
        "amount": amount,
        "order_id": str(order.get("id")),
        "margin_used": margin_used,
        "notional": notional,
        "detail": f"Bracket order terisolasi terkirim, id {order.get('id')} (margin {margin_used:,.2f} {config.MARGIN_COIN}).",
    }
