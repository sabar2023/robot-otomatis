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
import pnl
import risk
import telegram_bot
import watchlist

log = logging.getLogger("brandbisnis_vst")


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def _one_line(exc):
    return str(exc).splitlines()[0][:200]


def owner_user():
    return {
        "id": None,
        "email": "owner",
        "nama": "Owner",
        "api_key": config.BINGX_API_KEY,
        "secret_key": config.BINGX_SECRET_KEY,
        "mode_otomatis": True,
        "coins": [],
        "margin_pct": None,
        "leverage": None,
        "tp_pct": None,
        "sl_pct": None,
        "tg_chat_id": None,
    }


def resolve_users(only_email=None):
    users = database.fetch_users()
    if only_email:
        wanted = only_email.lower()
        users = [u for u in users if (u["email"] or "").lower() == wanted]
        if not users:
            log.warning("User %s tidak ditemukan di user_settings.", only_email)
        return users
    if not users:
        log.info("Belum ada user di Supabase - pakai akun owner (env BINGX_*).")
        return [owner_user()]
    return users


def log_evaluation(symbol, result):
    status = f"SINYAL {result['direction']}" if result["passed"] else "STANDBY"
    log.info("%s | %s | harga=%s ATR=%s", symbol, status, f"{result['price']:,.4f}", f"{result['atr']:,.4f}")
    for layer in result["layers"]:
        mark = "PASS" if layer["passed"] else "FAIL"
        detail = " ".join(f"{k}={v:,.4f}" if isinstance(v, float) else f"{k}={v}" for k, v in layer["detail"].items())
        log.info("    %-26s %s | %s", layer["name"], mark, detail)
    if not result["passed"]:
        log.info("    Dibatalkan: %s", ", ".join(result["failed_layers"]))


def scan_symbol(live, fetch, user, symbol, auto_global):
    now = dt.datetime.now(dt.timezone.utc)
    log.info("Memindai %s ...", symbol)
    raw, src = fetch(symbol, config.TIMEFRAME, config.CANDLE_LIMIT)
    base = market_data.closed_candles(raw)
    log.debug("Sumber data: %s | %d candle close", src, len(base))

    candle_open = base["ts"].iloc[-1]
    candle_close = candle_open + dt.timedelta(minutes=config.TIMEFRAME_MINUTES)
    age_minutes = (now - candle_close).total_seconds() / 60.0
    fresh = age_minutes <= config.FRESH_CANDLE_MAX_AGE_MINUTES

    result = filters.evaluate(symbol, base)
    log_evaluation(symbol, result)
    database.log_scan(symbol, "live" if live else "dry-run", result, src)

    if not result["passed"]:
        log.info("Tidak ada sinyal - 5 layer filter tidak tercapai.")
        return
    if not fresh:
        log.info(
            "Sinyal %s berbasis candle tutup %s UTC (umur %.1f menit) - basi, dilewati.",
            symbol,
            candle_close.strftime("%Y-%m-%d %H:%M"),
            age_minutes,
        )
        return

    auto = auto_global and bool(user["mode_otomatis"])
    execute_live = live and auto
    if live and not auto:
        log.info("Mode otomatis user / ro_config.auto_trading nonaktif - eksekusi live dilewati (simulasi).")

    levels = risk.compute_levels(
        result["direction"],
        result["price"],
        result["atr"],
        sl_pct=user["sl_pct"],
        tp_pct=user["tp_pct"],
        leverage=user["leverage"],
        margin_pct=user["margin_pct"],
    )
    credentials = {"api_key": user["api_key"], "secret_key": user["secret_key"]}
    execution = executor.execute(levels, live=execute_live, data_source_id=src, symbol=symbol, credentials=credentials)
    database.log_execution(symbol, execution["mode"], levels, execution)
    database.log_trade(user["id"], symbol, levels, execution)
    log.info("Eksekusi [%s]: %s", execution["mode"], execution["detail"])

    html = telegram_bot.build_alert_html(result, levels, execution, user)
    try:
        if telegram_bot.send_message(html) is not None:
            log.info("Pesan alert terkirim ke Telegram (admin).")
        else:
            log.info("Telegram tidak dikonfigurasi - pesan hanya di log.")
        user_chat = (user.get("tg_chat_id") or "").strip()
        if user_chat and user_chat != config.TELEGRAM_CHAT_ID:
            if telegram_bot.send_message(html, chat_id=user_chat) is not None:
                log.info("Pesan alert terkirim ke chat user %s.", user["email"])
    except Exception as exc:
        log.error("Gagal kirim alert Telegram: %s", _one_line(exc))


