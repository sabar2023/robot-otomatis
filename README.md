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
4. Jika lolos: hitung level berbasis ATR(14):
   - LONG: entry = harga s.d. +0.1%, SL = 1.5x ATR di bawah, TP = 3.0x ATR di atas (RR 1:2).
   - SHORT: entry = harga −0.1% s.d. harga, SL = 1.5x ATR di atas, TP = 3.0x ATR di bawah.
   - **Leverage** = floor(2.0% / jarak-SL-%), dibatasi 2x–10x → risiko margin tetap ±2% saat SL kena.
5. Kirim pesan HTML ke Telegram (template di `telegram_bot.py`: posisi, entry, SL, TP, leverage, analisis + "Penjelasan Sinyal").
6. Jika SEMUA bursa gagal memberi data → run gagal (exit 1), terlihat merah di Actions.

## Struktur File

| File | Isi |
|---|---|
| `main.py` | Orkestrasi: scan, freshness, kirim Telegram; CLI `--dry-run`, `--loop`, `--test-telegram` |
| `config.py` | Semua konstanta + pembacaan `.env` |
| `filters.py` | 5 layer filter dua arah (LONG/SHORT) |
| `risk.py` | Level ATR entry/SL/TP + kalkulasi leverage |
| `indicators.py` | EMA/SMA/RSI/ATR/ADX/VWAP sesi/swing — pandas murni, tanpa pandas_ta |
| `market_data.py` | Chain bursa ccxt + fetcher failover + filter candle close |
| `telegram_bot.py` | Format pesan HTML + kirim via Bot API |
| `requirements.txt` | ccxt, pandas, requests |
| `.github/workflows/cron.yml` | Cron prod (*/5) + trigger manual `workflow_dispatch` |
| `.env.example` | Template env lokal (nilai riil di `.env` yang gitignored) |
| `archive/legacy_v1/` | Sistem V1 (FastAPI dashboard + Vite + Cloudflare) sebelum V2 — arsip, bukan dijalankan |

## Sub-sistem VST (Eksekusi Demo BingX) — folder `vst/`

Berdasarkan PRD "Robot Trading BrandBisnis (M5 VST Edition)"
(`docs/PRD-Robot-Trading-M5-VST.md`): bot yang
**mengirim bracket order** (market + SL/TP terlampir) ke demo trading BingX
(`marginCoin: VST`). Sistem terpisah dari signal bot di atas; keduanya jalan
berdampingan.

- **Simbol:** BTC/USDT:USDT saja (env `VST_SYMBOL`).
- **Mode default: DRY-RUN** — tidak ada order dikirim. Order asli hanya jika
  `VST_LIVE=1` (env/secret GitHub) **dan** `BINGX_API_KEY`/`BINGX_SECRET_KEY`
  (API key dibuat di menu *Demo Trading* BingX) terisi.
- **Strategi (5 layer, dua arah, semua wajib TRUE):** L1 Close vs EMA-200 (M5),
  L2 dekat swing low/high 20 candle (±0.2%), L3 RSI(14) cross dari <30 (LONG)
  / >70 (SHORT), L4 Volume > SMA20, L5 ADX(14) > 20.
- **Risiko:** SL = 1.5x ATR(14), TP = 3.0x ATR(14), RR 1:2, ukuran 100 USDT,
  leverage 10x.
- **Pengaman:** freshness guard (candle tutup ≤ 9.5 menit) + di mode live
  otomatis skip jika sudah ada posisi terbuka di simbul tersebut.
- **Sumber data:** bingx dengan failover multi-bursa (hanya untuk data;
  eksekusi selalu di host VST BingX).

```bash
# simulasi (default): scan + log, tanpa order
python3 vst/main.py

# paksa simulasi / paksa live
python3 vst/main.py --dry-run
python3 vst/main.py --live

# loop lokal tiap kelipatan 5 menit (dev)
python3 vst/main.py --loop

# tes kredensial Telegram
python3 vst/main.py --test-telegram
```

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

- Repo: `sabar2023/robot-trading`, branch `main` (push = langsung live).
- Secrets GitHub yang dipakai: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
- Run manual: tombol *Run workflow* di tab Actions, atau `gh workflow run cron.yml`.
- Biaya: repo publik → menit Actions gratis tanpa limit.

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

- 2026-10-26: sub-sistem VST (folder `vst/`) — eksekusi bracket order demo BingX, dry-run default, cron `cron-vst.yml`.
- 2026-10-24: timeframe M15 → M5 (higher TF H1 → M15), window freshness 9.5 menit.
- 2026-10-24: sinyal dua arah LONG/SHORT + rekomendasi leverage (futures standard).
- 2026-10-24: section "Penjelasan Sinyal" di tiap pesan; cron 15 menit → 5 menit.
- 2026-10-24: failover multi-bursa (crash-safe) + exit 1 bila semua bursa gagal.
- 2026-10-24: rilis V2 (Python murni + Telegram + Actions), V1 diarsipkan.
