# AGENTS.md — Konteks Kerja untuk Sesi/AI Baru

Proyek ini adalah **signal bot non-execution** (lihat `README.md` untuk detail lengkap
dan `docs/PRD-Signal-Bot-V2.md` untuk PRD asli) plus **platform trading multi-user
V5.0** (folder `vst/`, PRD di `docs/PRD-Robot-Trading-M5-VST.md` = versi H1/multi-user).
Sistem utama berjalan di GitHub Actions yang dipicu Cloudflare Worker tiap 1 jam di
branch `main` — **push ke main = langsung live di produksi**, jadi selalu verifikasi
sebelum push.

## Perintah Utama

```bash
# verifikasi sintaks semua modul
python3 -m py_compile config.py main.py filters.py risk.py telegram_bot.py market_data.py indicators.py vst/config.py vst/indicators.py vst/market_data.py vst/filters.py vst/risk.py vst/executor.py vst/telegram_bot.py vst/database.py vst/watchlist.py vst/main.py

# scan sekali dengan data live, tanpa kirim Telegram
python3 main.py --dry-run

# scan sekali sistem V5.0 multi-user (dry-run, tanpa order)
python3 vst/main.py --dry-run

# scan sekali hanya satu user tertentu (uji per-user)
python3 vst/main.py --dry-run --user email-user@contoh.com

# kirim pesan tes ke grupTelegram (butuh .env terisi)
python3 main.py --test-telegram
python3 vst/main.py --test-telegram

# push lalu uji di produksi (repo: sabar2023/robot-otomatis = sistem V5.0)
git add -A && git commit -m "..." && git push
gh workflow run cron-vst.yml -R sabar2023/robot-otomatis
gh run view <run-id> -R sabar2023/robot-otomatis --log
```

## Pembagian Repo

- `sabar2023/robot-trading` (lama): signal bot 4 koin, workflow `cron.yml`
  (dispatch-only). Sinyal lama **dimatikan** (tidak dipicu Worker); repo tetap
  utuh, bisa dijalankan manual bila diperlukan.
- `sabar2023/robot-otomatis` (baru): sistem **V5.0** (folder `vst/`),
  `cron-vst.yml` (dispatch-only). `cron.yml` (signal bot) di repo baru hanya
  manual.
