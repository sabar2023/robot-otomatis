# Robot Trading BrandBisnis — Signal Bot (Non-Execution)

Bot signal scalping kripto yang berjalan **100% tanpa server**: cron GitHub Actions
memindai pasar setiap 5 menit, menjalankan filter 5-lapis, dan mengirim sinyal
Entry/SL/TP + rekomendasi leverage ke grup Telegram. Tidak menyentuh dana,
tidak mengeksekusi order.

- **Timeframe dasar:** M5 (sejak 2026-10-24; sebelumnya M15)
- **Higher timeframe (cek tren):** M15 (sebelumnya H1)
- **Arah sinyal:** dua arah — LONG (BUY) dan SHORT (SELL) untuk futures standard
- **Watchlist:** BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT (env `SYMBOLS`)
- **Sumber data:** ccxt, failover binance → bybit → kraken → bitget → gate → kucoin
- **Dokumen PRD asli:** `docs/PRD-Signal-Bot-V2.md`
- **Panduan agen (untuk AI/session baru):** `AGENTS.md`

## Cara Kerja Singkat

Setiap 5 menit (cron `*/5 * * * *`), `main.py` untuk tiap koin:

1. Ambil 300 candle M5 (terakhir yang sudah close) + 100 candle M15 via chain bursa.
2. Evaluasi 5 layer (LONG dan SHORT di-evaluasi simultan; yang lolos 5/5 yang menang):
   - **L1 Tren Multi-TF:** LONG: close M5 > EMA200(M5) dan close M15 > EMA50(M15). SHORT: cermin.
   - **L2 Zona + VWAP:** LONG: dekat support (±0.5%) atau breakout resistance, dan close > VWAP sesi. SHORT: dekat resistance/breakdown support, dan close < VWAP.
   - **L3 Momentum + Volume:** LONG: RSI rebound dari <30 atau > 50. SHORT: RSI dead-cross dari >70 atau < 50. Keduanya wajib volume > SMA20.
   - **L4 ADX:** ADX(14) > 20 (anti-sideways).
   - **L5 Bitcoin Rule (altcoin saja):** BTC tidak boleh breaking support (LONG) / resistant breakout atau jauh > EMA200 (SHORT).
3. Freshness guard: sinyal hanya dikirim jika berbasis candle M5 yang baru close ≤ 9.5 menit (mencegah duplikat/sinyal basi).
4. Jika lolos: hitung level persentase dari entry:
   - LONG: entry = harga s.d. +0.1%, SL = 2.5% di bawah, TP = 7.5% di atas (RR 1:3).
   - SHORT: entry = harga −0.1% s.d. harga, SL = 2.5% di atas, TP = 7.5% di bawah.
   - SL/TP diatur `SL_PCT`/`TP_PCT` (default 2.5/7.5 → rentang SL 2-3%, TP 5-10%).
   - **Leverage** = floor(2.0% / jarak-SL-%), dibatasi 2x-10x.
5. Kirim pesan HTML ke Telegram (template di `telegram_bot.py`: posisi, entry, SL, TP, leverage, analisis + "Penjelasan Sinyal").
6. Jika SEMUA bursa gagal memberi data → run gagal (exit 1), terlihat merah di Actions.

## Struktur File

| File | Isi |
|---|---|
| `main.py` | Orkestrasi: scan, freshness, kirim Telegram; CLI `--dry-run`, `--loop`, `--test-telegram` |
| `config.py` | Semua konstanta + pembacaan `.env` |
| `filters.py` | 5 layer filter dua arah (LONG/SHORT) |
| `risk.py` | Level entry/SL/TP (persentase) + kalkulasi leverage |
| `indicators.py` | EMA/SMA/RSI/ATR/ADX/VWAP sesi/swing — pandas murni, tanpa pandas_ta |
| `market_data.py` | Chain bursa ccxt + fetcher failover + filter candle close |
| `telegram_bot.py` | Format pesan HTML + kirim via Bot API |
| `requirements.txt` | ccxt, pandas, requests |
| `.github/workflows/cron.yml` | Cron prod (*/5) + trigger manual `workflow_dispatch` |
| `.env.example` | Template env lokal (nilai riil di `.env` yang gitignored) |
| `archive/legacy_v1/` | Sistem V1 (FastAPI dashboard + Vite + Cloudflare) sebelum V2 — arsip, bukan dijalankan |

## Sub-sistem VST V5.0 (Platform Multi-User, Eksekusi BingX VST) — folder `vst/`

