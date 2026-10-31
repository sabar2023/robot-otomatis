import datetime as dt
import logging

import requests

import database
import executor
import reporting

log = logging.getLogger("brandbisnis_vst")


def _open_side_map(exchange):
    result = {}
    try:
        for p in exchange.fetch_positions():
            if float(p.get("contracts") or 0) > 0:
                result[p["symbol"]] = str(p.get("side") or "").lower()
    except Exception as exc:
        log.warning("fetch_positions saat sync PnL gagal: %s", str(exc).splitlines()[0][:120])
        return None
    return result


def fetch_open_trades(user_id):
    if not database.is_configured() or not user_id:
        return []
    try:
        resp = requests.get(
            f"{database._url()}/rest/v1/trade_history?select=id,symbol,direction,executed_at,entry_price,sl_price,tp_price,quantity,margin_used,leverage&user_id=eq.{user_id}&status=eq.open&order=executed_at.desc&limit=50",
            headers=database._headers(database._service_key()),
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        log.warning("trade_history open user %s: HTTP %s %s", user_id, resp.status_code, resp.text[:120])
    except Exception as exc:
        log.warning("Baca trade_history open user %s gagal: %s", user_id, str(exc).splitlines()[0][:120])
    return []


def close_trade(trade_id, pnl, closed_at):
    try:
        resp = requests.patch(
            f"{database._url()}/rest/v1/trade_history?id=eq.{trade_id}",
            headers=database._headers(database._service_key()),
            json={"pnl": pnl, "closed_at": closed_at, "status": "closed"},
            timeout=15,
        )
        if resp.status_code >= 300:
            log.warning("Update trade tertutup id=%s: HTTP %s %s", trade_id, resp.status_code, resp.text[:120])
    except Exception as exc:
        log.warning("Update trade tertutup id=%s gagal: %s", trade_id, str(exc).splitlines()[0][:120])


def _exec_ms(row):
    return int(dt.datetime.fromisoformat(row["executed_at"]).timestamp() * 1000)


def sync_closed_trades(user):
    open_rows = fetch_open_trades(user["id"])
    if not open_rows:
        return 0
    if not (user["api_key"] and user["secret_key"]):
        return 0
    try:
        exchange = executor.build_trading_exchange(user["api_key"], user["secret_key"])
    except Exception as exc:
        log.warning("Sync PnL %s - exchange gagal: %s", user["email"], str(exc).splitlines()[0][:120])
        return 0

    closed_map = {}
    symbols = sorted({r["symbol"] for r in open_rows})
    now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    since_ms = now_ms - 90 * 86400 * 1000
    open_map = _open_side_map(exchange)
    if open_map is None:
        return 0
    for sym in symbols:
        try:
            hist = exchange.fetch_position_history(sym, since=since_ms, limit=100, params={"until": now_ms})
        except Exception as exc:
            log.warning("Position history %s gagal: %s", sym, str(exc).splitlines()[0][:120])
            continue
        for h in hist or []:
            info = h.get("info") or {}
            ts = info.get("updateTime") or h.get("last") or h.get("timestamp")
            if not ts:
                continue
            try:
                ts = int(ts)
            except (TypeError, ValueError):
                continue
            closed_map.setdefault((h["symbol"], str(h.get("side") or "").lower()), []).append({"h": h, "ts": ts})

    closed_count = 0
    for row in open_rows:
        if open_map.get(row["symbol"]) == row["direction"].lower():
            continue
        key = (row["symbol"], row["direction"].lower())
        candidates = [c for c in closed_map.get(key, []) if c["ts"] >= _exec_ms(row) - 60000]
        if not candidates:
            continue
        best = max(candidates, key=lambda c: c["ts"])
        total = 0.0
        found = False
        for cand in candidates:
            info = cand["h"].get("info") or {}
            value = info.get("netProfit")
            if value is None:
                value = info.get("realisedProfit")
            if value is None:
                value = cand["h"].get("pnl")
            try:
                number = float(value) if value is not None else None
            except (TypeError, ValueError):
                number = None
            if number is not None:
                total += number
                found = True
        pnl_val = total if found else None
        closed_iso = dt.datetime.fromtimestamp(best["ts"] / 1000, dt.timezone.utc).isoformat()
        close_trade(row["id"], pnl_val, closed_iso)
        closed_count += 1
        log.info("PnL close %s %s id=%s pnl=%s", row["symbol"], row["direction"], row["id"], pnl_val)
        try:
            reporting.send_trade_close(
                {
                    "symbol": row["symbol"],
                    "direction": row["direction"].upper(),
                    "entry_price": row.get("entry_price"),
                    "sl_price": row.get("sl_price"),
                    "tp_price": row.get("tp_price"),
                    "margin_used": row.get("margin_used"),
                    "leverage": row.get("leverage"),
                    "pnl": pnl_val,
                    "closed_at": closed_iso,
                },
                user,
            )
        except Exception as exc:
            log.warning("Kirim notif close gagal: %s", str(exc).splitlines()[0][:120])
    return closed_count


def sync_all(users, live):
    if not live:
        return 0
    total = 0
    for user in users:
        if not (user["api_key"] and user["secret_key"]):
            continue
        try:
            total += sync_closed_trades(user)
        except Exception as exc:
            log.warning("Sync PnL user %s gagal: %s", user["email"], str(exc).splitlines()[0][:120])
    return total