def scan_once(live, only_email=None):
    chain = market_data.build_chain()
    fetch = market_data.make_fetcher(chain)
    users = resolve_users(only_email)
    if not users:
        log.info("Tidak ada user untuk dipindai.")
        return 0

    auto_global = database.auto_enabled()
    watch_cache = {}
    for user in users:
        log.info("=== User: %s (%s) | otomatis: %s ===", user["nama"], user["email"], user["mode_otomatis"])
        if user["coins"]:
            coins = user["coins"]
            log.info("Watchlist manual: %s", ", ".join(coins))
        else:
            if "default" not in watch_cache:
                watch_cache["default"], watch_src = watchlist.default_watchlist(chain)
                log.info("Watchlist default (top %d volume, %s): %s", config.WATCHLIST_SIZE, watch_src, ", ".join(watch_cache["default"]))
            coins = watch_cache["default"]
        for symbol in coins:
            try:
                scan_symbol(live, fetch, user, symbol, auto_global)
            except Exception as exc:
                log.error("Gagal memindai %s untuk %s: %s", symbol, user["email"], _one_line(exc))
    closed = pnl.sync_all(users, live)
    if closed:
        log.info("PnL: %d trade dinyatakan tertutup.", closed)
    return len(users)


def next_boundary(now):
    return now.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)


def run_loop(live, only_email=None):
    log.info("Mode loop lokal: scan sekarang, lalu tiap awal jam UTC.")
    while True:
        try:
            scan_once(live, only_email)
        except Exception as exc:
            log.error("Error pada siklus: %s", _one_line(exc))
        now = dt.datetime.now(dt.timezone.utc)
        wait = (next_boundary(now) - now).total_seconds()
        if wait > 5:
            log.info("Menunggu %s UTC untuk siklus berikutnya (%.0f detik).", next_boundary(now).strftime("%H:%M"), wait)
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser(description=f"{config.PRODUCT_NAME}")
    parser.add_argument("--dry-run", action="store_true", help="Paksa mode simulasi - tidak ada order dikirim")
    parser.add_argument("--live", action="store_true", help="Paksa mode live - kirim order ke BingX VST (demo) user")
    parser.add_argument("--loop", action="store_true", help="Jalankan terus tiap awal jam (hanya dev lokal)")
    parser.add_argument("--user", metavar="EMAIL", help="Hanya pindai user dengan email ini")
    parser.add_argument("--test-telegram", action="store_true", help="Kirim pesan tes untuk validasi kredensial Telegram")
    args = parser.parse_args()

    setup_logging()
    live = config.EXECUTE_LIVE
    if args.dry_run:
        live = False
    if args.live:
        live = True
    mode_label = "LIVE VST" if live else "DRY-RUN"
    env_label = executor.execution_env_label()
    if live and config.EXEC_MODE == "real":
        mode_label = "LIVE REAL"
    log.info("=== %s | %s | mode: %s | lingkungan: %s ===", config.PRODUCT_NAME, config.TIMEFRAME_LABEL, mode_label, env_label)
    log.info(
        "Scan tiap %d menit | leverage %d-%dx | margin maksimal %g%%/order | SL/TP default ATR x%.1f/x%.1f",
        config.SCAN_INTERVAL_MINUTES,
        config.LEVERAGE_MIN,
        config.LEVERAGE_MAX,
        config.MARGIN_PCT,
        config.ATR_SL_MULT,
        config.ATR_TP_MULT,
    )

    if args.test_telegram:
        if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
            log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID kosong. Isi .env dulu.")
            sys.exit(1)
        telegram_bot.send_test_message(live)
        log.info("Pesan tes Telegram terkirim. Kredensial valid.")
        sys.exit(0)

    users = database.fetch_users()
    has_user_keys = any(u["api_key"] and u["secret_key"] for u in users)
    if live and not ((config.BINGX_API_KEY and config.BINGX_SECRET_KEY) or has_user_keys):
        log.error("Mode live dipilih tetapi tidak ada kredensial BingX (env maupun Supabase). Jalankan dengan --dry-run.")
        sys.exit(1)
    if live:
        log.warning(
            "MODE LIVE: order bracket terisolasi akan dikirim ke %s untuk user dengan mode otomatis aktif.",
            executor.execution_env_label(),
        )

    if args.loop:
        run_loop(live, args.user)
        return

    try:
        scan_once(live, args.user)
    except Exception as exc:
        log.error("Scan gagal: %s", _one_line(exc))
        try:
            telegram_bot.send_message(telegram_bot.build_error_html(_one_line(exc), "live" if live else "dry-run"))
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
