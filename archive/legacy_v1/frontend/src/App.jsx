import { useEffect, useMemo, useState } from 'react'

const fmt = (n, d = 2) => Number(n || 0).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
const money = (n) => `$${fmt(n, 2)}`
const pct = (n) => `${Number(n || 0) >= 0 ? '+' : ''}${fmt(n, 2)}%`

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

function badgeClass(action) {
  if (action === 'BUY') return 'buy'
  if (action === 'AVERAGE_DOWN') return 'dca'
  if (action === 'STOP_LOSS') return 'sl'
  if (action === 'TAKE_PROFIT') return 'tp'
  return 'standby'
}

function Spark({ candles }) {
  const closes = (candles || []).map((c) => c.close)
  if (!closes.length) return <div className="chart" />
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const span = max - min || 1
  return (
    <div className="chart">
      {closes.slice(-70).map((v, i) => {
        const h = ((v - min) / span) * 100
        const up = i === 0 || v >= closes.slice(-70)[i - 1]
        return <div key={i} className="bar" style={{ height: `${Math.max(8, h)}%`, background: up ? '#14b8a6' : '#ef4444' }} />
      })}
    </div>
  )
}

function Switch({ on, label, danger, onToggle }) {
  return (
    <label className={`switch ${on ? 'on' : ''} ${danger ? 'danger' : ''}`}>
      <input type="checkbox" checked={on} onChange={onToggle} />
      <span className="track" />
      {label}
    </label>
  )
}

function Settings({ cfg, marketInfo, cloud, exchanges, onSaved }) {
  const [form, setForm] = useState({
    exchange_id: 'binance',
    max_daily_drawdown: 5,
    cycle_seconds: 15,
    worker_url: '',
    worker_token: '',
    api_key: '',
    api_secret: '',
    cloud_sync_enabled: false,
  })
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(() => {
    if (!cfg) return
    setForm((f) => ({
      ...f,
      exchange_id: cfg.exchange_id || 'binance',
      max_daily_drawdown: cfg.max_daily_drawdown ?? 5,
      cycle_seconds: cfg.cycle_seconds ?? 15,
      worker_url: cfg.worker_url || '',
      cloud_sync_enabled: !!cfg.cloud_sync_enabled,
    }))
  }, [cfg])

  const change = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setForm((f) => ({ ...f, [k]: v }))
  }

  const save = async () => {
    setBusy(true)
    setMsg('')
    try {
      const payload = {
        exchange_id: form.exchange_id,
        max_daily_drawdown: Number(form.max_daily_drawdown),
        cycle_seconds: Number(form.cycle_seconds),
        worker_url: form.worker_url,
        cloud_sync_enabled: form.cloud_sync_enabled,
      }
      if (form.worker_token) payload.worker_token = form.worker_token
      if (form.api_key) payload.api_key = form.api_key
      if (form.api_secret) payload.api_secret = form.api_secret
      await api('/api/config', { method: 'POST', body: JSON.stringify(payload) })
      setForm((f) => ({ ...f, api_key: '', api_secret: '', worker_token: '' }))
      setMsg('Pengaturan tersimpan.')
      onSaved && onSaved()
    } catch (e) {
      setMsg('Gagal menyimpan pengaturan.')
    } finally {
      setBusy(false)
    }
  }

  const liveReady = exchanges?.status?.live_ready
  const publicOk = exchanges?.status?.public_ok

  return (
    <section className="card" style={{ marginTop: 16 }}>
      <h2>Pengaturan Sistem & Cloudflare</h2>
      <div className="settings-grid">
        <div className="field">
          <label>Exchange (CCXT)</label>
          <select value={form.exchange_id} onChange={change('exchange_id')}>
            {(exchanges?.supported || ['binance', 'okx']).map((x) => (
              <option key={x} value={x}>{x}</option>
            ))}
          </select>
          <div className="log-meta">
            Public data: {publicOk ? 'OK' : 'fallback simulator'} · Live order: {liveReady ? 'READY' : 'butuh API key'}
          </div>
        </div>
        <div className="field">
          <label>Batas Drawdown Harian (%)</label>
          <input type="number" step="0.5" value={form.max_daily_drawdown} onChange={change('max_daily_drawdown')} />
        </div>
        <div className="field">
          <label>Interval Siklus (detik)</label>
          <input type="number" min="5" value={form.cycle_seconds} onChange={change('cycle_seconds')} />
          <div className="log-meta">PRD interval produksi: 900 detik (15 menit)</div>
        </div>
        <div className="field">
          <label>Cloudflare Worker URL</label>
          <input type="text" placeholder="https://brandbisnis-worker.xxx.workers.dev" value={form.worker_url} onChange={change('worker_url')} />
        </div>
        <div className="field">
          <label>Worker Token {cfg?.worker_token ? `(tersimpan: ${cfg.worker_token})` : ''}</label>
          <input type="password" placeholder="Bearer token" value={form.worker_token} onChange={change('worker_token')} />
        </div>
        <div className="field">
          <label>Exchange API Key {cfg?.has_api_key ? '(tersimpan)' : ''}</label>
          <input type="password" placeholder="API key" value={form.api_key} onChange={change('api_key')} />
        </div>
        <div className="field">
          <label>Exchange API Secret {cfg?.has_api_secret ? '(tersimpan)' : ''}</label>
          <input type="password" placeholder="API secret" value={form.api_secret} onChange={change('api_secret')} />
        </div>
        <div className="field">
          <label>Sinkronisasi Cloud (D1)</label>
          <label className="switch" style={{ width: 'fit-content' }}>
            <input type="checkbox" checked={form.cloud_sync_enabled} onChange={change('cloud_sync_enabled')} />
            <span className="track" />
            {form.cloud_sync_enabled ? 'ON' : 'OFF'}
          </label>
        </div>
      </div>
      <div className="settings-actions">
        <button className="btn" onClick={save} disabled={busy}>{busy ? 'Menyimpan...' : 'Simpan Pengaturan'}</button>
        <span className="log-meta">Market: {marketInfo?.source || '-'} · Cloud sync: {cloud?.last_status || 'IDLE'}</span>
        {msg ? <span className="log-meta">{msg}</span> : null}
      </div>
    </section>
  )
}

