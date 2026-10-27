import requests

import config


def fmt_price(value):
    value = float(value)
    if value >= 1000:
        return f"{value:,.1f}"
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:,.4f}"


def build_alert_html(result, levels, execution):
    is_long = levels["direction"] == "LONG"
    mode_line = (
        "&#128225; <b>LIVE VST</b> (demo BingX)"
        if execution["mode"] == "live"
        else "&#9888;&#65039; <b>DRY-RUN</b> (simulasi, tanpa order)"
    )
    pos_line = "&#128994; <b>POSISI</b>  : LONG (BUY)" if is_long else "&#128308; <b>POSISI</b>  : SHORT (SELL)"
    layer_lines = []
    for layer in result["layers"]:
        mark = "&#9989;" if layer["passed"] else "&#10060;"
        detail = " ".join(f"{k}={fmt_price(v)}" for k, v in layer["detail"].items())
        layer_lines.append(f"{mark} <b>{layer['name']}</b>: {detail}")

    lines = [
        "&#128680; <b>BRANDBISNIS VST ALERT</b> &#128680;",
        mode_line,
        "",
        f"&#128200; <b>PASANGAN</b> : {result['symbol']}",
        f"&#9200; <b>TIMEFRAME</b> : {result['timeframe']} (basis candle tutup {result['candle_open'].strftime('%Y-%m-%d %H:%M')} UTC)",
        pos_line,
        "",
        f"&#127919; <b>ENTRY</b>    : {fmt_price(levels['entry'])}",
        f"&#128721; <b>STOP LOSS</b>: {fmt_price(levels['stop_loss'])} ({config.ATR_SL_MULT:g}x ATR)",
        f"&#9989; <b>TAKE PROFIT</b>: {fmt_price(levels['take_profit'])} (RR 1:{levels['rr']:g})",
        f"&#128202; <b>ATR(14)</b>  : {fmt_price(levels['atr'])}",
        f"&#128176; <b>SIZE</b>     : {levels['size_usdt']:g} USDT | <b>LEVERAGE</b>: {levels['leverage']}x | <b>MARGIN</b>: {config.MARGIN_COIN}",
        "",
        "&#128221; <b>5-Layer Check:</b>",
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


def send_message(text):
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return None
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    resp = requests.post(
        url,
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True},
        timeout=30,
    )
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram menolak pesan: {data.get('description', data)}")
    return data


def send_test_message(live):
    body = (
        "&#128225; <b>BRANDBISNIS VST BOT</b>\n"
        f"Bot aktif. Mode: <b>{'LIVE VST (demo BingX)' if live else 'DRY-RUN'}</b>.\n"
        f"Menyusun 5-Layer Filter {config.TIMEFRAME_LABEL} untuk {config.SYMBOL} setiap {config.SCAN_INTERVAL_MINUTES} menit.\n"
        f"Order: bracket SL/TP ATR ({config.ATR_SL_MULT:g}x/{config.ATR_TP_MULT:g}x), leverage {config.LEVERAGE}x, margin {config.MARGIN_COIN}."
    )
    return send_message(body)
