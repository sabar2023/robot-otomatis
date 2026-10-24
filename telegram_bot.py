import requests

import config
import risk as risk_mod


def fmt_price(value):
    value = float(value)
    if value >= 1000:
        return f"{value:,.0f}"
    if value >= 1:
        return f"{value:,.2f}"
    return f"{value:,.4f}"


def build_alert_html(result, levels):
    d1 = result["layers"][0]["detail"]
    d2 = result["layers"][1]["detail"]
    d3 = result["layers"][2]["detail"]
    d4 = result["layers"][3]["detail"]
    price = result["price"]

    if d2["near_support"]:
        dist = abs(price - d2["support"]) / d2["support"] * 100.0
        zone_line = (
            f"Harga {fmt_price(price)} memantul {dist:.1f}% di atas support {fmt_price(d2['support'])} "
            f"(swing low 20 candle M15) dan tetap di atas VWAP {fmt_price(d2['vwap'])} "
            f"— area beli berisiko rendah di zona kunci."
        )
    else:
        zone_line = (
            f"Harga baru saja close di atas resistance {fmt_price(d2['resistance'])} — "
            f"konfirmasi penguatan breakout, divalidasi VWAP {fmt_price(d2['vwap'])} di bawah harga."
        )

    if d3["bounce"]:
        mom_line = (
            f"RSI ({d3['rsi']:.0f}) baru crossing naik dari area oversold (&lt;30) — "
            f"awal pembalikan momentum, masih masuk disisi awal gelombang."
        )
    else:
        mom_line = (
            f"RSI ({d3['rsi']:.0f}) di atas 50 — momentum beli dominan, "
            f"bukan kejaran puncak karena volume masih sehat."
        )

    vol_line = (
        f"Volume {d3['volume_ratio']:.1f}x rata-rata 20 candle — ada penyerapan/akumulasi "
        f"yang mendukung gerak, mengurangi risiko fakeout."
    )

    trend_line = (
        f"M15 close di atas EMA{config.EMA_TREND_M15} dan H1 close di atas EMA{config.EMA_TREND_H1} — "
        f"mengikuti tren institusi; melawan tren adalah penyebab utama scalping gagal."
    )

    explanation = [
        f"&#129504; <b>Penjelasan Sinyal:</b>",
        f"&#8226; Zona: {zone_line}",
        f"&#8226; Momentum: {mom_line}",
        f"&#8226; Volume: {vol_line}",
        f"&#8226; Tren: {trend_line}",
    ]
    if result["is_altcoin"]:
        d5 = result["layers"][4]["detail"]
        explanation.append(
            f"&#8226; BTC: {fmt_price(d5['btc_close'])} &gt; EMA{config.EMA_TREND_M15} "
            f"({fmt_price(d5['btc_ema200'])}) dan tidak breaking support — "
            f"'penguasa pasar' searah, pergerakan altcoin lebih aman."
        )
    explanation.append(
        f"&#8226; Risiko: SL 1.5x ATR ({fmt_price(result['atr'])}) mengikuti volatilitas riil pasar; "
        f"TP 3.0x ATR menghasilkan RR 1:2 — rugi kecil, profit target besar."
    )

    lines = [
        "&#128680; <b>BRANDBISNIS SCALP ALERT</b> &#128680;",
        f"&#9200; <i>Timeframe:</i> 15 Menit (M15)",
        "",
        f"&#128200; <b>PASANGAN</b> : {result['symbol']}",
        "&#128994; <b>POSISI</b>   : LONG (BUY)",
        "",
        f"&#127919; <b>ENTRY</b>    : {fmt_price(levels['entry_low'])} - {fmt_price(levels['entry_high'])}",
        f"&#128721; <b>STOP LOSS</b>: {fmt_price(levels['stop_loss'])} ({config.ATR_SL_MULT:g}x ATR)",
        f"&#9989; <b>TAKE PROFIT</b>: {fmt_price(levels['take_profit'])} (RR 1:{levels['rr']:.0f})",
        "",
        "&#128202; <b>Analisis AI Teknikal:</b>",
        f"- Tren: Multi-TF Bullish (M15 &gt; EMA{config.EMA_TREND_M15}, H1 &gt; EMA{config.EMA_TREND_H1}).",
        f"- Zona: {'Pantulan Support terkonfirmasi' if d2['near_support'] else 'Breakout Resistance terkonfirmasi'} "
        f"(S {fmt_price(d2['support'])} / R {fmt_price(d2['resistance'])}) + Price &gt; VWAP {fmt_price(d2['vwap'])}.",
        f"- Vol &amp; Mom: RSI ({d3['rsi']:.0f}) {'naik dari oversold' if d3['bounce'] else 'tren kuat di atas 50'}, "
        f"Volume {d3['volume_ratio']:.1f}x SMA{config.VOLUME_SMA_PERIOD}.",
        f"- ADX ({d4['adx']:.0f}) &gt; {config.ADX_MIN} (Strong Trend).",
        "",
    ]
    lines.extend(explanation)
    return "\n".join(lines)


def send_message(text):
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diisi di .env atau secrets GitHub.")
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


def send_test_message():
    body = (
        "&#128225; <b>BRANDBISNIS SIGNAL BOT</b>\n"
        "Bot aktif. Mesin 5-Layer Filter siap memindai pasar setiap 15 menit (M15).\n"
        "<i>Non-Execution: sinyal Entry, TP, dan SL saja, tanpa menyentuh dana.</i>"
    )
    return send_message(body)