- Pemicu: Cloudflare Worker `bot-cron` (cron `0 * * * *`, sumber di
  `cloudflare/bot-cron/`) **hanya** dispatch `cron-vst.yml` (robot-otomatis)
  tiap 1 jam. `schedule` GitHub di kedua repo sengaja dimatikan
  (throttle 4-5 jam + anti dobel). Gagal dispatch → alert Telegram otomatis.
  Endpoint manual: `GET https://bot-cron.sabar2023.workers.dev/run?key=<TRIGGER_KEY>`.
  Secret Worker: `GITHUB_PAT` (fine-grained, Actions: write), `TRIGGER_KEY`,
  `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- Database: Supabase project "robot otomatis" (`jklbczruvbxscpwxxfud`).
  Tabel mesin: `ro_scans` (scan per koin), `ro_executions` (per order/simulasi),
  `ro_config` (toggle `auto_trading`). Tabel SaaS V5.0: `users_profile`
  (id, email, nama, no_hp), `user_settings` (API key terenkripsi Fernet,
  `mode_otomatis`, `koin_pilihan[]`, `margin_persen`, `leverage`, `tp_persen`,
  `sl_persen`), `trade_history` (riwayat + PnL per user, `status` open/simulated).
  RLS aktif; engine baca/lintas-user pakai service key, user Flutter baca data
  sendiri via auth. User owner pertama sudah diseed (sabarberkah2017@gmail.com).

## Aturan Proyek

1. Kode **tanpa komentar** (tidak ada docstring tambahan); ikuti gaya file yang ada.
2. **Tidak boleh menghapus file** — arsipkan (contoh: `archive/legacy_v1/`).
3. Jangan menulis nilai rahasia (token Telegram) di file ter-commit; hanya di `.env`
   (gitignored) dan GitHub secrets.
4. Dependensi Python diinstal dengan `pip3 install --break-system-packages`.
5. Bahasa respon/commit message sesuai preferensi pengguna (Indonesia diterima).
6. Ubah konstanta strategi hanya di `config.py`, jangan hardcode duplikat di modul lain.

## Arsitektur yang Penting Dipahami

- `filters.evaluate(symbol, base, higher, btc_base, is_altcoin)` → dict dengan
  `direction` ("LONG"/"SHORT"/None), `layers` (5 dict {name, passed, detail}),
  `failed_layers`. Layer LONG dan SHORT dievaluasi simultan; arah menang = yang
  lolos 5/5. SHORT adalah cermin matematis LONG (lihat `docs/PRD-*.md` untuk aturan
  LONG asli; mirror-nya di `filters.py`).
- Key detail layer 1: `close_base, ema200_base, close_high, ema50_high`.
  Key layer 2 disamakan dua arah: `near_support` (flag zona), `breakout` (flag
  breakout/breakdown), `above_vwap` (flag sisi VWAP). L5 short memakai key
  `support_break` (artinya: BTC breaking resistance) dan `far_below_ema200`
  (artinya: BTC jauh di atas EMA200) — sengaja reuse untuk berbagi kode
  `telegram_bot.build_alert_html`.
- `vst/risk.compute_levels(direction, entry_price, atr_value, sl_pct=None, tp_pct=None, leverage=None, margin_pct=None)`
  → entry, SL, TP. Default (tanpa override user) mengikuti `config.RISK_MODE`
  (`VST_RISK_MODE`, default `pct`): SL `SL_PCT_DEFAULT` 3,0% dan TP `TP_PCT_DEFAULT`
  6,0% (`VST_SL_PCT`/`VST_TP_PCT`), plus **TP parsial** `TP1_PCT` 1,5% untuk
  `TP1_FRACTION` 70% posisi (`VST_TP1_PCT`/`VST_TP1_FRACTION`); TP1 aktif hanya bila
  `TP1_PCT < 0,9 × TP`. Mode `atr` = SL ATR×1.5 clamp 1–4,5%, TP ATR×4 clamp 3–12%.
  Override user (`sl_pct`/`tp_pct`) clamp 0.5–4,5% / 0.5–50%. `leverage` clamp
  5–20x (default 10, `VST_LEVERAGE_MAX`; owner diset 15x). `margin_pct` = porsi
  saldo per order (default 10%). Return: `entry, stop_loss, take_profit, rr, atr,
  sl_distance_pct, tp_distance_pct, tp1, tp1_pct, tp1_fraction, margin_pct, leverage`.
- TP parsial: order entry membawa SL penuh + TP akhir untuk sisa 30%; setelah entry
  `executor._place_partial_tp` memasang TAKE_PROFIT_MARKET reduceOnly 70% di TP1.
  Bila entry dengan TP parsial ditolak bursa → fallback entry SL saja + dua order TP
  terpisah (aman dari dobel entry: dicek `open_positions` dulu). Karena 70%×1,5% >
  30%×3%, trade yang menyentuh TP1 selalu berakhir positif walau sisa kena SL
  (tidak perlu geser SL ke BE).
- Strategi V5.0 H1 = **5 layer tampilan** (semua wajib lolos; isinya gabungan dari
  8 kondisi): L1 Tren Arah (close>EMA200 DAN EMA20≥EMA50 toleransi 0,15%), L2 Pullback
  swing 10 bar +2,0% (support/resistance), L3 Momentum RSI < 40 dan naik (mirror SHORT:
  >60 turun), L4 Kualitas Pasar (volume > SMA20 DAN ADX>20), L5 Tren Harian koin+BTC
  searah (close D1 > EMA50 D1 dan EMA50 D1 naik 3 hari; mirror SHORT). Ouput
  `filters.evaluate` kini mengembalikan 5 `layers` ter-gabung, bukan 8. Data D1 diambil
  `fetch(symbol, "1d", 150)`, candle D1 terakhir dibuang (`closed_candles`), tren BTC
  di-cache sekali per scan. Stack penuh 7>10>20>50 **jangan** dipakai (bentrok entry
  pullback); tren harian (L5) **jangan** dipisah/dihapus — tanpa alignment D1 winrate
  turun drastis.
- Hasil backtest produksi (`vst/backtest.py`, 41 koin × ~6 bulan H1, 8 kondisi =
  5 layer tampilan di atas): **SL 3%/TP 6% + TP1 1,5% (70%)** → ~124 trade,
  **~0,7 sinyal/hari**, winrate total 83%, rata-rata winrate bulanan ~84%,
  +0,7–0,8%/trade, total +87–103%, streak loss maks 6. Winrate >80% TIDAK bisa dicapai
  tiap bulan (bulan minim sinyal bisa 60–70%); yang realistis rata-rata bulanan >80%.
  Menghapus kondisi tren harian / mengurangi jadi 5 kondisi beneran → winrate mentok
  ~73–77% dan sinyal meledak 7/hari. Tanpa TP parsial winrate hanya ~45% (TP penuh).
  Tuning frekuensi (ADX 25→20): ±1,2 sinyal/hari, WR 80%, tapi sinyal tetap
  terdistribusi (hanya ±42% hari ada sinyal) — tidak mungkin "order tiap hari" sambil
  tahan WR >80% karena L5 tren harian BTC memblokir semua koin saat BTC netral.
  Watchlist owner = 40 koin kripto manual (hindari aset tokenized).
- `vst/watchlist.default_watchlist(chain)` → top-N swap USDT (default 5) berdasarkan
  volume 24h dari bursa pertama yang sukses; daftar bisa memuat aset tokenized
  (contoh `NCCOGOLD2USD`) — backtest hanya memvalidasi koin kripto, jadi set
  `koin_pilihan` manual bila ingin menghindari instrumen non-kripto.
- `vst/pnl.sync_all(users, live)`: tiap run, baris `trade_history`
  `status=open` dicocokkan `fetch_position_history` BingX per simbol
  (wajib `params={"until": now_ms}` — API BingX menolak tanpa `endTs`);
  **PnL dijumlahkan dari semua record penutupan** sejak entry (TP1 parsial +
  penutupan akhir), bukan hanya record terakhir; posisi tertutup → PATCH
  `pnl`/`closed_at`, status `closed`.
- Notifikasi: sinyal selalu ke grup utama; bila `user_settings.tg_chat_id`
  terisi → juga ke chat user (`send_message(text, chat_id=None)`). `vst/reporting.py`
  kirim: notif per-transaksi saat close (label TP/SL + PnL), plus laporan otomatis
  **harian** (jam 00:00 UTC, ringkasan 24 jam: sinyal/posisi terbuka/trade tutup/PnL),
  **mingguan** (Senin) dan **bulanan** (tgl 1) — dipicu `reporting.send_due_reports`
  di akhir `scan_once` bila `live`.
- `app/` = aplikasi Flutter resmi (web+android), auth Supabase + RLS;
  `web/dashboard-test/` = prototipe HTML dashboard tes. APK via CI
  `app-apk.yml` (build jalan di Actions, bukan lokal).
- Multi-user: `vst/database.fetch_users()` baca `user_settings` join `users_profile`
  (service key), dekripsi API key Fernet (`SETTINGS_ENC_KEY`; nilai plaintext lama
  tetap terbaca sebagai fallback). Bila DB kosong → fallback akun owner dari env
  `BINGX_API_KEY`/`BINGX_SECRET_KEY`. User `mode_otomatis=false` tetap di-scan
  (sinyal tercatat di `ro_scans`/`trade_history` sebagai simulated) tapi tidak
  ada order live. Eksekusi live juga butuh `ro_config.auto_trading=true`.
- `vst/executor.execute(levels, live, data_source_id, symbol, credentials)` →
  dry-run pakai notional simulasi (`SIMULATED_NOTIONAL_USDT`); live = `ccxt.bingx`
  + `set_sandbox_mode(True)` dengan kredensial per-user, margin mode **isolated**
  (best-effort: `set_margin_mode` → `set_cross_margin(False)`), sizing =
  `saldo free VST × margin_pct% × leverage` (PRD: maksimal 10% margin per
  eksekusi), bracket order `stopLoss`/`takeProfit` + `marginCoin: VST`. Skip entry
  jika posisi terbuka untuk simbol ini.
- `vst/database.log_trade(user_id, symbol, levels, execution)` → `trade_history`
  (`status`: open = order live terkirim, simulated = dry-run/user manual). Kolom
  `pnl`/`closed_at` diisi proses penutupan (belum ada di engine saat ini).
- Timeframe H1: `TIMEFRAME_MINUTES=60`, freshness candle tutup ≤ 90 menit, scan
  1x/jam (Worker `0 * * * *`). Cadence lama M5/5 menit sudah tidak dipakai.
- Signal bot lama (root) tetap memakai `SL_PCT`/`TP_PCT` fixed + leverage 2–10x —
  **jangan** campur konstanta root dengan `vst/config.py`.

## Pitfall Lingkungan (Jangan Diulang)

- **Binance & Bybit = HTTP 451 dari IP GitHub Actions runner.** Lokal (jaringan dev)
  binance sehat. Jangan kaget kalau log produksi "Sumber data: kraken". BingX
  **belum tentu** juga kena 451, jadi `vst/market_data.py` tetap pakai chain
  failover multi-bursa untuk data. Eksekusi live VST tetap harus ke host BingX.
- **pandas 3.1:** `Series.replace(0.0, pd.NA)` → dtype object → `No numeric types to
  aggregate` di `.mean()`/`rolling`. Selalu `float("nan")`.
- okx ter-exclude dari chain karena bug local di versi ccxt yang terpasang; jangan
  ditambahkan kembali tanpa tes.
- Kredensial git integrasi di environment ini hanya bisa **push** (API 403);
  `gh` CLI (gh auth login device flow, akun sabar2023) yang dipakai untuk secrets,
  workflow dispatch, dan log Actions.
- **`open-api-vst.bingx.com` = domain resmi "simulasi" BingX** (mata uang VST,
  **hanya perpetual**, tanpa spot/std futures). Top-up VST: `POST /openApi/swap/v2/
  trade/getVst` (`adjustType=0` tambah, `amount` **integer**). API BingX kini v3:
  header `X-BX-APIKEY` + `X-SOURCE-KEY`, signature HMAC di **query string**
  (`...&signature=`), bukan di header — ccxt versi terpasang sudah menangani.
- **"Akun USDT Virtual" di APK BingX = simulasi dalam-aplikasi tanpa API**, bukan
  pool VST. Terbukti: +10.005 VST via `getVst` tidak mengubah saldo virtual di APK
  dan posisi VST tidak pernah muncul di sana (host real pun tidak melihatnya).
  Artinya order engine **tidak akan pernah** tampil di APK selama memakai VST;
  satu-satunya pool yang sama antara API & APK adalah **USDT real**.
- **Akun VST berjalan di hedge mode**: order penutup jangan kirim `reduceOnly`
  (ditolak `109400 In the Hedge mode, the 'ReduceOnly' field can not be filled`);
  pakai `positionSide` (LONG/SHORT) + side berlawanan. ccxt mengabaikan
  `reduceOnly` pada order trigger TP, jadi TP1 parsial tetap aman.
- **`fetch_position_history` BingX**: ccxt memetakan `pnl`/`last`/`closePrice`
  kosong. `vst/pnl.py` membaca raw `info`: `netProfit` (fallback `realisedProfit`),
  waktu tutup `updateTime`, harga tutup `avgClosePrice`.
- Secrets GitHub aktif (robot-otomatis): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
  (grup "Grup robot trading"), `BINGX_API_KEY`/`BINGX_SECRET_KEY` (fallback owner),
  `SUPABASE_KEY` (anon), `SUPABASE_SERVICE_KEY` (service, untuk `user_settings`/
  `trade_history` lintas user), `SETTINGS_ENC_KEY` (Fernet, dekripsi API key user).
  Variables: `VST_LIVE`, `SUPABASE_URL`.
- `archive/legacy_v1/` itu kode V1 lama (FastAPI + Vite) — jangan diedit/dirujuk
  sebagai referensi perilaku V2 selain membandingkan fitur.

## Cek Verifikasi Standar Sebelum Menutup Tugas

1. `python3 -m py_compile` semua modul (root + `vst/`).
2. `python3 main.py --dry-run` → semua koin ter-evaluasi (STANDBY/SINYAL wajar).
3. `python3 vst/main.py --dry-run` → watchlist owner (default top-5) ter-evaluasi
   (STANDBY/SINYAL wajar), tidak ada order.
4. Setelah push: `gh workflow run cron-vst.yml -R sabar2023/robot-otomatis`, tunggu
   completion, log menampilkan "=== User: ..." + "Sumber data"-less per-koin rows
   tanpa error. (Cron signal bot lama `cron.yml` sudah off.)
5. Jika mengubah format pesan: kirim 1 contoh ke grup dengan label CONTOH/TEST
   (pola: buat result sintetis lolos filter → `build_alert_html` → `send_message`).
