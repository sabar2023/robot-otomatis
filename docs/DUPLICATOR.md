# Duplicator Backup & Restore BrandBisnis V5.0

Dua skrip untuk mencadangkan seluruh sistem dan memulihkannya (atau menduplikasi ke akun/proyek baru) seperti duplicator.

- `tools/duplicator/backup.py` — membuat arsip lengkap.
- `tools/duplicator/restore.py` — memulihkan data ke Supabase tujuan dan menyiapkan langkah lanjutan.

Arsip backup memuat rahasia (API key, service key, token). Simpan di tempat aman, jangan commit/push. Folder `backups/` sudah masuk `.gitignore`.

## 1. Membuat Backup

```bash
python3 tools/duplicator/backup.py
```

Hasil default:

```text
backups/duplicator-YYYYMMDD-HHMMSS/
backups/duplicator-YYYYMMDD-HHMMSS.tar.gz
backups/duplicator-YYYYMMDD-HHMMSS.sha256
```

Isi arsip:

| Path | Isi |
|---|---|
| `repo.bundle` | Clone repo lengkap dengan seluruh riwayat Git |
| `db/*.json` | Seluruh tabel Supabase (13 tabel) |
| `auth/users.json` | Daftar user Supabase Auth (tanpa password/hash) |
| `github/variables.json` | GitHub Actions variables beserta nilainya |
| `github/secrets.json` | Nama secret GitHub (nilai tidak dapat dibaca ulang) |
| `github/workflows.json` | Daftar workflow |
| `cloudflare/worker.json` | Konfigurasi Worker dan daftar secret-nya |
| `secrets/env.backup` | Nilai environment rahasia (mode 600) |
| `manifest.json` | Metadata, jumlah baris tiap tabel, commit |

Opsi:

```bash
python3 tools/duplicator/backup.py --out-dir /path/aman
python3 tools/duplicator/backup.py --skip-gh --skip-worker
python3 tools/duplicator/backup.py --no-git-bundle
python3 tools/duplicator/backup.py --upload-supabase
```

`--upload-supabase` mengunggah arsip ke bucket privat `system-backups` (Supabase Storage)
dan mencetak `OBJECT_PATH=` serta `SHA256=`. Bucket dibuat otomatis bila belum ada.

## 2. Restore ke Proyek Supabase Baru

Siapkan project Supabase baru, jalankan migrasi SQL yang dibutuhkan (lihat `docs/migration-*.sql`), lalu:

```bash
python3 tools/duplicator/restore.py \
  --archive backups/duplicator-YYYYMMDD-HHMMSS.tar.gz \
  --target-url https://PROJECT_BARU.supabase.co \
  --target-service-key SERVICE_KEY_BARU \
  --yes
```

Tanpa `--yes` skrip hanya menampilkan rencana (dry-run).

Yang dilakukan skrip:

1. Membuat user di Supabase Auth (password sementara dibuat otomatis, karena password lama tidak dapat diekspor).
2. Menyalin `users_profile` dan memetakan `auth_id` ke user baru berdasarkan email.
3. Menyalin seluruh tabel lain dengan upsert (`on_conflict` primary key), memetakan `user_id` lama ke profil tujuan.
4. Menulis password sementara ke `restored/auth_passwords.txt` (mode 600).

Opsi restore:

```bash
# tanpa membuat user auth (hanya data)
python3 tools/duplicator/restore.py --archive ... --target-url ... --target-service-key ... --yes --skip-auth

# sekaligus set GitHub variables/secrets ke repo baru
python3 tools/duplicator/restore.py --archive ... --target-url ... --target-service-key ... --yes \
  --new-repo akun/repo-baru --apply-github

# sekaligus deploy Worker
python3 tools/duplicator/restore.py --archive ... --target-url ... --target-service-key ... --yes --deploy-worker
```

## 3. Duplikasi ke Akun/Repo Baru (End-to-End)

