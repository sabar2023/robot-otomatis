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

CREATE INDEX IF NOT EXISTS idx_trade_logs_ts ON trade_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_id ON agent_logs (id DESC);

INSERT OR IGNORE INTO system_config (id, execution_mode, global_kill_switch, max_daily_drawdown)
VALUES (1, 'PAPER', 0, 5.0);
