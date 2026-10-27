import argparse
import datetime as dt
import logging
import sys
import time

import config
import database
import executor
import filters
import market_data
import risk
import telegram_bot

log = logging.getLogger("brandbisnis_vst")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def log_evaluation(symbol, result):
    status = f"SINYAL {result['direction']}" if result["passed"] else "STANDBY"
    log.info("%s | %s | harga=%s ATR=%s", symbol, status, f"{result['price']:,.2f}", f"{result['atr']:,.2f}")
    for layer in result["layers"]:
        mark = "PASS" if layer["passed"] else "FAIL"
        detail = " ".join(f"{k}={v:,.2f}" if isinstance(v, float) else f"{k}={v}" for k, v in layer["detail"].items())
        log.info("    %-26s %s | %s", layer["name"], mark, detail)
    if not result["passed"]:
        log.info("    Dibatalkan: %s", ", ".join(result["failed_layers"]))


def scan_once(live):
    now = dt.datetime.now(dt.timezone.utc)
    chain = market_data.build_chain()
    fetch = market_data.make_fetcher(chain)
    symbol = config.SYMBOL

    log.info("Memindai %s ...", symbol)
    raw, src = fetch(symbol, config.TIMEFRAME, config.CANDLE_LIMIT)
    base = market_data.closed_candles(raw)
    log.info("Sumber data: %s | %d candle close", src, len(base))

    candle_open = base["ts"].iloc[-1]
    candle_close = candle_open + dt.timedelta(minutes=config.TIMEFRAME_MINUTES)
    age_minutes = (now - candle_close).total_seconds() / 60.0
    fresh = age_minutes <= config.FRESH_CANDLE_MAX_AGE_MINUTES

    result = filters.evaluate(symbol, base)
    log_evaluation(symbol, result)
    database.log_scan(symbol, "live" if live else "dry-run", result, src)

    if not result["passed"]:
        log.info("Tidak ada sinyal - 5 layer filter tidak tercapai.")
        return None
    if not fresh:
        log.info("Sinyal %s berbasis candle %s UTC (umur %.1f menit) - basi, dilewati.", symbol, candle_close.strftime("%H:%M"), age_minutes)
        return None

    execute_live = live
    if execute_live and not database.auto_enabled():
        log.info("Toggle ro_config.auto_trading = false - eksekusi live dilewati (simulasi).")
        execute_live = False
    levels = risk.compute_levels(result["direction"], result["price"], result["atr"])
    execution = executor.execute(levels, live=execute_live, data_source_id=src)
    database.log_execution(symbol, execution["mode"], levels, execution)
    log.info("Eksekusi [%s]: %s", execution["mode"], execution["detail"])

    html = telegram_bot.build_alert_html(result, levels, execution)
    try:
        if telegram_bot.send_message(html) is not None:
            log.info("Pesan VST terkirim ke Telegram.")
        else:
            log.info("Telegram tidak dikonfigurasi - pesan hanya di log.")
    except Exception as exc:
        log.error("Gagal mengirim pesan VST ke Telegram: %s", exc)

    return {"result": result, "levels": levels, "execution": execution}


def next_boundary(now):
    interval = config.SCAN_INTERVAL_MINUTES
    minute = (now.minute // interval) * interval
    target = now.replace(minute=minute, second=0, microsecond=0) + dt.timedelta(minutes=interval)
    return target


def run_loop(live):
    log.info("Mode loop lokal: scan sekarang, lalu tiap kelipatan %d menit.", config.SCAN_INTERVAL_MINUTES)
    while True:
        try:
            scan_once(live)
        except Exception as exc:
            log.error("Error pada siklus: %s", exc)
        now = dt.datetime.now(dt.timezone.utc)
        wait = (next_boundary(now) - now).total_seconds()
        if wait > 5:
            log.info("Menunggu %s UTC untuk siklus berikutnya (%.0f detik).", next_boundary(now).strftime("%H:%M"), wait)
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description=f"{config.PRODUCT_NAME} - eksekusi M5 (BingX VST)")
    parser.add_argument("--dry-run", action="store_true", help="Paksa mode simulasi - tidak ada order dikirim")
    parser.add_argument("--live", action="store_true", help="Paksa mode live VST - kirim bracket order (butuh BINGX_API_KEY/BINGX_SECRET_KEY)")
    parser.add_argument("--loop", action="store_true", help="Jalankan terus tiap kelipatan 5 menit (hanya dev lokal)")
    parser.add_argument("--test-telegram", action="store_true", help="Kirim pesan tes untuk validasi kredensial Telegram")
    args = parser.parse_args()

    setup_logging()
    live = config.EXECUTE_LIVE
    if args.dry_run:
        live = False
    if args.live:
        live = True
    mode_label = "LIVE VST" if live else "DRY-RUN"
    log.info("=== %s | %s | mode: %s ===", config.PRODUCT_NAME, config.TIMEFRAME_LABEL, mode_label)
    log.info("Simbol: %s | Size: %g USDT | Leverage: %dx | Margin: %s", config.SYMBOL, config.POSITION_SIZE_USDT, config.LEVERAGE, config.MARGIN_COIN)

    if args.test_telegram:
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID kosong. Isi .env dulu.")
            sys.exit(1)
        telegram_bot.send_test_message(live)
        log.info("Pesan tes Telegram terkirim. Kredensial valid.")
        sys.exit(0)

    if live and not (config.BINGX_API_KEY and config.BINGX_SECRET_KEY):
        log.error("Mode live dipilih tetapi BINGX_API_KEY / BINGX_SECRET_KEY kosong. Jalankan dengan --dry-run atau isi kredensial VST.")
        sys.exit(1)
    if live:
        log.warning("MODE LIVE: bracket order akan dikirim ke BingX VST (demo) untuk %s.", config.SYMBOL)

    if args.loop:
        run_loop(live)
        return

    try:
        scan_once(live)
    except Exception as exc:
        log.error("Scan gagal: %s", exc)
        try:
            telegram_bot.send_message(telegram_bot.build_error_html(str(exc).splitlines()[-1], "live" if live else "dry-run"))
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
