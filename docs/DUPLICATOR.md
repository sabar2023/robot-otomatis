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
