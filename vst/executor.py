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


def split_partial(exchange, symbol, levels, amount):
    fraction = levels.get("tp1_fraction") or 0.0
    if fraction <= 0 or not levels.get("tp1"):
        return 0.0, amount
    partial = float(exchange.amount_to_precision(symbol, amount * fraction))
    remainder = float(exchange.amount_to_precision(symbol, amount - partial))
    if partial <= 0 or remainder <= 0:
        return 0.0, amount
    return partial, remainder


def prepare_order(exchange, symbol, levels, amount):
    side = "buy" if levels["direction"] == "LONG" else "sell"
    _partial, remainder = split_partial(exchange, symbol, levels, amount)
    params = {
        "marginCoin": config.MARGIN_COIN,
        "stopLoss": {
            "triggerPrice": float(exchange.price_to_precision(symbol, levels["stop_loss"])),
            "type": "STOP_MARKET",
            "quantity": amount,
        },
        "takeProfit": {
            "triggerPrice": float(exchange.price_to_precision(symbol, levels["take_profit"])),
            "type": "TAKE_PROFIT_MARKET",
            "quantity": remainder,
        },
    }
    return side, params


def _place_tp_order(exchange, symbol, direction, amount, trigger_price):
    if amount <= 0:
        return None
    close_side = "sell" if direction == "LONG" else "buy"
    trigger = float(exchange.price_to_precision(symbol, trigger_price))
    base = {"takeProfitPrice": trigger, "reduceOnly": True, "marginCoin": config.MARGIN_COIN}
    attempts = [
        dict(base, positionSide=direction),
        dict(base, hedged=True),
        dict(base),
    ]
    last_error = None
    for params in attempts:
        try:
            order = exchange.create_order(symbol, "TAKE_PROFIT_MARKET", close_side, amount, None, params=params)
            log.info("TP %.6g qty %.8g terpasang (id %s).", trigger, amount, order.get("id"))
            return order
        except Exception as exc:
            last_error = exc
    log.warning("TP %.6g gagal dipasang: %s", trigger, str(last_error).splitlines()[0][:150])
    return None


def _place_partial_tp(exchange, symbol, levels, amount):
    partial, _remainder = split_partial(exchange, symbol, levels, amount)
    if partial <= 0:
        return None
    return _place_tp_order(exchange, symbol, levels["direction"], partial, levels["tp1"])


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


def _place_entry_order_fallback(exchange, symbol, side, amount, params, levels):
    slim = {k: v for k, v in params.items() if k != "takeProfit"}
    order = None
    last_error = None
    for hedged in (True, False):
        attempt = dict(slim)
        if hedged:
            attempt["hedged"] = True
        try:
            order = exchange.create_order(symbol, "market", side, amount, None, params=attempt)
            break
        except Exception as exc:
            last_error = exc
            text = str(exc).lower()
            if "positionside" not in text and "hedge" not in text:
                break
    if order is None:
        raise last_error
    _remainder, _ = split_partial(exchange, symbol, levels, amount)
    tp2 = _place_tp_order(exchange, symbol, levels["direction"], _remainder, levels["take_profit"])
    tp1 = _place_partial_tp(exchange, symbol, levels, amount)
    if tp2 is None:
        log.warning("TP akhir fallback gagal - posisi hanya dilindungi SL.")
    if tp1 is None:
        log.warning("TP1 fallback gagal - posisi hanya dilindungi SL dan TP akhir.")
    return order, tp1


def execute(levels, live, data_source_id=None, symbol=None, credentials=None):
    symbol = symbol or config.SYMBOL
    if not live:
        exchange = _public_exchange_with_markets(data_source_id)
        notional = config.SIMULATED_NOTIONAL_USDT
        margin_used = notional / levels["leverage"]
        amount = float(exchange.amount_to_precision(symbol, notional / levels["entry"]))
        side, _ = prepare_order(exchange, symbol, levels, amount)
        partial, _ = split_partial(exchange, symbol, levels, amount)
        return {
            "mode": "dry-run",
            "executed": False,
            "side": side,
            "amount": amount,
            "order_id": None,
            "margin_used": margin_used,
            "notional": notional,
            "tp1_amount": partial,
            "detail": f"Simulasi - tidak ada order dikirim (TP1 {levels['tp1_fraction']*100:.0f}% @ {levels['tp1_pct']:.1f}%, sisa ke TP {levels['tp_distance_pct']:.1f}%)." if partial else "Simulasi - tidak ada order dikirim ke bursa.",
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
    partial, _ = split_partial(exchange, symbol, levels, amount)
    side, params = prepare_order(exchange, symbol, levels, amount)
    tp1_order = None
    fallback_used = False
    try:
        order = _place_entry_order(exchange, symbol, side, amount, params)
    except Exception as exc:
        log.warning("Entry dengan TP parsial ditolak (%s) - mencoba fallback.", str(exc).splitlines()[0][:150])
        if open_positions(exchange, symbol):
            raise
        order, tp1_order = _place_entry_order_fallback(exchange, symbol, side, amount, params, levels)
        fallback_used = True
    if not fallback_used and partial > 0:
        tp1_order = _place_partial_tp(exchange, symbol, levels, amount)
    detail = f"Bracket order terisolasi terkirim, id {order.get('id')} (margin {margin_used:,.2f} {config.MARGIN_COIN})."
    if partial > 0 and tp1_order is None:
        detail += " TP parsial GAGAL - sisa posisi hanya dilindungi SL dan TP akhir."
    elif tp1_order is not None:
        detail += f" TP1 {levels['tp1_fraction']*100:.0f}% @ {levels['tp1_pct']:.1f}% (id {tp1_order.get('id')})."
    return {
        "mode": "live",
        "executed": True,
        "side": side,
        "amount": amount,
        "order_id": str(order.get("id")),
        "margin_used": margin_used,
        "notional": notional,
        "tp1_amount": partial,
        "tp1_order_id": str(tp1_order.get("id")) if tp1_order else None,
        "detail": detail,
    }
