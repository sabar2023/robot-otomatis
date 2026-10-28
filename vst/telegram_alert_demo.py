import logging
import sys

import config
import database
import filters
import market_data
import telegram_bot

log = logging.getLogger("brandbisnis_vst")


def _one_line(exc):
    return str(exc).splitlines()[0][:200]


def build_levels(row, user):
    entry = float(row["entry"])
    stop_loss = float(row["stop_loss"])
    take_profit = float(row["take_profit"])
    direction = row["direction"]
    leverage = int(user.get("leverage") or config.LEVERAGE_DEFAULT)
    margin_pct = float(user.get("margin_pct") or config.MARGIN_PCT)
    sl_distance_pct = abs(entry - stop_loss) / entry * 100.0
    tp_distance_pct = abs(take_profit - entry) / entry * 100.0
    rr = tp_distance_pct / sl_distance_pct if sl_distance_pct else 0.0
    return {
        "direction": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "sl_distance_pct": sl_distance_pct,
        "tp_distance_pct": tp_distance_pct,
        "rr": rr,
        "leverage": leverage,
        "margin_pct": margin_pct,
    }


def build_result(row, symbol):
    chain = market_data.build_chain()
    fetch = market_data.make_fetcher(chain)
    raw, _src = fetch(symbol, config.TIMEFRAME, config.CANDLE_LIMIT)
    base = market_data.closed_candles(raw)
    result = filters.evaluate(symbol, base)
    result["direction"] = row["direction"]
    result["passed"] = True
    result["layers"] = [dict(layer, passed=True) for layer in result["layers"]]
    result["failed_layers"] = []
    return result


def build_execution(row):
    return {
        "mode": row["mode"],
        "executed": bool(row.get("executed")),
        "side": row.get("side"),
        "amount": row.get("amount"),
        "order_id": row.get("order_id"),
        "margin_used": None,
        "notional": None,
        "detail": row.get("detail") or "",
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s", stream=sys.stdout)
    row = database.latest_execution()
    if not row:
        log.error("ro_executions kosong - tidak ada eksekusi terakhir untuk dibuatkan contoh alert.")
        sys.exit(1)

    users = database.fetch_users()
    user = users[0] if users else {"email": "owner", "leverage": None, "margin_pct": None, "tg_chat_id": None}
    symbol = row["symbol"]
    log.info("Membuat contoh alert dari eksekusi terakhir %s id=%s", symbol, row.get("id"))

    try:
        result = build_result(row, symbol)
    except Exception as exc:
        log.error("Gagal memuat data pasar untuk contoh alert: %s", _one_line(exc))
        sys.exit(1)

    levels = build_levels(row, user)
    execution = build_execution(row)
    html = telegram_bot.build_alert_html(result, levels, execution, user)

    sent = telegram_bot.send_message(html)
    if sent is None:
        log.error("Telegram tidak dikonfigurasi - contoh alert tidak terkirim.")
        sys.exit(1)
    message_id = sent.get("message_id") if isinstance(sent, dict) else sent
    log.info("Contoh alert terkirim ke grup Telegram (message id %s).", message_id)

    user_chat = (user.get("tg_chat_id") or "").strip()
    if user_chat and user_chat != config.TELEGRAM_CHAT_ID:
        if telegram_bot.send_message(html, chat_id=user_chat) is not None:
            log.info("Contoh alert juga terkirim ke chat user %s.", user.get("email"))


if __name__ == "__main__":
    main()
