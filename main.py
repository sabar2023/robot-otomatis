import argparse
import datetime as dt
import logging
import sys
import time

import config
import filters
import market_data
import risk
import telegram_bot

log = logging.getLogger("brandbisnis")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def log_scan_result(symbol, result):
    status = "SINYAL LONG" if result["passed"] else "STANDBY"
    log.info("%s | %s | harga=%s ATR=%s", symbol, status, f"{result['price']:,.2f}", f"{result['atr']:,.2f}")
    for layer in result["layers"]:
        mark = "PASS" if layer["passed"] else "FAIL"
        detail = layer["detail"]
        summary = " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in detail.items())
        log.info("    %-22s %s | %s", layer["name"], mark, summary)
    if not result["passed"]:
        log.info("    Dibatalkan: %s", ", ".join(result["failed_layers"]))


def scan_once():
    now = dt.datetime.now(dt.timezone.utc)
    chain = market_data.build_chain(config.EXCHANGE_ID)
    fetch = market_data.make_fetcher(chain)
    symbols = config.SYMBOLS
    btc_m15 = None
    btc_src = None
    signals = []
    scanned = 0
    failed = 0

    for symbol in symbols:
        log.info("Memindai %s ...", symbol)
        try:
            if symbol == config.BTC_SYMBOL:
                btc_raw, btc_src = fetch(symbol, config.TIMEFRAME_SCALP, config.M15_CANDLE_COUNT)
                btc_m15 = market_data.closed_candles(btc_raw)
                m15 = btc_m15
            else:
                if btc_m15 is None and config.BTC_SYMBOL in symbols:
                    btc_raw, btc_src = fetch(config.BTC_SYMBOL, config.TIMEFRAME_SCALP, config.M15_CANDLE_COUNT)
                    btc_m15 = market_data.closed_candles(btc_raw)
                if btc_m15 is None:
                    btc_raw, btc_src = fetch(config.BTC_SYMBOL, config.TIMEFRAME_SCALP, config.M15_CANDLE_COUNT)
                    btc_m15 = market_data.closed_candles(btc_raw)
                m15, m15_src = fetch(symbol, config.TIMEFRAME_SCALP, config.M15_CANDLE_COUNT)
                m15 = market_data.closed_candles(m15)
            h1, h1_src = fetch(symbol, config.TIMEFRAME_HIGHER, config.H1_CANDLE_COUNT)
            h1 = market_data.closed_candles(h1)
            scanned += 1
            log.info("  Sumber data: %s", m15_src if symbol != config.BTC_SYMBOL else btc_src)
        except Exception as exc:
            failed += 1
            log.error("Gagal mengambil data %s: %s", symbol, exc)
            continue

        candle_close = m15["ts"].iloc[-1] + dt.timedelta(minutes=15)
        age_minutes = (now - candle_close).total_seconds() / 60.0
        fresh = age_minutes <= config.FRESH_CANDLE_MAX_AGE_MINUTES

        result = filters.evaluate(symbol, m15, h1, btc_m15, is_altcoin=symbol != config.BTC_SYMBOL)
        log_scan_result(symbol, result)
        if result["passed"] and not fresh:
            log.info("  Sinyal %s berbasis candle %s (umur %.1f menit) — basi untuk scalping, dilewati.", symbol, candle_close.strftime("%H:%M"), age_minutes)
            continue
        if result["passed"]:
            levels = risk.compute_levels(result["price"], result["atr"])
            signals.append({"result": result, "levels": levels})

    for signal in signals:
        html = telegram_bot.build_alert_html(signal["result"], signal["levels"])
        try:
            telegram_bot.send_message(html)
            log.info("Sinyal %s terkirim ke Telegram.", signal["result"]["symbol"])
        except Exception as exc:
            log.error("Gagal mengirim sinyal %s ke Telegram: %s", signal["result"]["symbol"], exc)

    if not signals:
        log.info("Tidak ada sinyal. Semua aset STANDBY.")
    if scanned == 0 and failed > 0:
        log.error("SEMUA bursa gagal menyediakan data (%d symbol). Siklus gagal.", failed)
        raise RuntimeError("Semua bursa tidak dapat dihubungi untuk mengambil data.")
    return signals


def next_boundary(now):
    interval = config.SCAN_INTERVAL_MINUTES
    minute = (now.minute // interval) * interval
    target = now.replace(minute=minute, second=0, microsecond=0) + dt.timedelta(minutes=interval)
    return target


def run_loop():
    log.info("Mode loop lokal: scan sekarang, lalu tiap kelipatan 15 menit.")
    while True:
        try:
            scan_once()
        except Exception as exc:
            log.error("Error pada siklus: %s", exc)
        now = dt.datetime.now(dt.timezone.utc)
        wait = (next_boundary(now) - now).total_seconds()
        if wait > 5:
            log.info("Menunggu %s UTC untuk siklus berikutnya (%.0f detik).", next_boundary(now).strftime("%H:%M"), wait)
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description="Robot Trading BrandBisnis - Signal Bot M15 (Non-Execution)")
    parser.add_argument("--dry-run", action="store_true", help="Hanya log ke console, tidak mengirim Telegram")
    parser.add_argument("--loop", action="store_true", help="Jalankan terus tiap kelipatan 15 menit (simulasi lokal)")
    parser.add_argument("--test-telegram", action="store_true", help="Kirim pesan tes untuk validasi kredensial")
    args = parser.parse_args()

    setup_logging()
    log.info("=== %s | Signal Bot M15 | 5-Layer Filter ===", config.PRODUCT_NAME)
    log.info("Exchange: %s | Watchlist: %s", config.EXCHANGE_ID, ", ".join(config.SYMBOLS))

    if args.test_telegram:
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID kosong. Isi .env dulu.")
            sys.exit(1)
        telegram_bot.send_test_message()
        log.info("Pesan tes Telegram terkirim. Kredensial valid.")
        sys.exit(0)

    if args.dry_run:
        log.info("MODE DRY-RUN: Telegram tidak akan menerima pesan.")

    if args.loop:
        run_loop()
    else:
        try:
            scan_once()
        except Exception as exc:
            log.error("Scan gagal: %s", exc)
            sys.exit(1)


if __name__ == "__main__":
    main()
