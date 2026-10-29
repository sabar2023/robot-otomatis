import datetime as dt

import requests

import config
import database
import telegram_bot


def _coin():
    return config.MARGIN_COIN


def _fetch_closed(user_id, since=None, until=None):
    cols = "id,symbol,direction,entry_price,sl_price,tp_price,pnl,closed_at"
    url = f"{database._url()}/rest/v1/trade_history?select={cols}&user_id=eq.{user_id}&status=eq.closed"
    if since:
        url += f"&closed_at=gte.{since}"
    if until:
        url += f"&closed_at=lt.{until}"
    url += "&order=closed_at.desc&limit=500"
    try:
        resp = requests.get(url, headers=database._headers(database._service_key()), timeout=20)
        if resp.status_code == 200:
            return resp.json()
        return []
    except Exception:
        return []


def _fmt_money(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return "?"
    return f"{value:+,.2f}"


def trade_close_message(row):
    pnl = row.get("pnl")
    try:
        pnl = float(pnl) if pnl is not None else None
    except (TypeError, ValueError):
        pnl = None
    if pnl is None:
        return None
    hit = "TP" if pnl > 0 else "SL"
    emoji = "&#9989;" if pnl > 0 else "&#128308;"
    lines = [
        f"{emoji} <b>TRADE CLOSED [{hit}]</b>",
        f"&#128200; {row.get('symbol')} | {row.get('direction')}",
        f"Entry: {row.get('entry_price')} | SL: {row.get('sl_price')} | TP: {row.get('tp_price')}",
        f"&#128176; PnL: {_fmt_money(pnl)} {_coin()}",
    ]
    closed = row.get("closed_at")
    if closed:
        lines.append(f"Closing: {str(closed).replace('T', ' ')[:16]} UTC")
    return "\n".join(lines)


def send_trade_close(row, user):
    msg = trade_close_message(row)
    if not msg:
        return
    telegram_bot.send_message(msg)
    user_chat = (user.get("tg_chat_id") or "").strip()
    if user_chat and user_chat != config.TELEGRAM_CHAT_ID:
        telegram_bot.send_message(msg, chat_id=user_chat)


def _aggregate(rows):
    pnls = []
    for r in rows:
        try:
            v = float(r.get("pnl"))
        except (TypeError, ValueError):
            continue
        pnls.append(v)
    if not pnls:
        return None
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    return {
        "n": len(pnls),
        "wins": len(wins),
        "losses": len(losses),
        "winrate": len(wins) / len(pnls) * 100.0,
        "total": sum(pnls),
        "avg": sum(pnls) / len(pnls),
        "best": max(pnls),
        "worst": min(pnls),
        "pf": sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else float("inf"),
    }


def period_message(user, label, stats):
    lines = [
        f"&#128202; <b>LAPORAN {label.upper()}</b>",
        f"&#128100; User: {user.get('nama') or user.get('email')}",
        f"Trade: <b>{stats['n']}</b> | Win: {stats['wins']} | Loss: {stats['losses']}",
        f"Winrate: <b>{stats['winrate']:.1f}%</b>",
        f"Total PnL: <b>{_fmt_money(stats['total'])} {_coin()}</b>",
        f"Rata-rata/trade: {_fmt_money(stats['avg'])} {_coin()}",
        f"Profit factor: {stats['pf']:.2f}",
        f"Terbaik: {_fmt_money(stats['best'])} | Terburuk: {_fmt_money(stats['worst'])}",
    ]
    return "\n".join(lines)


def send_period_report(users, label, days):
    now = dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(days=days)).isoformat()
    for user in users:
        rows = _fetch_closed(user["id"], since=since)
        stats = _aggregate(rows)
        if not stats or stats["n"] == 0:
            continue
        msg = period_message(user, label, stats)
        try:
            telegram_bot.send_message(msg)
            user_chat = (user.get("tg_chat_id") or "").strip()
            if user_chat and user_chat != config.TELEGRAM_CHAT_ID:
                telegram_bot.send_message(msg, chat_id=user_chat)
        except Exception:
            pass


def send_due_reports(users):
    if not users:
        return
    now = dt.datetime.now(dt.timezone.utc)
    if now.hour != 0:
        return
    if now.weekday() == 0:
        send_period_report(users, "mingguan", 7)
    if now.day == 1:
        send_period_report(users, "bulanan", 30)
