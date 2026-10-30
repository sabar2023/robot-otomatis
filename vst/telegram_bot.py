import requests

import config


def fmt_price(value):
    value = float(value)
    if value >= 1000:
        return f"{value:,.1f}"
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:,.4f}"


def build_alert_html(result, levels, execution, user=None):
    is_long = levels["direction"] == "LONG"
    if execution["mode"] == "live" and config.EXEC_MODE == "real":
        mode_line = "&#128225; <b>LIVE (BingX akun real, USDT)</b>"
    elif execution["mode"] == "live":
        mode_line = "&#128225; <b>LIVE VST</b> (demo BingX)"
    else:
        mode_line = "&#9888;&#65039; <b>DRY-RUN</b> (simulasi, tanpa order)"
    pos_line = "&#128994; <b>POSISI</b>  : LONG (BUY)" if is_long else "&#128308; <b>POSISI</b>  : SHORT (SELL)"
    layer_lines = []
    for layer in result["layers"]:
        mark = "&#9989;" if layer["passed"] else "&#10060;"
        detail = " ".join(f"{k}={fmt_price(v)}" for k, v in layer["detail"].items())
        layer_lines.append(f"{mark} <b>{layer['name']}</b>: {detail}")

    user_line = None
    if user and user.get("email") and user["email"] != "owner":
        user_line = f"&#128100; <b>USER</b>     : {user['email']}"
    notional = execution.get("notional")
    margin_used = execution.get("margin_used")
    lev_line = f"&#128737; <b>LEVERAGE</b> : {levels['leverage']}x"
    size_line = f"&#128176; <b>SIZE</b>     : {notional:,.0f} USDT notional | <b>MARGIN</b>: {margin_used:,.2f} {config.MARGIN_COIN} ({levels['margin_pct']:g}%)" if notional else (
        f"&#128176; <b>MARGIN</b>   : {config.MARGIN_COIN} terisolasi"
    )

    tp1_line = None
    if levels.get("tp1") and levels.get("tp1_fraction"):
        tp1_line = (
            f"&#127919; <b>TP1 (partial)</b>: {fmt_price(levels['tp1'])} ({levels['tp1_pct']:.2f}% | "
            f"{levels['tp1_fraction']*100:.0f}% posisi ditutup)"
        )

    lines = [
        "&#128680; <b>BRANDBISNIS V5.0 ALERT</b> &#128680;",
        mode_line,
        user_line,
        "",
        f"&#128200; <b>PASANGAN</b> : {result['symbol']}",
        f"&#9200; <b>TIMEFRAME</b> : {result['timeframe']} (basis candle tutup {result['candle_open'].strftime('%Y-%m-%d %H:%M')} UTC)",
        pos_line,
        "",
        f"&#127919; <b>ENTRY</b>    : {fmt_price(levels['entry'])}",
        f"&#128721; <b>STOP LOSS</b>: {fmt_price(levels['stop_loss'])} (<b>SL {levels['sl_distance_pct']:.2f}%</b>)",
        tp1_line,
        f"&#9989; <b>TAKE PROFIT</b>: {fmt_price(levels['take_profit'])} (<b>TP {levels['tp_distance_pct']:.2f}%</b> | RR 1:{levels['rr']:g})",
        lev_line,
        size_line,
        "",
        f"&#128221; <b>{len(result['layers'])}-Layer Check:</b>",
        *layer_lines,
        "",
        f"&#128228; <b>STATUS ORDER</b>: {execution['detail']}",
        (f"&#127991; <b>ORDER ID</b>   : {execution['order_id']}") if execution["order_id"] else None,
    ]
    return "\n".join(line for line in lines if line is not None)


def build_error_html(message, mode):
    mode_label = "LIVE VST" if mode == "live" else "DRY-RUN"
    return (
        "&#10060; <b>BRANDBISNIS VST ERROR</b>\n"
        f"Mode: {mode_label}\n"
        f"Error: <code>{message}</code>"
    )


def send_message(text, chat_id=None):
    token = config.TELEGRAM_BOT_TOKEN
    chat = chat_id or config.TELEGRAM_CHAT_ID
    if not token or not chat:
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram menolak pesan: {data.get('description', data)}")
    return data


def send_test_message(live):
    body = (
        "&#128225; <b>BRANDBISNIS V5.0 BOT</b>\n"
        f"Bot aktif. Mode: <b>{'LIVE VST (demo BingX)' if live else 'DRY-RUN'}</b>.\n"
        f"Menyusun 5-Layer Filter {config.TIMEFRAME_LABEL} (multi-user) setiap {config.SCAN_INTERVAL_MINUTES} menit.\n"
        f"Order: bracket SL/TP (default ATR x{config.ATR_SL_MULT:g}/x{config.ATR_TP_MULT:g}, bisa di-set user), "
        f"leverage {config.LEVERAGE_MIN}-{config.LEVERAGE_MAX}x, margin maksimal {config.MARGIN_PCT:g}% per order, terisolasi."
    )
    return send_message(body)
