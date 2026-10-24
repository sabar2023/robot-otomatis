import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "brandbisnis.db"


def utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS system_config (
            id INTEGER PRIMARY KEY,
            execution_mode TEXT NOT NULL CHECK(execution_mode IN ('PAPER', 'LIVE')),
            global_kill_switch INTEGER DEFAULT 0,
            max_daily_drawdown FLOAT DEFAULT 5.0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trade_logs (
            log_id TEXT PRIMARY KEY,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            asset_pair TEXT NOT NULL,
            action TEXT NOT NULL,
            ai_reason TEXT NOT NULL,
            mode TEXT NOT NULL,
            profit_loss FLOAT DEFAULT 0.0,
            price FLOAT DEFAULT 0.0,
            quantity FLOAT DEFAULT 0.0,
            agent TEXT DEFAULT 'ORCHESTRATOR',
            score FLOAT DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            asset_pair TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price FLOAT NOT NULL,
            quantity FLOAT NOT NULL,
            stop_loss FLOAT NOT NULL,
            take_profit FLOAT NOT NULL,
            dca_levels INTEGER DEFAULT 0,
            avg_price FLOAT NOT NULL,
            unrealized_pnl FLOAT DEFAULT 0.0,
            status TEXT DEFAULT 'OPEN',
            opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            closed_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            agent TEXT NOT NULL,
            level TEXT DEFAULT 'INFO',
            message TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS equity_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            equity FLOAT NOT NULL,
            daily_pnl FLOAT DEFAULT 0.0,
            drawdown FLOAT DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY,
            starting_balance FLOAT DEFAULT 10000.0,
            cash FLOAT DEFAULT 10000.0,
            equity FLOAT DEFAULT 10000.0,
            daily_start_equity FLOAT DEFAULT 10000.0,
            daily_date TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    _migrate(cur)
    cur.execute("SELECT COUNT(*) AS c FROM system_config")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO system_config (id, execution_mode, global_kill_switch, max_daily_drawdown) VALUES (1, 'PAPER', 0, 5.0)"
        )
    cur.execute("SELECT COUNT(*) AS c FROM account")
    if cur.fetchone()["c"] == 0:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        cur.execute(
            "INSERT INTO account (id, starting_balance, cash, equity, daily_start_equity, daily_date) VALUES (1, 10000.0, 10000.0, 10000.0, 10000.0, ?)",
            (today,),
        )
    conn.commit()
    conn.close()


def _has_column(cur, table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def _add_column(cur, table, column, ddl):
    if not _has_column(cur, table, column):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _migrate(cur):
    _add_column(cur, "system_config", "exchange_id", "TEXT DEFAULT 'binance'")
    _add_column(cur, "system_config", "cycle_seconds", "INTEGER DEFAULT 15")
    _add_column(cur, "system_config", "worker_url", "TEXT DEFAULT ''")
    _add_column(cur, "system_config", "worker_token", "TEXT DEFAULT ''")
    _add_column(cur, "system_config", "cloud_sync_enabled", "INTEGER DEFAULT 0")
    _add_column(cur, "system_config", "api_key", "TEXT DEFAULT ''")
    _add_column(cur, "system_config", "api_secret", "TEXT DEFAULT ''")

    _add_column(cur, "positions", "exchange_order_id", "TEXT DEFAULT ''")
    _add_column(cur, "positions", "sl_order_id", "TEXT DEFAULT ''")
    _add_column(cur, "positions", "tp_order_id", "TEXT DEFAULT ''")


def row_to_dict(row):
    if row is None:
        return None
    return dict(row)


def get_config():
    conn = get_conn()
    row = conn.execute("SELECT * FROM system_config WHERE id = 1").fetchone()
    conn.close()
    data = row_to_dict(row)
    data["global_kill_switch"] = bool(data["global_kill_switch"])
    data["cloud_sync_enabled"] = bool(data.get("cloud_sync_enabled"))
    data["has_api_key"] = bool(data.get("api_key"))
    data["has_api_secret"] = bool(data.get("api_secret"))
    data["api_key"] = _mask(data.get("api_key"))
    data["api_secret"] = _mask(data.get("api_secret"))
    data["worker_token"] = _mask(data.get("worker_token"))
    return data


def get_secrets():
    conn = get_conn()
    row = conn.execute("SELECT * FROM system_config WHERE id = 1").fetchone()
    conn.close()
    data = row_to_dict(row) or {}
    return {
        "exchange_id": data.get("exchange_id") or "binance",
        "api_key": data.get("api_key") or "",
        "api_secret": data.get("api_secret") or "",
        "worker_url": data.get("worker_url") or "",
        "worker_token": data.get("worker_token") or "",
        "cloud_sync_enabled": bool(data.get("cloud_sync_enabled")),
        "cycle_seconds": int(data.get("cycle_seconds") or 15),
    }


def _mask(value):
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * 8}{value[-4:]}"


def update_config(**kwargs):
    allowed = {
        "execution_mode",
        "global_kill_switch",
        "max_daily_drawdown",
        "exchange_id",
        "cycle_seconds",
        "worker_url",
        "worker_token",
        "cloud_sync_enabled",
        "api_key",
        "api_secret",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_config()
    if "global_kill_switch" in fields:
        fields["global_kill_switch"] = 1 if fields["global_kill_switch"] else 0
    if "cloud_sync_enabled" in fields:
        fields["cloud_sync_enabled"] = 1 if fields["cloud_sync_enabled"] else 0
    if "cycle_seconds" in fields:
        fields["cycle_seconds"] = max(5, int(fields["cycle_seconds"]))
    fields["updated_at"] = utcnow()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn = get_conn()
    conn.execute(f"UPDATE system_config SET {sets} WHERE id = 1", list(fields.values()))
    conn.commit()
    conn.close()
    return get_config()


def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()
    conn.close()



def get_account():
    conn = get_conn()
    row = conn.execute("SELECT * FROM account WHERE id = 1").fetchone()
    conn.close()
    return row_to_dict(row)


def update_account(**kwargs):
    allowed = {"cash", "equity", "daily_start_equity", "daily_date"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_account()
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn = get_conn()
    conn.execute(f"UPDATE account SET {sets} WHERE id = 1", list(fields.values()))
    conn.commit()
    conn.close()
    return get_account()


def insert_trade_log(asset_pair, action, ai_reason, mode, profit_loss=0.0, price=0.0, quantity=0.0, agent="ORCHESTRATOR", score=0.0):
    log_id = str(uuid.uuid4())
    ts = utcnow()
    conn = get_conn()
    conn.execute(
        """INSERT INTO trade_logs (log_id, timestamp, asset_pair, action, ai_reason, mode, profit_loss, price, quantity, agent, score)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (log_id, ts, asset_pair, action, ai_reason, mode, profit_loss, price, quantity, agent, score),
    )
    conn.commit()
    conn.close()
    return log_id


def list_trade_logs(limit=80):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM trade_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


def insert_agent_log(agent, message, level="INFO"):
    conn = get_conn()
    conn.execute(
        "INSERT INTO agent_logs (timestamp, agent, level, message) VALUES (?, ?, ?, ?)",
        (utcnow(), agent, level, message),
    )
    conn.commit()
    conn.close()


def list_agent_logs(limit=120):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM agent_logs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


def open_positions():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM positions WHERE status = 'OPEN' ORDER BY id DESC").fetchall()
    conn.close()
    return [row_to_dict(r) for r in rows]


def insert_position(asset_pair, side, entry_price, quantity, stop_loss, take_profit, exchange_order_id="", sl_order_id="", tp_order_id=""):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO positions (asset_pair, side, entry_price, quantity, stop_loss, take_profit, dca_levels, avg_price, status, opened_at, exchange_order_id, sl_order_id, tp_order_id)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, 'OPEN', ?, ?, ?, ?)""",
        (asset_pair, side, entry_price, quantity, stop_loss, take_profit, entry_price, utcnow(), exchange_order_id, sl_order_id, tp_order_id),
    )
    conn.commit()
    pid = cur.lastrowid
    conn.close()
    return pid


def update_position(pid, **kwargs):
    allowed = {"quantity", "stop_loss", "take_profit", "dca_levels", "avg_price", "unrealized_pnl", "status", "closed_at", "exchange_order_id", "sl_order_id", "tp_order_id"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn = get_conn()
    conn.execute(f"UPDATE positions SET {sets} WHERE id = ?", list(fields.values()) + [pid])
    conn.commit()
    conn.close()


def insert_equity(equity, daily_pnl, drawdown):
    conn = get_conn()
    conn.execute(
        "INSERT INTO equity_snapshots (timestamp, equity, daily_pnl, drawdown) VALUES (?, ?, ?, ?)",
        (utcnow(), equity, daily_pnl, drawdown),
    )
    conn.commit()
    conn.close()


def list_equity(limit=120):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM equity_snapshots ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [row_to_dict(r) for r in reversed(rows)]
