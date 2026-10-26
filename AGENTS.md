# AGENTS.md — Konteks Kerja untuk Sesi/AI Baru

Proyek ini adalah **signal bot non-execution** (lihat `README.md` untuk detail lengkap
dan `docs/PRD-Signal-Bot-V2.md` untuk PRD asli). Bot berjalan di GitHub Actions cron
tiap 5 menit di branch `main` — **push ke main = langsung live di produksi**, jadi
selalu verifikasi sebelum push.

## Perintah Utama

```bash
# verifikasi sintaks semua modul
python3 -m py_compile config.py main.py filters.py risk.py telegram_bot.py market_data.py indicators.py

# scan sekali dengan data live, tanpa kirim Telegram
python3 main.py --dry-run

# kirim pesan tes ke grupTelegram (butuh .env terisi)
python3 main.py --test-telegram

# push lalu uji di produksi (repo: sabar2023/robot-trading)
git add -A && git commit -m "..." && git push
gh workflow run cron.yml -R sabar2023/robot-trading
gh run view <run-id> -R sabar2023/robot-trading --log
```

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
- `risk.compute_levels(direction, entry_price, atr_value)` → entry zone, SL, TP,
  `sl_distance_pct`, `leverage` (floor(2%/sl_dist%), clamp 2–10x), `rr`.
- `market_data.make_fetcher(chain)` mengembalikan fetcher yang "nempel" ke bursa
  terakhir yang sukses dalam satu run (failover per run).
- Freshness: `main.py menolak sinyal bila candle basis > 9.5 menit` (window 2 candle
  M5; scan cadence 5 menit). Ini juga mekanisme anti-duplikat, tidak ada state store.

## Pitfall Lingkungan (Jangan Diulang)

- **Binance & Bybit = HTTP 451 dari IP GitHub Actions runner.** Lokal (jaringan dev)
  binance sehat. Jangan kaget kalau log produksi "Sumber data: kraken".
- **pandas 3.1:** `Series.replace(0.0, pd.NA)` → dtype object → `No numeric types to
  aggregate` di `.mean()`/`rolling`. Selalu `float("nan")`.
- okx ter-exclude dari chain karena bug local di versi ccxt yang terpasang; jangan
  ditambahkan kembali tanpa tes.
- Kredensial git integrasi di environment ini hanya bisa **push** (API 403);
  `gh` CLI (gh auth login device flow, akun sabar2023) yang dipakai untuk secrets,
  workflow dispatch, dan log Actions.
- Secrets GitHub aktif: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (grup:
  `TELEGRAM_CHAT_ID` = supergroup "Grup robot trading").
- `archive/legacy_v1/` itu kode V1 lama (FastAPI + Vite) — jangan diedit/dirujuk
  sebagai referensi perilaku V2 selain membandingkan fitur.

## Cek Verifikasi Standar Sebelum Menutup Tugas

1. `python3 -m py_compile` semua modul.
2. `python3 main.py --dry-run` → semua koin ter-evaluasi (STANDBY/SINYAL wajar).
3. Setelah push: `gh workflow run cron.yml`, tunggu completion, log run terakhir
   menunjukkan "Sumber data: <bursa>" + baris per-koin tanpa error.
4. Jika mengubah format pesan: kirim 1 contoh ke grup dengan label CONTOH/TEST
   (pola: buat dataframe sintetis lolos filter → `build_alert_html` → `send_message`).