Berdasarkan PRD "Robot Trading BrandBisnis (V5.0 — Edisi Platform
SaaS/Dashboard H1 VST)" (`docs/PRD-Robot-Trading-V5.md`): platform
**multi-user** day-trading H1: engine Python (1x/jam) membacakan setting tiap
user dari Supabase, mengeksekusi bracket order **isolated margin** di demo
BingX (VST) dengan API key masing-masing user, dan mencatat riwayat + PnL.
Aplikasi web/APK Flutter resmi ada di folder `app/` (mencari tabel Supabase
yang sama via auth + RLS).

- **Timeframe:** H1 (env `VST_TIMEFRAME`, opsi 5m/15m/1h/4h), scan 1x/jam.
- **Multi-user:** `users_profile` + `user_settings` di Supabase. API key &
  secret key user disimpan **terenkripsi Fernet** (`SETTINGS_ENC_KEY`); engine
  mendekripsi saat run. `mode_otomatis=false` → tetap di-scan (riwayat tercatat)
  tapi tanpa order live. Bila belum ada user di DB → fallback akun owner dari
  env `BINGX_API_KEY`/`BINGX_SECRET_KEY`.
- **Watchlist per user:** `koin_pilihan[]` manual; jika kosong → default **top-5
  volume 24h** bursa (env `VST_WATCHLIST_SIZE`).
- **Mode default: DRY-RUN** — tidak ada order dikirim. Order live hanya jika
  `VST_LIVE=1` **dan** `ro_config.auto_trading=true` **dan** user
  `mode_otomatis=true`.
- **Strategi (5 layer, dua arah, semua wajib TRUE):** L1 Close vs EMA-200 (H1),
  L2 dekat swing low/high 20 candle (±0.2%), L3 RSI(14) cross dari <30 (LONG)
  / >70 (SHORT), L4 Volume > SMA20, L5 ADX(14) > 20.
- **Risiko per user:** SL/TP default **ATR dinamis** (SL = ATR×1.5 clamp 1–5%,
  TP = ATR×4 clamp 3–12%); user bisa set `sl_persen`/`tp_persen` sendiri
  (clamp 0.5–20% / 0.5–50%). Leverage 5–10x (default 10). Margin maksimal
  `margin_persen`% (default 10%) dari saldo VST free per order — PRD: maksimal
  10% sisa margin per eksekusi.
- **Pengaman:** freshness guard (candle tutup ≤ 90 menit) + skip entry jika
  sudah ada posisi terbuka di simbol tersebut + toggle `ro_config.auto_trading`.
- **Sumber data:** bingx dengan failover multi-bursa (hanya untuk data;
  eksekusi selalu di host VST BingX).
- **Supabase:** `ro_scans` (scan per koin), `ro_executions` (order/simulasi),
  `trade_history` (riwayat + PnL per user), `ro_config` (toggle). Engine baca
  lintas-user pakai `SUPABASE_SERVICE_KEY`; user Flutter baca data sendiri via
  auth (RLS aktif).
- **PnL realisasi otomatis:** `vst/pnl.py` — tiap run, baris `trade_history`
  `status=open` dicocokkan dengan `fetch_position_history` BingX (90 hari);
  posisi yang sudah tertutup (SL/TP terketuk) diisi `pnl` + `closed_at`
  (status `closed`).
- **Notifikasi per user:** selain grup utama, bila user mengisi
  `user_settings.tg_chat_id`, sinyal juga dikirim ke chat pribadi user tersebut.

```bash
# simulasi (default): scan semua user, tanpa order
python3 vst/main.py --dry-run

# paksa live
python3 vst/main.py --live

# scan hanya satu user (uji per-user)
python3 vst/main.py --dry-run --user email-user@contoh.com

# loop lokal tiap awal jam (dev)
python3 vst/main.py --loop

# tes kredensial Telegram
python3 vst/main.py --test-telegram

# kirim contoh alert ke Telegram dari eksekusi terakhir (cek format pesan)
python3 vst/telegram_alert_demo.py
```

## Aplikasi Flutter (Web + APK) — folder `app/`

Frontend resmi V5.0: login Supabase (email/kata sandi, auto-confirm), dashboard
pengaturan (moda otomatis, koin pilihan, leverage, margin, SL/TP, API key
BingX, Telegram chat ID), dan riwayat trade per user dengan PnL + hapus baris.
Tema dark teal gaya 3D.

```bash
# build web (hasil di app/build/web, serve statis apa pun)
cd app && flutter build web --release

# build APK (lokal butuh Android SDK; CI menjalan otomatis)
flutter build apk --release
```

- CI APK: `.github/workflows/app-apk.yml` — build otomatis tiap push yang
  menyentuh `app/`; hasil di tab Actions (artifact `brandbisnis-app-apk`).
- Prototipe dashboard web (HTML statis, untuk tes cepat):
  `web/dashboard-test/`.

## Menjalankan Lokal

