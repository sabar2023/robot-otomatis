import datetime as dt
import logging

import requests
from cryptography.fernet import Fernet

import config

log = logging.getLogger("brandbisnis_vst")


def _url():
    return config.SUPABASE_URL.rstrip("/")


def is_configured():
    return bool(config.SUPABASE_URL and (config.SUPABASE_KEY or config.SUPABASE_SERVICE_KEY))


def _headers(key=None):
    token = key or config.SUPABASE_KEY or config.SUPABASE_SERVICE_KEY
    return {
        "apikey": token,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _service_key():
    return config.SUPABASE_SERVICE_KEY or config.SUPABASE_KEY


def _err_text(exc):
    text = str(exc) or exc.__class__.__name__
    return text.splitlines()[0][:120]


def _post(table, payload, key=None):
    if not is_configured():
        return
    try:
        resp = requests.post(f"{_url()}/rest/v1/{table}", headers=_headers(key), json=payload, timeout=15)
        if resp.status_code >= 300:
            log.warning("Supabase %s: HTTP %s %s", table, resp.status_code, resp.text[:150])
    except Exception as exc:
        log.warning("Supabase %s gagal: %s", table, _err_text(exc))


def _fernet():
    if not config.SETTINGS_ENC_KEY:
        return None
    return Fernet(config.SETTINGS_ENC_KEY.encode())


def encrypt_secret(value):
    if not value:
        return value
    key = _fernet()
    if not key:
        return value
    return key.encrypt(value.encode()).decode()


def decrypt_secret(value):
    if not value:
        return value
    if value.startswith("gAAAAA"):
        key = _fernet()
        if not key:
            raise RuntimeError("SETTINGS_ENC_KEY kosong - tidak bisa mendekripsi API key")
        return key.decrypt(value.encode()).decode()
    return value


def _store_encrypted(user_id, api_key, secret_key):
    if not is_configured() or not _fernet() or not user_id:
        return
    payload = {"updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    if api_key:
        payload["api_key_encrypted"] = encrypt_secret(api_key)
    if secret_key:
        payload["secret_key_encrypted"] = encrypt_secret(secret_key)
    try:
        resp = requests.patch(
            f"{_url()}/rest/v1/user_settings?user_id=eq.{user_id}",
            headers=_headers(_service_key()),
            json=payload,
            timeout=15,
        )
        if resp.status_code >= 300:
            log.warning("Migrasi enkripsi user %s: HTTP %s", user_id, resp.status_code)
    except Exception as exc:
        log.warning("Migrasi enkripsi user %s gagal: %s", user_id, _err_text(exc))


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


def log_trade(user_id, symbol, levels, execution):
    _post(
        "trade_history",
        {
            "user_id": user_id,
            "symbol": symbol,
            "direction": levels["direction"],
            "entry_price": float(levels["entry"]),
            "sl_price": float(levels["stop_loss"]),
            "tp_price": float(levels["take_profit"]),
            "leverage": levels["leverage"],
            "quantity": execution.get("amount"),
            "margin_used": execution.get("margin_used"),
            "pnl": None,
            "status": "open" if execution.get("executed") else "simulated",
            "order_id": execution.get("order_id"),
        },
        key=_service_key(),
    )


def fetch_users():
    if not is_configured():
        return []
    try:
        resp = requests.get(
            f"{_url()}/rest/v1/user_settings?select=*,users_profile(email,nama)",
            headers=_headers(_service_key()),
            timeout=15,
        )
        if resp.status_code != 200:
            log.warning("Supabase user_settings: HTTP %s %s", resp.status_code, resp.text[:150])
            return []
        users = []
        for row in resp.json():
            profile = row.get("users_profile") or {}
            user_id = row.get("user_id")
            email = (profile.get("email") or "?")
            raw_api = row.get("api_key_encrypted") or ""
            raw_sec = row.get("secret_key_encrypted") or ""
            try:
                api_key = (decrypt_secret(raw_api) or "").strip()
                secret_key = (decrypt_secret(raw_sec) or "").strip()
            except Exception as exc:
                log.warning("Gagal dekripsi API key user %s: %s", email, _err_text(exc))
                continue
            if _fernet() and ((raw_api and not raw_api.startswith("gAAAAA")) or (raw_sec and not raw_sec.startswith("gAAAAA"))):
                _store_encrypted(user_id, api_key, secret_key)
            users.append(
                {
                    "id": user_id,
                    "email": email,
                    "nama": profile.get("nama") or email,
                    "api_key": api_key,
                    "secret_key": secret_key,
                    "mode_otomatis": bool(row.get("mode_otomatis")),
                    "coins": [s.strip() for s in (row.get("koin_pilihan") or []) if s and s.strip()],
                    "margin_pct": row.get("margin_persen"),
                    "leverage": row.get("leverage"),
                    "tp_pct": row.get("tp_persen"),
                    "sl_pct": row.get("sl_persen"),
                    "tg_chat_id": row.get("tg_chat_id"),
                }
            )
        return users
    except Exception as exc:
        log.warning("Supabase user_settings gagal: %s", _err_text(exc))
        return []


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
