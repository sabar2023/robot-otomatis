# Product Requirement Document (PRD)

**Nama Produk:** Robot Trading BrandBisnis
**Tipe Produk:** Automated Signal Provider (Non-Execution)
**Strategi Utama:** Scalping (Timeframe 15 Menit / M15)
**Infrastruktur:** Python Murni, Telegram Bot API, GitHub Actions (Serverless Cron Job)
**Status:** V2.0 - Final Draft (5-Layer Filter Edition)

> Catatan: dokumen asli dari pengguna. Implementasi terkini sudah ber-migrasi ke
> timeframe dasar M5 dengan higher-timeframe M15 (lihat README.md).

---

## 1. Ringkasan Eksekutif
Robot Trading BrandBisnis adalah sistem algoritma pemantau pasar mata uang kripto yang beroperasi secara otonom 24/7 tanpa biaya operasional (Rp0). Sistem ini tidak memegang akses dana pengguna. Tugas utamanya adalah menarik data pasar secara gratis, memprosesnya melewati 5 lapisan filter analitik ketat, dan mendistribusikan sinyal *Entry*, *Take Profit*, serta *Stop Loss* langsung ke Telegram pengguna.

## 2. Arsitektur Teknis (Zero-Cost & Serverless)
*   **Data Ingestion (Pengumpul Data):** Menggunakan pustaka `ccxt` (Python) untuk menarik data *candlestick* (OHLCV) dari bursa seperti Binance atau Bybit secara publik tanpa API Key rahasia.
*   **Engine Analitik:** Mengandalkan pustaka `pandas`, `pandas_ta`, dan kalkulasi matematika kustom untuk menghitung indikator.
*   **Distribusi Sinyal:** Menggunakan *Telegram Bot API* (`requests`) untuk mengirim notifikasi ke *Channel* atau *Group* privat.
*   **Hosting Automasi:** Menuliskan instruksi di `.github/workflows/cron.yml` agar sistem *GitHub Actions* menjalankan skrip Python secara otomatis setiap kelipatan 15 menit (menit ke-0, 15, 30, dan 45).

## 3. Mesin Analitik: 5 Lapisan Filter Wajib
Sistem menggunakan pendekatan penyaringan (*filtering*) berlapis. Jika satu aset gagal memenuhi **satu saja** dari 5 filter ini, maka sinyal akan dibatalkan. (Aturan di bawah dicontohkan untuk posisi **LONG/BUY**).

### Lapisan 1: Filter Tren & Multi-Timeframe (Arah Utama)
*   **Logika:** Jangan pernah melawan tren besar institusi.
*   **Syarat M15:** Harga penutupan (Close) saat ini wajib berada di atas EMA-200.
*   **Syarat H1 (1 Jam):** Skrip melakukan inspeksi ke *timeframe* H1. Harga di H1 wajib berada di atas EMA-50.

### Lapisan 2: Filter Zona Kunci & VWAP (Keamanan Posisi)
*   **Logika:** Beli di harga murah (Support) atau saat kekuatan terkonfirmasi (Resistance Breakout).
*   **Syarat S&R:** Harga harus berada dalam rentang toleransi 0.5% dari garis *Support* lokal (hasil kalkulasi *swing low* 20 *candle* terakhir) ATAU harga baru saja *closing* menembus *Resistance*.
*   **Syarat VWAP:** Harga saat ini wajib berada **di atas** garis VWAP (Volume-Weighted Average Price).

### Lapisan 3: Filter Momentum & Volume (Tenaga Dorong)
*   **Logika:** Momentum palsu (*fakeout*) sering terjadi jika tidak didukung volume transaksi.
*   **Syarat Momentum:** Indikator RSI (14) sedang memantul naik dari area *oversold* (menyilang ke atas angka 30) atau menunjukkan tren kuat (berada di atas 50).
*   **Syarat Volume:** Volume *candlestick* saat sinyal muncul wajib **lebih besar** dari rata-rata volume (Volume > SMA 20 Volume).

### Lapisan 4: Filter Kondisi Pasar (Anti-Sideways)
*   **Logika:** Menghindari pasar yang sedang datar/konsolidasi (*choppy*) yang sering menipu indikator EMA.
*   **Syarat ADX:** Nilai indikator ADX (Average Directional Index) wajib berada **di atas 20**. Jika di bawah 20, bot masuk ke mode *Standby* untuk koin tersebut.

### Lapisan 5: Filter Penguasa (The Bitcoin Rule)
*   **Logika:** Nasib Altcoin (ETH, SOL, dll) sangat bergantung pada arah Bitcoin.
*   **Syarat:** Jika koin yang dipindai adalah *Altcoin*, bot akan mengecek tren BTC/USDT di TF M15. Jika BTC/USDT sedang menembus *Support* atau harga berada jauh di bawah EMA-200, maka sinyal BUY untuk *Altcoin* otomatis **dibatalkan**.

## 4. Manajemen Risiko: Kalkulasi Output (TP & SL)
Bot tidak menggunakan persentase statis (misal: baku 1% atau 2%), melainkan beradaptasi dengan volatilitas pasar sesungguhnya menggunakan **ATR (Average True Range)**.

*   **Entry:** Rentang harga saat bot mengirim sinyal hingga +0.1% di atasnya.
*   **Stop Loss (SL):** Ditempatkan sejauh **1.5x nilai ATR** ke bawah dari harga *Entry*.
*   **Take Profit (TP):** Ditempatkan sejauh **3.0x nilai ATR** ke atas dari harga *Entry*. (Menjaga keunggulan matematis *Risk/Reward Ratio* 1:2).

## 5. Template Antarmuka Pesan (Telegram UI)
Pesan diformat menggunakan mode pemformatan HTML Telegram untuk memberikan tampilan visual yang bersih, tegas, dan mudah dibaca (dengan *emoji* penanda warna).

```text
🚨 BRANDBISNIS SCALP ALERT 🚨
⏱ Timeframe: 15 Menit (M15)

📈 PASANGAN : BTC/USDT
🟢 POSISI   : LONG (BUY)

🎯 ENTRY    : 64,250 - 64,300
🛑 STOP LOSS: 63,950 (Support)
✅ TAKE PROFIT: 64,850 (RR 1:2)

📊 Analisis AI Teknikal:
- Tren: Multi-TF Bullish (M15 & H1 valid).
- Zona: Pantulan Support terkonfirmasi + Price > VWAP.
- Vol & Mom: RSI (32) naik, Volume Breakout (1.2x SMA).
- ADX > 20 (Strong Trend).
```

## 6. Roadmap Pengerjaan (Development Plan)
1.  **Fase Persiapan:** Pendaftaran Telegram Bot via `@BotFather` (mendapatkan Token) dan pembuatan Repositori GitHub Privat.
2.  **Fase Coding:** Penulisan skrip `main.py` menggunakan Python. Implementasi 5 lapisan logika bersarang (*nested-if*) dan fungsi API Telegram.
3.  **Fase Simulasi Lokal:** Pengujian *script* secara manual di komputer pengembang menggunakan data *live* bursa untuk memastikan filter berfungsi (membuang sinyal buruk).
4.  **Fase Deployment:** Konfigurasi *GitHub Actions* (`cron.yml`) agar skrip berjalan otomatis dan independen di awan (*cloud*).