```bash
# install dependensi
pip3 install --break-system-packages -r requirements.txt

# buat .env dari template, isi TELEGRAM_BOT_TOKEN dan TELEGRAM_CHAT_ID
cp .env.example .env

# cek sinyal tanpa kirim Telegram
python3 main.py --dry-run

# uji kredensial Telegram (kirim pesan tes ke grup)
python3 main.py --test-telegram

# loop lokal tiap 5 menit (hanya untuk dev; produksi = GitHub Actions)
python3 main.py --loop
```

## Deployment (sudah berjalan)

- **Pemicu utama:** Cloudflare Worker `bot-cron`
  (`https://bot-cron.sabar2023.workers.dev`, cron `0 * * * *`) memanggil
  `workflow_dispatch` ke `cron-vst.yml` (robot-otomatis). Signal bot repo lama
  **dinonaktifkan** (tidak dipicu; manual via tombol Actions bila perlu).
  `schedule` GitHub sengaja **dimatikan** (terbukti di-throttle 4-5 jam) dan
  agar tidak ada run dobel. Gagal dispatch → alert otomatis ke Telegram.
  Manual: `https://bot-cron.sabar2023.workers.dev/run?key=<TRIGGER_KEY>`.
- **Repo baru (sistem V5.0):** `sabar2023/robot-otomatis`, branch `main`
  (push = langsung live). Workflow `cron-vst.yml` (dispatch-only).
  `cron.yml` (signal bot) hanya manual di repo ini karena signal bot tetap
  jalan di repo lama.
- **Repo lama (signal bot):** `sabar2023/robot-trading`, branch `main`,
  `cron.yml` (dispatch-only). `cron-vst.yml` di sana tidak dipakai (VST hanya
  di repo baru).
- Secrets repo baru: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `BINGX_API_KEY`, `BINGX_SECRET_KEY` (fallback owner), `SUPABASE_KEY` (anon),
  `SUPABASE_SERVICE_KEY` (service role, baca lintas-user), `SETTINGS_ENC_KEY`
  (kunci Fernet API key user). Variable: `VST_LIVE=1` (aktif), `SUPABASE_URL`.
- Run manual: tombol *Run workflow* di tab Actions, atau
  `gh workflow run cron-vst.yml -R sabar2023/robot-otomatis`.
- Biaya: repo publik → menit Actions gratis tanpa limit; Worker cron gratis
  (288 request/hari dari 100k limit).
- Jika PAT GitHub di Worker kedaluwarsa, dispatch berhenti diam-diam: perbarui
  via `wrangler secret put GITHUB_PAT` (log: Workers & Pages → bot-cron → Logs).

## Catatan Penting (Pitfall)

- **Binance & Bybit memblokir IP runner GitHub Actions (HTTP 451)** — di produksi data
  biasanya jatuh ke Kraken. Jangan "memperbaiki" ini dengan hardcoded satu bursa;
  chain failover di `market_data.py` sengaja multi-bursa.
- **pandas 3.x:** jangan `.replace(0.0, pd.NA)` pada kolom numerik (menjadi object dtype
  dan agregasi gagal). Pakai `float("nan")` (lihat `indicators.py`).
- Emoji di pesan Telegram ditulis sebagai `&#NNNN;` (numeric entity) di kode,
  dirender Telegram sebagai emoji.
- Jangan pernah menaruh nilai token riil di file yang ter-commit; `.env` sudah
  masuk `.gitignore`.

## Perubahan Terkini

- 2026-10-28: aplikasi Flutter resmi di `app/` (web + APK via CI
  `app-apk.yml`); sync PnL posisi tertutup otomatis tiap run (`vst/pnl.py`);
  notifikasi Telegram per user (`tg_chat_id`); prototipe dashboard web di
  `web/dashboard-test/`.
- 2026-10-27: upgrade V5.0 — platform **multi-user** H1: setting/riwayat per
  user di Supabase (`users_profile`, `user_settings`, `trade_history`), API key
  terenkripsi Fernet, leverage 5–10x, margin terisolasi, position sizing
  10% sisa margin, SL/TP default ATR (bisa di-override user), watchlist
  default top-5 volume, cron 1x/jam (`0 * * * *`).
- 2026-10-26: sub-sistem VST (folder `vst/`) — eksekusi bracket order demo BingX, dry-run default, cron `cron-vst.yml`.
- 2026-10-24: timeframe M15 → M5 (higher TF H1 → M15), window freshness 9.5 menit.
- 2026-10-24: sinyal dua arah LONG/SHORT + rekomendasi leverage (futures standard).
- 2026-10-24: section "Penjelasan Sinyal" di tiap pesan; cron 15 menit → 5 menit.
- 2026-10-24: failover multi-bursa (crash-safe) + exit 1 bila semua bursa gagal.
- 2026-10-24: rilis V2 (Python murni + Telegram + Actions), V1 diarsipkan.
