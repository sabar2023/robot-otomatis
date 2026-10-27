import logging

import requests

import config

log = logging.getLogger("brandbisnis_vst")


def _url():
    return config.SUPABASE_URL.rstrip("/")


def is_configured():
    return bool(config.SUPABASE_URL and config.SUPABASE_KEY)


def _headers():
    return {
        "apikey": config.SUPABASE_KEY,
        "Authorization": f"Bearer {config.SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _err_text(exc):
    text = str(exc) or exc.__class__.__name__
    return text.splitlines()[0][:120]


def _post(table, payload):
    if not is_configured():
        return
    try:
        resp = requests.post(f"{_url()}/rest/v1/{table}", headers=_headers(), json=payload, timeout=15)
        if resp.status_code >= 300:
            log.warning("Supabase %s: HTTP %s %s", table, resp.status_code, resp.text[:150])
    except Exception as exc:
        log.warning("Supabase %s gagal: %s", table, _err_text(exc))


def log_scan(symbol, mode, result, source):
    status = f"SINYAL {result['direction']}" if result["passed"] else "STANDBY"
    _post(
        "ro_scans",
        {
            "symbol": symbol,
            "mode": mode,
            "status": status,
            "price": float(result["price"]),
            "atr": float(result["atr"]),
            "candle_open": result["candle_open"].isoformat(),
            "source": source,
            "layers": result["layers"],
            "failed_layers": result["failed_layers"],
        },
    )


def log_execution(symbol, mode, levels, execution):
    _post(
        "ro_executions",
        {
            "symbol": symbol,
            "mode": mode,
            "direction": levels["direction"],
            "executed": bool(execution.get("executed")),
            "side": execution.get("side"),
            "amount": execution.get("amount"),
            "order_id": execution.get("order_id"),
            "entry": float(levels["entry"]),
            "stop_loss": float(levels["stop_loss"]),
            "take_profit": float(levels["take_profit"]),
            "detail": execution.get("detail"),
        },
    )


def auto_enabled():
    if not is_configured():
        return True
    try:
        resp = requests.get(
            f"{_url()}/rest/v1/ro_config?key=eq.auto_trading&select=value",
            headers=_headers(),
            timeout=15,
        )
        if resp.status_code == 200:
            rows = resp.json()
            if isinstance(rows, list) and rows:
                value = rows[0].get("value")
                if isinstance(value, dict):
                    value = value.get("enabled")
                return bool(value)
    except Exception as exc:
        log.warning("Supabase ro_config tidak terbaca: %s", _err_text(exc))
    return True