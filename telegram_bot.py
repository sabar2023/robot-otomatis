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
    is_long = levels["direction"] == "LONG"

    if is_long:
        pos_line = "&#128994; <b>POSISI</b>   : LONG (BUY)"
        if d2["near_support"]:
            dist = abs(price - d2["support"]) / d2["support"] * 100.0
            zone_line = (
                f"Harga {fmt_price(price)} memantul {dist:.1f}% di atas support {fmt_price(d2['support'])} "
                f"(swing low 20 candle {config.TIMEFRAME_LABEL}) dan tetap di atas VWAP {fmt_price(d2['vwap'])} "
                f"— area beli berisiko rendah di zona kunci."
            )
            zone_short = f"Pantulan Support {fmt_price(d2['support'])}"
        else:
            zone_line = (
                f"Harga baru saja close di atas resistance {fmt_price(d2['resistance'])} — "
                f"konfirmasi penguatan breakout, divalidasi VWAP {fmt_price(d2['vwap'])} di bawah harga."
            )
            zone_short = f"Breakout Resistance {fmt_price(d2['resistance'])}"
        if d3["bounce"]:
            mom_line = (
                f"RSI ({d3['rsi']:.0f}) baru crossing naik dari area oversold (&lt;30) — "
                f"awal pembalikan momentum, masih sisi awal gelombang."
            )
            mom_short = "RSI naik dari oversold"
        else:
            mom_line = (
                f"RSI ({d3['rsi']:.0f}) di atas 50 — momentum beli dominan."
            )
            mom_short = "RSI kuat di atas 50"
        trend_line = (
            f"{config.TIMEFRAME_LABEL} close di atas EMA{config.EMA_TREND_BASE} dan {config.TIMEFRAME_HIGHER_LABEL} close di atas EMA{config.EMA_TREND_HIGHER} — "
            f"mengikuti tren institusi; melawan tren adalah penyebab utama scalping gagal."
        )
        trend_short = f"{config.TIMEFRAME_LABEL} &gt; EMA{config.EMA_TREND_BASE}, {config.TIMEFRAME_HIGHER_LABEL} &gt; EMA{config.EMA_TREND_HIGHER}"
        vol_line = (
            f"Volume {d3['volume_ratio']:.1f}x rata-rata 20 candle — ada penyerapan/akumulasi "
            f"yang mendukung gerak naik, mengurangi risiko fakeout."
        )
        risk_line = (
            f"SL {config.ATR_SL_MULT:g}x ATR ({fmt_price(result['atr'])}) di bawah entry mengikuti volatilitas riil; "
            f"TP {config.ATR_TP_MULT:g}x ATR menghasilkan RR 1:2 — rugi kecil, profit target besar."
        )
    else:
        pos_line = "&#128308; <b>POSISI</b>   : SHORT (SELL)"
        if d2["near_support"]:
            dist = abs(d2["resistance"] - price) / d2["resistance"] * 100.0
            zone_line = (
                f"Harga {fmt_price(price)} tertahan {dist:.1f}% di bawah resistance {fmt_price(d2['resistance'])} "
                f"(swing high 20 candle {config.TIMEFRAME_LABEL}) dan di bawah VWAP {fmt_price(d2['vwap'])} "
                f"— area jual berisiko rendah di zona kunci."
            )
            zone_short = f"Pantulan Resistance {fmt_price(d2['resistance'])}"
        else:
            zone_line = (
                f"Harga baru saja close di bawah support {fmt_price(d2['support'])} — "
                f"konfirmasi pelemahan breakdown, divalidasi VWAP {fmt_price(d2['vwap'])} di atas harga."
            )
            zone_short = f"Breakdown Support {fmt_price(d2['support'])}"
        if d3["bounce"]:
            mom_line = (
                f"RSI ({d3['rsi']:.0f}) baru crossing turun dari area overbought (&gt;70) — "
                f"awal pembalikan bearish, masih sisi awal gelombang turun."
            )
            mom_short = "RSI turun dari overbought"
        else:
            mom_line = (
                f"RSI ({d3['rsi']:.0f}) di bawah 50 — momentum jual dominan."
            )
            mom_short = "RSI lemah di bawah 50"
        trend_line = (
            f"{config.TIMEFRAME_LABEL} close di bawah EMA{config.EMA_TREND_BASE} dan {config.TIMEFRAME_HIGHER_LABEL} close di bawah EMA{config.EMA_TREND_HIGHER} — "
            f"mengikuti tren turun institusi; melawan tren adalah penyebab utama short gagal."
        )
        trend_short = f"{config.TIMEFRAME_LABEL} &lt; EMA{config.EMA_TREND_BASE}, {config.TIMEFRAME_HIGHER_LABEL} &lt; EMA{config.EMA_TREND_HIGHER}"
        vol_line = (
            f"Volume {d3['volume_ratio']:.1f}x rata-rata 20 candle — ada tekanan jual yang tervalidasi, "
            f"bukan penurunan sepi volume."
        )
        risk_line = (
            f"SL {config.ATR_SL_MULT:g}x ATR ({fmt_price(result['atr'])}) di atas entry mengikuti volatilitas riil; "
            f"TP {config.ATR_TP_MULT:g}x ATR di bawah menghasilkan RR 1:2."
        )

    vol_and_mom_short = f"{mom_short}, Volume {d3['volume_ratio']:.1f}x SMA{config.VOLUME_SMA_PERIOD}"

    leverage_line = (
        f"&#9881; <b>LEVERAGE</b>   : {levels['leverage']}x "
        f"(jarak SL {levels['sl_distance_pct']:.2f}%, risiko max ±{config.RISK_PER_TRADE_PCT:g}% margin saat SL kena)"
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
        if is_long:
            explanation.append(
                f"&#8226; BTC: {fmt_price(d5['btc_close'])} &gt; EMA{config.EMA_TREND_BASE} "
                f"({fmt_price(d5['btc_ema200'])}) dan tidak breaking support — "
                f"'penguasa pasar' searah, pergerakan altcoin lebih aman."
            )
        else:
            explanation.append(
                f"&#8226; BTC: {fmt_price(d5['btc_close'])} tidak breakout resistance "
                f"({fmt_price(d5['btc_resistance'])}) dan di bawah EMA{config.EMA_TREND_BASE} "
                f"{fmt_price(d5['btc_ema200'])} +{config.BTC_FAR_BELOW_EMA_PCT:g}% — "
                f"'penguasa pasar' tidak melawan posisi short."
            )
    explanation.append(f"&#8226; Risiko: {risk_line}")

    if is_long:
        trend_bullet = (
            f"- Tren: Multi-TF Bullish ({config.TIMEFRAME_LABEL} &gt; EMA{config.EMA_TREND_BASE}, {config.TIMEFRAME_HIGHER_LABEL} &gt; EMA{config.EMA_TREND_HIGHER})."
        )
    else:
        trend_bullet = (
            f"- Tren: Multi-TF Bearish ({config.TIMEFRAME_LABEL} &lt; EMA{config.EMA_TREND_BASE}, {config.TIMEFRAME_HIGHER_LABEL} &lt; EMA{config.EMA_TREND_HIGHER})."
        )
    btc_bullet_long = (
        f"- BTC: Sejalan (BTC/USDT {fmt_price(d5['btc_close']) if result['is_altcoin'] else '-'} "
        f"&gt; EMA{config.EMA_TREND_BASE})."
    ) if is_long else None

    lines = [
        "&#128680; <b>BRANDBISNIS SCALP ALERT</b> &#128680;",
        f"&#9200; <i>Timeframe:</i> 5 Menit ({config.TIMEFRAME_LABEL}) | <i>Mode:</i> Futures Standard",
        "",
        f"&#128200; <b>PASANGAN</b> : {result['symbol']}",
        pos_line,
        "",
        f"&#127919; <b>ENTRY</b>    : {fmt_price(levels['entry_low'])} - {fmt_price(levels['entry_high'])} "
        f"({'di atas harga sinyal' if is_long else 'di bawah harga sinyal'})",
        f"&#128721; <b>STOP LOSS</b>: {fmt_price(levels['stop_loss'])} ({config.ATR_SL_MULT:g}x ATR)",
        f"&#9989; <b>TAKE PROFIT</b>: {fmt_price(levels['take_profit'])} (RR 1:2)",
        leverage_line,
        "",
        "&#128202; <b>Analisis AI Teknikal:</b>",
        trend_bullet,
        f"- Zona: {zone_short} + Price {'&gt;' if is_long else '&lt;'} VWAP {fmt_price(d2['vwap'])}.",
        f"- Vol &amp; Mom: {vol_and_mom_short}.",
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
        f"Bot aktif. Mesin 5-Layer Filter siap memindai pasar setiap 5 menit ({config.TIMEFRAME_LABEL}).\n"
        "<i>Non-Execution: sinyal Entry, TP, dan SL saja, tanpa menyentuh dana.</i>"
    )
    return send_message(body)