```bash
# 1. ekstrak arsip bila perlu
tar -xzf backups/duplicator-YYYYMMDD-HHMMSS.tar.gz -C /tmp

# 2. clone kode dari bundle
git clone /tmp/duplicator-YYYYMMDD-HHMMSS/repo.bundle robot-otomatis-baru
cd robot-otomatis-baru

# 3. buat repo baru dan push
gh repo create akun/robot-otomatis-baru --private --source=. --push

# 4. restore data Supabase
python3 tools/duplicator/restore.py \
  --archive /path/duplicator-YYYYMMDD-HHMMSS.tar.gz \
  --target-url https://PROJECT_BARU.supabase.co \
  --target-service-key SERVICE_KEY_BARU \
  --yes --new-repo akun/robot-otomatis-baru --apply-github

# 5. restore secret Worker
cd cloudflare/bot-cron
wrangler secret put GITHUB_PAT
wrangler secret put TRIGGER_KEY
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_CHAT_ID
wrangler deploy
```

## 4. Web Duplicator (Klik untuk Restore)

Tersedia UI web agar backup/restore cukup klik, tanpa CLI.

```bash
export DUPLICATOR_TOKEN=$(python3 -c "import secrets,string;print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(18)))")
python3 tools/duplicator/webapp.py --host 0.0.0.0 --port 8090
```

Buka `http://localhost:8090/?token=<DUPLICATOR_TOKEN>`.

Fitur:

- Tombol **Buat Backup** — menjalankan `backup.py` dari server, arsip tersimpan di `backups/`.
- Daftar arsip + tombol **download**.
- Form **Restore** — pilih arsip, isi Target Supabase URL + Service Key, opsi (dry-run, skip auth, set GitHub, deploy Worker), klik **Restore Sekarang**.

Token akses wajib, semua API dilindungi token. Jangan buka ke publik tanpa token.

## 5. Rahasia yang Wajib Disimpan Manual

| Rahasia | Lokasi | Catatan |
|---|---|---|
| `SETTINGS_ENC_KEY` | `.env` + GitHub secret | Wajib sama persis, jika berubah API key user tidak bisa didekripsi |
| `GITHUB_PAT` | Worker secret | Tidak bisa dibaca ulang, buat baru bila hilang |
| `TRIGGER_KEY` | Worker secret | Tidak bisa dibaca ulang, buat string acak baru |
| Password user | Supabase Auth | Tidak dapat diekspor; restore membuat password sementara |
| `BINGX_API_KEY` / `SECRET` | `.env` + GitHub secret | Tersimpan di `secrets/env.backup` |

## 6. Verifikasi Setelah Restore

```bash
python3 -m py_compile config.py main.py vst/*.py
python3 vst/main.py --dry-run
gh workflow run cron-vst.yml -R akun/robot-otomatis-baru
gh run view <run-id> -R akun/robot-otomatis-baru --log
```

Pastikan log menampilkan `=== User: ...`, baris scan per koin, dan tidak ada error kredensial.

## 7. Aturan Emas

1. Buat backup berkala, simpan minimal di dua tempat (offline + storage aman).
2. Jangan pernah commit arsip backup atau `secrets/env.backup`.
3. Uji restore di project Supabase percobaan sebelum dipakai produksi.
4. Jaga `SETTINGS_ENC_KEY` — tanpa kunci ini API key pelanggan tidak dapat dipulihkan.

## 8. Duplicator Hosted (Tanpa Terminal)

Portal statis: `https://sabar2023.github.io/robot-otomatis/duplicator.html`
(sumber `app/web/duplicator.html`). Dua workflow GitHub Actions:

| Workflow | Fungsi | Input |
|---|---|---|
| `duplicator-backup.yml` | Buat arsip lalu unggah ke Storage | — |
| `duplicator-restore.yml` | Unduh arsip lalu restore ke project tujuan | `archive`, `target_url`, `skip_auth`, `confirm=RESTORE` |

Secrets repository yang dipakai:

- `SUPABASE_SERVICE_KEY` — export DB sumber + unggah arsip.
- `RESTORE_SERVICE_KEY` — service key project Supabase tujuan.
- `RESTORE_TEMP_PASSWORD` — password sementara user auth hasil restore.
- `SETTINGS_ENC_KEY` — harus sama dengan sistem lama.

Alur backup:

1. Buka halaman workflow `duplicator-backup`, klik **Run workflow** pada `main`.
2. Tunggu selesai; step summary menampilkan `OBJECT_PATH` dan `SHA256`.
3. Arsip tersimpan privat di `system-backups`. Bukan artifact publik.

Alur restore:

1. Siapkan project Supabase baru dan jalankan migrasi SQL (`docs/migration-*.sql`).
2. Set `RESTORE_SERVICE_KEY` dan `RESTORE_TEMP_PASSWORD` di repository.
3. Buka workflow `duplicator-restore`, isi nama objek arsip, URL tujuan, ketik `RESTORE`.
4. Setelah restore: clone repo, set GitHub secrets/variables, deploy Worker.

Uji lokal upload/download:

```bash
python3 tools/duplicator/storage.py --upload backups/duplicator-*.tar.gz
python3 tools/duplicator/storage.py --download <nama-objek> --out /tmp/uji.tar.gz
```

## 9. Backup dari Admin Panel + Restore via cPanel (tanpa VPS/SSH)

Metode ini untuk skenario paling sederhana: admin klik tombol di Flutter app, backup dibuat oleh GitHub Actions dan di-upload ke Supabase Storage. Restore dilakukan dengan upload satu file PHP ke cPanel.

### 9.1 Prasyarat sekali jalan

1. **Bucket Supabase Storage**: buat bucket `system-backups` (private) di project Supabase.
2. **GitHub Secrets** (repo `sabar2023/robot-otomatis`): pastikan `SUPABASE_URL` dan `SUPABASE_SERVICE_KEY` ada di repo secrets (sudah dipakai workflow lain; workflow `duplicator-backup.yml` juga memerlukannya).
3. **Cloudflare Worker secret**: `GITHUB_PAT` harus sudah ada di worker `bot-cron` (sudah ada untuk dispatch workflow). Worker juga butuh `SUPABASE_SERVICE_KEY` (sudah ada).
4. Deploy worker setelah update kode:
   ```bash
   cd cloudflare/bot-cron
   npx wrangler deploy
   ```

Tidak ada migrasi DB baru. Tidak ada secret baru selain yang sudah ada.

### 9.2 Alur Backup (dari Admin Panel Flutter)

1. Admin buka **Dashboard Admin** → bagian **Backup & Restore**.
2. Klik **Backup Sekarang**.
3. App memanggil `POST /admin/backup` di worker `bot-cron` dengan Bearer token admin Supabase.
4. Worker memvalidasi admin via `requireAdmin()` lalu dispatch `workflow_dispatch` ke `duplicator-backup.yml` via GitHub API (`GITHUB_PAT`).
5. GitHub Actions menjalankan `python3 tools/duplicator/backup.py --upload-supabase`:
   - membuat arsip backup lengkap (DB, env, worker, workflows, engine) — sama seperti backup manual,
   - upload arsip ke bucket Supabase Storage `system-backups`,
   - menulis `SHA256`, `OBJECT_PATH` ke step summary.
6. Admin klik **Refresh** di panel. App memanggil `GET /admin/backups`, worker list isi bucket `system-backups`.
7. Untuk download, admin klik ikon download. App memanggil `GET /admin/backup-url?name=...`, worker membuat signed URL Supabase Storage (berlaku 10 menit), app membuka URL itu di browser/external app.

### 9.3 Endpoint Worker baru

Semua endpoint butuh `Authorization: Bearer <supabase_access_token>` milik admin (divalidasi `requireAdmin()`).

| Endpoint | Method | Fungsi |
|---|---|---|
| `/admin/backups` | GET | List file `.tar.gz` di bucket `system-backups`, urut terbaru |
| `/admin/backup` | POST | Dispatch workflow `duplicator-backup.yml` (ref `main`) |
| `/admin/backup-url?name=<file>` | GET | Buat signed download URL (600 detik). Nama divalidasi ketat (tanpa `/`, `..`, harus `.tar.gz`) |

Respons error umum: `401/403` bukan admin, `500 github_pat_missing`, `502` gagal ke GitHub/Supabase Storage.