export default function App() {
  const [overview, setOverview] = useState(null)
  const [trades, setTrades] = useState([])
  const [logs, setLogs] = useState([])
  const [positions, setPositions] = useState([])
  const [candles, setCandles] = useState([])
  const [pair, setPair] = useState('BTC/USDT')
  const [error, setError] = useState('')
  const [exchanges, setExchanges] = useState(null)

  const load = async () => {
    try {
      const [ov, tr, lg, pos, mkt, ex] = await Promise.all([
        api('/api/overview'),
        api('/api/trades'),
        api('/api/logs'),
        api('/api/positions'),
        api(`/api/market?pair=${encodeURIComponent(pair)}`),
        api('/api/exchanges'),
      ])
      setOverview(ov)
      setTrades(tr)
      setLogs(lg)
      setPositions(pos)
      setCandles(mkt.candles || [])
      setExchanges(ex)
      setError('')
    } catch (e) {
      setError('Engine belum siap. Menunggu API...')
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, 4000)
    return () => clearInterval(id)
  }, [pair])

  const cfg = overview?.config
  const acc = overview?.account
  const tickers = overview?.tickers || {}
  const kill = !!cfg?.global_kill_switch
  const live = cfg?.execution_mode === 'LIVE'
  const running = !!overview?.engine?.running

  const setMode = async (nextLive) => {
    await api('/api/config', { method: 'POST', body: JSON.stringify({ execution_mode: nextLive ? 'LIVE' : 'PAPER' }) })
    load()
  }
  const setKill = async (next) => {
    await api('/api/config', { method: 'POST', body: JSON.stringify({ global_kill_switch: next }) })
    load()
  }
  const setEngine = async (next) => {
    await api('/api/engine', { method: 'POST', body: JSON.stringify({ running: next }) })
    load()
  }

  const dailyClass = (acc?.daily_pnl_pct || 0) >= 0 ? 'pos' : 'neg'

  const agents = useMemo(() => {
    const latest = {}
    for (const log of logs) {
      if (!latest[log.agent]) latest[log.agent] = log
    }
    return ['ORCHESTRATOR', 'PATTERN', 'DCA', 'RISK'].map((name) => latest[name] || { agent: name, message: 'Menunggu siklus...', timestamp: '-' })
  }, [logs])

  return (
    <>
      <header className="topbar">
        <div className="brand">
          <h1>BrandBisnis Robot Trading</h1>
          <p>
            <span className={`status-dot ${running && !kill ? '' : 'off'}`} />
            Multi-agent AI · {overview?.market?.source || 'SIMULATOR'} · Cloud {overview?.cloud?.last_status || 'IDLE'} · {running ? 'Engine 24/7 aktif' : 'Engine pause'} {error ? `· ${error}` : ''}
          </p>
        </div>
        <div className="controls">
          <Switch on={running} label={running ? 'Engine ON' : 'Engine OFF'} onToggle={() => setEngine(!running)} />
          <Switch on={live} label={live ? 'LIVE' : 'PAPER'} onToggle={() => setMode(!live)} />
          <Switch danger on={kill} label={kill ? 'KILL LOCKED' : 'Kill Switch'} onToggle={() => setKill(!kill)} />
          <button className="btn ghost" onClick={() => api('/api/cycle', { method: 'POST' }).then(load)}>Jalankan Siklus</button>
          <a className="btn" href="/api/export.csv">Export CSV</a>
        </div>
      </header>

      <section className="kpis">
        <div className="card">
          <div className="label">Equity</div>
          <div className="value">{money(acc?.equity)}</div>
          <div className="sub">Cash {money(acc?.cash)} · Mode {cfg?.execution_mode || 'PAPER'}</div>
        </div>
        <div className="card">
          <div className="label">PnL Harian</div>
          <div className={`value ${dailyClass}`}>{pct(acc?.daily_pnl_pct)}</div>
          <div className="sub">Batas drawdown {fmt(cfg?.max_daily_drawdown, 1)}%</div>
        </div>
        <div className="card">
          <div className="label">PnL Total</div>
          <div className={`value ${(acc?.total_pnl_pct || 0) >= 0 ? 'pos' : 'neg'}`}>{pct(acc?.total_pnl_pct)}</div>
          <div className="sub">Modal awal {money(acc?.starting_balance)}</div>
        </div>
        <div className="card">
          <div className="label">Posisi Terbuka</div>
          <div className="value">{acc?.open_positions || 0}</div>
          <div className="sub">Bracket TP/SL wajib di setiap order</div>
        </div>
      </section>

      <Settings cfg={cfg} marketInfo={overview?.market} cloud={overview?.cloud} exchanges={exchanges} onSaved={load} />

      <section className="grid">
        <div className="card">
          <h2>Pasar · {pair}</h2>
          <div className="tickers" style={{ marginBottom: 16 }}>
            {Object.values(tickers).map((t) => (
              <button key={t.pair} className="ticker" onClick={() => setPair(t.pair)} style={{ textAlign: 'left', cursor: 'pointer', border: t.pair === pair ? '1px solid #14b8a6' : '1px solid transparent' }}>
                <b>{t.pair}</b>
                <span>{fmt(t.price, t.price > 100 ? 2 : 4)}</span>
                <div className={t.change_pct >= 0 ? 'pos' : 'neg'}>{pct(t.change_pct)}</div>
              </button>
            ))}
          </div>
          <Spark candles={candles} />
        </div>
        <div className="card">
          <h2>Status Agen</h2>
          {agents.map((a) => (
            <div className="log-row" key={a.agent}>
              <b>{a.agent}</b>
              <div>{a.message}</div>
              <div className="log-meta">{a.timestamp}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid-3">
        <div className="card">
          <h2>Posisi Aktif</h2>
          {positions.length === 0 ? <div className="sub">Tidak ada posisi terbuka.</div> : (
            <table className="table">
              <thead>
                <tr><th>Pair</th><th>Avg</th><th>Mark</th><th>PnL</th><th>SL / TP</th></tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.id}>
                    <td>{p.asset_pair}<div className="log-meta">DCA {p.dca_levels}/3 · qty {p.quantity}</div></td>
                    <td>{fmt(p.avg_price, 4)}</td>
                    <td>{fmt(p.mark_price, 4)}</td>
                    <td className={p.unrealized_pnl >= 0 ? 'pos' : 'neg'}>{pct(p.unrealized_pnl_pct)}</td>
                    <td>{fmt(p.stop_loss, 4)}<div className="log-meta">{fmt(p.take_profit, 4)}</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="card">
          <h2>Log Transaksi AI</h2>
          <div className="logs">
            {trades.slice(0, 20).map((t) => (
              <div className="log-row" key={t.log_id}>
                <span className={`badge ${badgeClass(t.action)}`}>{t.action}</span>
                {' '}{t.asset_pair} · {t.mode}
                <div className="reason">{t.ai_reason}</div>
                <div className="log-meta">{t.timestamp} · score {fmt(t.score, 1)} · PnL {pct(t.profit_loss)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <h2>Terminal Agen</h2>
          <div className="logs">
            {logs.slice(0, 24).map((l) => (
              <div className="log-row" key={l.id}>
                <b>{l.agent}</b>
                {l.level !== 'INFO' ? <span className="badge sl">{l.level}</span> : null}
                <div>{l.message}</div>
                <div className="log-meta">{l.timestamp}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </>
  )
}
