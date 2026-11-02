# Panduan Restore BrandBisnis V5.0

Panduan memulihkan sistem dari file backup `BACKUP_brandbisnis_v5.0_full.md` ke tempat baru (mesin lokal baru, server baru, atau task/sesi AI baru).

## Prasyarat

- File backup `BACKUP_brandbisnis_v5.0_full.md` (dari tempat aman).
- Python 3.9+ dengan `pip`.
- `git` dan `gh` CLI (opsional, untuk restore GitHub secrets).
- Akun GitHub dengan akses ke repo.

## Isi file backup (8 bagian)

1. Repository (URL, branch, visibility)
2. `.env` lengkap (semua credential)
3. GitHub Secrets & Variables
4. Cloudflare Worker bot-cron
5. Supabase (URL, project id, anon key)
6. Dump data Supabase (JSON)
7. Langkah restore (ringkas)
8. Credential yang tidak bisa direstore otomatis

## Langkah 1 — Clone kode

```bash
git clone https://github.com/sabar2023/robot-otomatis.git
cd robot-otomatis
```

## Langkah 2 — Install dependensi

```bash
pip3 install --break-system-packages -r requirements.txt
```

Catatan: flag `--break-system-packages` untuk Python yang dikelola sistem (Debian/Ubuntu). Di venv/conda tidak perlu.

## Langkah 3 — Buat `.env` lokal

Salin bagian 2 dari file backup ke file `.env` di root repo:

```bash
# contoh: buka editor lalu tempel isi bagian 2
nano .env
```

Verifikasi tidak ada nilai placeholder `<ISI>`:

```bash
grep -c "<ISI>" .env || echo "OK tidak ada placeholder"
```

## Langkah 4 — Verifikasi lokal

```bash
# cek sintaks semua modul
python3 -m py_compile config.py main.py vst/*.py

# scan dry-run (tanpa order, tanpa Telegram)
python3 vst/main.py --dry-run

# tes kirim pesan Telegram (butuh .env terisi)
python3 vst/main.py --test-telegram
```

## Langkah 5 — Restore GitHub Secrets & Variables

Buat repo baru (jika belum ada) lalu dorong kode:

```bash
gh repo create <akun>/robot-otomatis-baru --private --source=. --push
```

Set secret dari `.env`:

```bash
# zsh
set -a; source .env; set +a
for k in BINGX_API_KEY BINGX_SECRET_KEY TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID \
         SUPABASE_KEY SUPABASE_SERVICE_KEY SETTINGS_ENC_KEY; do
  gh secret set "$k" -R <akun>/robot-otomatis-baru --body "${(P)k}"
done

# bash
# for k in ...; do gh secret set "$k" -R <repo> --body "${!k}"; done
```

Set variable:

```bash
gh variable set VST_LIVE -R <akun>/robot-otomatis-baru --body 1
gh variable set SUPABASE_URL -R <akun>/robot-otomatis-baru --body "https://jklbczruvbxscpwxxfud.supabase.co"
```

## Langkah 6 — Restore Cloudflare Worker bot-cron

```bash
cd cloudflare/bot-cron
npx wrangler deploy
```

Lalu set Worker secrets (nilai harus dicatat manual, tidak bisa diambil dari backup):

```bash
npx wrangler secret put GITHUB_PAT
npx wrangler secret put TRIGGER_KEY
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID
```

Jika repo berubah nama, edit `TARGETS` di `cloudflare/bot-cron/src/index.js` dulu.

## Langkah 7 — Restore data Supabase

Data Supabase hidup di cloud (`jklbczruvbxscpwxxfud`) dan tidak ikut kode. Tidak perlu restore bila project sama.

Jika pindah ke project Supabase baru:
1. Buat project baru.
2. Buat 6 tabel: `ro_scans`, `ro_executions`, `ro_config`, `users_profile`, `user_settings`, `trade_history` (skema kolom ada di `AGENTS.md`).
3. Aktifkan RLS.
4. Import data dari bagian 6 file backup (JSON) dengan `supabase` CLI atau `curl` REST.

## Langkah 8 — Verifikasi produksi

```bash
gh workflow run cron-vst.yml -R <akun>/robot-otomatis-baru
gh run list -R <akun>/robot-otomatis-baru --limit 1
gh run view <run-id> -R <akun>/robot-otomatis-baru --log
```

Log sehat bila tampil `=== User: ...` dan baris `STANDBY` per koin tanpa error.

## Credential yang HARUS dicatat manual

Nilai berikut tidak bisa diexport ulang dari cloud, simpan terpisah:

| Credential | Lokasi | Cara dapat kembali |
|---|---|---|
| `GITHUB_PAT` | Cloudflare Worker | buat PAT baru (fine-grained, Actions: write) |
| `TRIGGER_KEY` | Cloudflare Worker | buat string acak baru |
| `BINGX_API_KEY` + `SECRET` | GitHub secret + `.env` | buat ulang di BingX menu Demo Trading (VST) |
| `SETTINGS_ENC_KEY` | GitHub secret + `.env` | TIDAK BOLEH diganti bila dekripsi API key user masih dibutuhkan |

## Aturan emas

1. Simpan `BACKUP_brandbisnis_v5.0_full.md` di 2 tempat (online + offline).
2. Jangan commit file backup (sudah di `.gitignore`).
3. Uji restore setiap 3 bulan di task kosong.
4. `SETTINGS_ENC_KEY` = kunci dekripsi API key user, jaga mutlak.