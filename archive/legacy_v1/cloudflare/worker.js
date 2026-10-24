export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type,Authorization",
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });

    const json = (data, status = 200) => Response.json(data, { status, headers: cors });

    const authorized = () => {
      if (!env.WORKER_TOKEN) return true;
      const auth = request.headers.get("Authorization") || "";
      return auth === `Bearer ${env.WORKER_TOKEN}`;
    };

    if (url.pathname === "/api/health") {
      return json({ status: "ok", service: "brandbisnis-worker", ts: new Date().toISOString() });
    }

    if (url.pathname.startsWith("/api/") && !authorized()) {
      return json({ error: "unauthorized" }, 401);
    }

    try {
      if (url.pathname === "/api/config" && request.method === "GET") {
        const row = await env.DB.prepare("SELECT * FROM system_config WHERE id = 1").first();
        return json(row);
      }

      if (url.pathname === "/api/config" && request.method === "POST") {
        const body = await request.json();
        await env.DB.prepare(
          `UPDATE system_config SET
             execution_mode = COALESCE(?, execution_mode),
             global_kill_switch = COALESCE(?, global_kill_switch),
             max_daily_drawdown = COALESCE(?, max_daily_drawdown),
             updated_at = CURRENT_TIMESTAMP
           WHERE id = 1`
        )
          .bind(
            body.execution_mode ?? null,
            body.global_kill_switch === undefined ? null : body.global_kill_switch ? 1 : 0,
            body.max_daily_drawdown ?? null
          )
          .run();
        const row = await env.DB.prepare("SELECT * FROM system_config WHERE id = 1").first();
        return json(row);
      }

      if (url.pathname === "/api/trades" && request.method === "GET") {
        const limit = Number(url.searchParams.get("limit") || 80);
        const { results } = await env.DB.prepare(
          "SELECT * FROM trade_logs ORDER BY timestamp DESC LIMIT ?"
        )
          .bind(limit)
          .all();
        return json(results);
      }

      if (url.pathname === "/api/trades" && request.method === "POST") {
        const body = await request.json();
        await env.DB.prepare(
          `INSERT INTO trade_logs (log_id, timestamp, asset_pair, action, ai_reason, mode, profit_loss, price, quantity, agent, score)
           VALUES (?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        )
          .bind(
            body.log_id, body.timestamp ?? null, body.asset_pair, body.action, body.ai_reason,
            body.mode, body.profit_loss || 0, body.price || 0, body.quantity || 0,
            body.agent || "ORCHESTRATOR", body.score || 0
          )
          .run();
        return json({ ok: true });
      }

      if (url.pathname === "/api/trades/batch" && request.method === "POST") {
        const { trades } = await request.json();
        if (!Array.isArray(trades) || trades.length === 0) return json({ ok: true, inserted: 0 });
        const stmt = env.DB.prepare(
          `INSERT OR REPLACE INTO trade_logs (log_id, timestamp, asset_pair, action, ai_reason, mode, profit_loss, price, quantity, agent, score)
           VALUES (?, COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?, ?, ?, ?, ?, ?, ?)`
        );
        const batch = trades.map((t) =>
          stmt.bind(
            t.log_id, t.timestamp ?? null, t.asset_pair, t.action, t.ai_reason, t.mode,
            t.profit_loss || 0, t.price || 0, t.quantity || 0, t.agent || "ORCHESTRATOR", t.score || 0
          )
        );
        await env.DB.batch(batch);
        return json({ ok: true, inserted: batch.length });
      }

      if (url.pathname === "/api/logs/batch" && request.method === "POST") {
        const { logs } = await request.json();
        if (!Array.isArray(logs) || logs.length === 0) return json({ ok: true, inserted: 0 });
        const stmt = env.DB.prepare(
          "INSERT INTO agent_logs (timestamp, agent, level, message) VALUES (COALESCE(?, CURRENT_TIMESTAMP), ?, ?, ?)"
        );
        const batch = logs.map((l) => stmt.bind(l.timestamp ?? null, l.agent, l.level || "INFO", l.message));
        await env.DB.batch(batch);
        return json({ ok: true, inserted: batch.length });
      }

      if (url.pathname === "/api/logs" && request.method === "GET") {
        const limit = Number(url.searchParams.get("limit") || 120);
        const { results } = await env.DB.prepare(
          "SELECT * FROM agent_logs ORDER BY id DESC LIMIT ?"
        )
          .bind(limit)
          .all();
        return json(results);
      }

      if (url.pathname === "/api/equity" && request.method === "POST") {
        const body = await request.json();
        await env.DB.prepare(
          "INSERT INTO equity_snapshots (timestamp, equity, daily_pnl, drawdown) VALUES (CURRENT_TIMESTAMP, ?, ?, ?)"
        )
          .bind(body.equity || 0, body.daily_pnl || 0, body.drawdown || 0)
          .run();
        return json({ ok: true });
      }

      if (url.pathname === "/api/equity" && request.method === "GET") {
        const { results } = await env.DB.prepare(
          "SELECT * FROM equity_snapshots ORDER BY id DESC LIMIT 120"
        ).all();
        return json(results);
      }

      if (url.pathname === "/api/r2/backup" && request.method === "POST") {
        if (!env.BUCKET) return json({ error: "R2 bucket belum di-bind" }, 500);
        const { filename, content } = await request.json();
        const key = `backups/${filename}`;
        await env.BUCKET.put(key, content, {
          httpMetadata: { contentType: "text/csv" },
        });
        return json({ ok: true, key });
      }

      if (url.pathname === "/api/r2/files" && request.method === "GET") {
        if (!env.BUCKET) return json({ error: "R2 bucket belum di-bind" }, 500);
        const list = await env.BUCKET.list({ prefix: "backups/" });
        return json(list.objects.map((o) => ({ key: o.key, size: o.size, uploaded: o.uploaded })));
      }

      return json({ error: "not_found" }, 404);
    } catch (err) {
      return json({ error: String(err) }, 500);
    }
  },
};