### 9.4 Restore via cPanel (`installer.php`)

File: `tools/duplicator/cpanel/installer.php` — satu file PHP mandiri.

**Cara pakai:**

1. Download arsip backup `.tar.gz` dari Admin Panel (atau dari Supabase Storage).
2. Upload `installer.php` ke folder web cPanel (mis. `public_html/restore/`).
3. Buka `https://domain-anda/restore/installer.php` di browser.
4. Buat password installer (disimpan sebagai hash di `.duplicator-installer-state.json` di folder yang sama).
5. Upload arsip `.tar.gz`. Installer akan extract ke `.duplicator-extract/`.
6. Isi kredensial Supabase target (project ref, db host/port/name/user/password, service role key). Klik **Jalankan Restore Supabase**.
   - Restore `schema.sql` via `psql` (butuh `psql` tersedia di server; kebanyakan shared hosting tidak punya — lihat batasan).
   - Import data public (SQL atau COPY dari CSV).
   - Buat auth users via Supabase Admin API.
   - Buat bucket + upload objek storage via Supabase Storage API.
7. Isi GitHub repo + PAT. Installer akan set secrets/variables dari manifest + `env/.env.sanitized`.
8. Isi Cloudflare Account ID, Worker name, API token. Installer deploy worker script dengan binding secret.
9. Selesai — hapus `installer.php`, `.duplicator-installer-state.json`, `.duplicator-installer.log`, `.duplicator-extract/`, dan arsip backup dari server.

**Keamanan installer:**
- Password installer wajib, disimpan sebagai `password_hash()`.
- Session-based auth + CSRF token di setiap form.
- DB password, service role key, GitHub PAT, Cloudflare API token **tidak disimpan** di state file.
- State file hanya menyimpan metadata non-sensitif (path arsip, project ref, host, repo, status langkah).
- Hapus semua file installer setelah restore.

### 9.5 Batasan cPanel/shared hosting

- **`psql` tidak selalu ada** di shared hosting. Restore schema/data SQL butuh `psql`. Jika tidak ada, gunakan VPS sementara atau jalankan restore DB via `tools/duplicator/restore.py` di mesin dengan `psql`.
- **`PharData`** harus aktif untuk extract `.tar.gz`. Umumnya aktif; jika tidak, extract manual lalu sesuaikan.
- **`shell_exec/proc_open`** mungkin diblokir. Installer butuh `proc_open` untuk `psql`.
- **`sodium`** extension dibutuhkan untuk enkripsi GitHub secrets. Umumnya aktif di PHP 7.2+.
- **Upload size**: sesuaikan `upload_max_filesize` dan `post_max_size` di PHP config cPanel agar muat arsip backup.
- **Timeout**: restore DB besar bisa kena `max_execution_time`. Jalankan dari PHP CLI atau naikkan limit bila memungkinkan.

### 9.6 Troubleshooting

| Gejala | Penyebab | Solusi |
|---|---|---|
| `github_pat_missing` dari `/admin/backup` | Secret `GITHUB_PAT` belum ada di worker | `wrangler secret put GITHUB_PAT` di `cloudflare/bot-cron` |
| `storage_list_failed` | Bucket `system-backups` belum ada / key salah | Buat bucket private `system-backups` di Supabase Storage |
| `dispatch_failed` 403 | PAT tidak punya akses Actions write | Pastikan PAT fine-grained punya Actions: Read & write untuk repo |
| Backup workflow gagal upload | `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` secret repo kosong | Set di GitHub repo Settings → Secrets and variables → Actions |
| Installer: `psql: command not found` | Shared hosting tanpa PostgreSQL client | Restore DB via VPS/mesin dengan psql, atau minta hosting enable psql |
| Installer: extract gagal | `PharData`/`zlib` tidak aktif | Aktifkan ekstensi PHP Phar dan zlib di cPanel Select PHP Version |
| Signed URL 400/404 | Nama file tidak valid / file dihapus | Refresh daftar backup, pastikan nama berakhiran `.tar.gz` |
| Download tidak terbuka di app | URL launcher / browser blocked | Coba salin link dari browser; signed URL berlaku 10 menit |
