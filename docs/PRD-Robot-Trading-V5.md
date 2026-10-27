# **PRD: Robot Trading BrandBisnis (V5.0 \- Edisi Platform SaaS/Dashboard H1 VST)**

# **1\. Ringkasan Eksekutif**

Ekspansi arsitektur sistem dari bot pribadi menjadi platform trading (Web & APK) multi-user dengan fitur manajemen akun, kustomisasi strategi, dan pelaporan transaksi, menggunakan Flutter sebagai frontend dan Supabase sebagai backend/database.  
---

# **2\. Fitur Dashboard & APK (Frontend Flutter)**

* **Panduan UI/UX Tombol:** Desain tombol di dalam Dashboard/APK (Frontend Flutter) harus menggunakan efek "3D Button" yang mirip dengan gaya desain aplikasi "GoPay Merchant", namun tetap mempertahankan palet warna "clean flat light theme" (putih dan teal).  
* **Autentikasi:** Login/Daftar (Email, Nama, No. HP) via Supabase Auth.  
* **Manajemen Kunci API:** Input API Key & Secret Key BingX (dengan enkripsi sebelum masuk database).  
* **Watchlist Koin:** Pemilihan koin untuk dianalisis (Default: Top 5 koin berdasar volume jika dikosongkan).Pengaturan Mode: Toggle Manual vs Otomatis (Default: Otomatis).  
*   
* **Manajemen Risiko & Margin:** Slider/Input untuk Persentase Margin dari total saldo, Persentase TP/SL (Default: Mengikuti sistem dinamis ATR jika kosong), dan Leverage (Default: Mengikuti sistem/10x jika kosong).  
* **Pelaporan & Histori:** Halaman Laporan Keuntungan/Kerugian total (PnL) dan tabel Histori Transaksi (dengan fitur hapus riwayat).

---

# **3\. Skema Database Supabase (Fase 2\)**

Rancangan tabel database sederhana untuk mendukung fitur platform SaaS:

* **Tabel users\_profile:** id, email, nama, no\_hp, created\_at.  
* **Tabel user\_settings:** user\_id, api\_key\_encrypted, secret\_key\_encrypted, mode\_otomatis (boolean), koin\_pilihan (array), margin\_persen, leverage, tp\_persen, sl\_persen.  
* **Tabel trade\_history:** id, user\_id, koin, arah, harga\_entry, pnl, waktu\_eksekusi.

---

# **4\. Alur Kerja Sistem yang Diperbarui**

1. Pengguna mengatur parameter via Dashboard/APK (tersimpan di Supabase).  
2. Mesin Python (di GitHub Actions) berjalan tiap 1 jam (0 \* \* \* \*), menarik pengaturan (user\_settings) dan daftar API keys dari Supabase.  
3. Mesin Python menganalisis koin sesuai pilihan pengguna dan mengeksekusi order (menggunakan parameter kustom pengguna atau default ATR).  
4. Hasil transaksi dicatat kembali ke tabel trade\_history Supabase untuk ditampilkan di Dashboard pengguna.

---

# **5\. Strategi Trading & Manajemen Posisi**

* **Timeframe & Target Profit:** Transisi dari Scalping (M5) ke Day Trading/Swing (H1 atau H4) untuk mengejar target Take Profit yang lebih besar (5% \- 10%).  
* **Logika Filter Analisis (5 Lapisan):**  
  * 1\. Tren: EMA-200.  
  * 2\. S\&R: Support & Resistance dinamis (ayunan harga).  
  * 3\. Momentum: RSI (14) yang memotong area jenuh jual/beli.  
  * 4\. Volume: Di atas rata-rata (SMA 20).  
  * 5\. Filter Choppy: ADX wajib \> 20 (memastikan pasar tidak sedang sideways atau datar).  
* **Manajemen Leverage:** Penggunaan Leverage 5x \- 10x di H1/H4 karena merupakan kombinasi paling realistis dan akurat dibandingkan leverage tinggi di timeframe kecil.  
* **Eksekusi Bracket Order & Isolated Margin:** Bot menembakkan satu paket pesanan ke BingX yang sudah berisi Harga Masuk, Stop Loss, dan Take Profit sekaligus. Mode margin diatur ke Isolated agar kegagalan satu posisi tidak menghabiskan seluruh saldo dompet pengguna.  
* **Position Sizing:** Algoritma wajib membatasi penggunaan modal (misal hanya 10% dari sisa margin yang tersedia per eksekusi) agar sistem tidak all-in dalam satu transaksi.

