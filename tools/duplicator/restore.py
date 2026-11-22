import argparse
import json
import os
import secrets
import shutil
import string
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import requests

import storage

TABLE_ORDER = [
    "users_profile",
    "user_settings",
    "subscriptions",
    "payments",
    "trade_history",
    "ro_scans",
    "ro_executions",
    "ro_config",
    "support_tickets",
    "ticket_messages",
    "app_versions",
    "guides",
    "admin_settings",
]

TABLE_PK = {
    "users_profile": "id",
    "user_settings": "user_id",
    "subscriptions": "id",
    "payments": "id",
    "trade_history": "id",
    "ro_scans": "id",
    "ro_executions": "id",
    "ro_config": "key",
    "support_tickets": "id",
    "ticket_messages": "id",
    "app_versions": "id",
    "guides": "id",
    "admin_settings": "key",
}

USER_REF_TABLES = ["user_settings", "subscriptions", "payments", "trade_history", "support_tickets"]

GITHUB_SECRET_ENV = [
    "BINGX_API_KEY",
    "BINGX_SECRET_KEY",
    "BINGX_BACKUP_API_KEY",
    "BINGX_BACKUP_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SETTINGS_ENC_KEY",
]


def headers(key, extra=None):
    h = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def read_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


def resolve_workdir(archive, workdir):
    if workdir:
        return Path(workdir), None
    if not archive:
        raise SystemExit("Butuh --archive <tar.gz> atau --workdir <folder>")
    tmp = Path(tempfile.mkdtemp(prefix="duplicator-restore-"))
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(tmp)
    entries = [p for p in tmp.iterdir() if p.is_dir()]
    if len(entries) != 1:
        raise SystemExit("Struktur arsip tidak dikenali")
    return entries[0], tmp


def load_env_backup(work):
    env = {}
    path = work / "secrets" / "env.backup"
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def gen_password():
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(14))


def auth_list(url, key):
    users = {}
    page = 1
    while True:
        resp = requests.get(
            f"{url}/auth/v1/admin/users",
            headers=headers(key),
            params={"page": page, "per_page": 200},
            timeout=60,
        )
        if resp.status_code != 200:
            return users
        data = resp.json()
        batch = data.get("users") if isinstance(data, dict) else data
        batch = batch or []
        for u in batch:
            email = (u.get("email") or "").lower()
            if email:
                users[email] = u.get("id")
        if len(batch) < 200:
            break
        page += 1
    return users


def auth_create(url, key, email, password):
    body = {"email": email, "password": password, "email_confirm": True}
    resp = requests.post(f"{url}/auth/v1/admin/users", headers=headers(key), json=body, timeout=60)
    if resp.status_code in (200, 201):
        return resp.json().get("id")
    if resp.status_code in (409, 422):
        return None
    raise RuntimeError(f"{email}: HTTP {resp.status_code} {resp.text[:150]}")


def pg_get(url, key, table, params):
    resp = requests.get(f"{url}/rest/v1/{table}", headers=headers(key), params=params, timeout=60)
    if resp.status_code != 200:
        return []
    return resp.json()


def pg_patch(url, key, table, filt, body):
    resp = requests.patch(
        f"{url}/rest/v1/{table}",
        headers=headers(key, {"Prefer": "return=minimal"}),
        params=filt,
        json=body,
        timeout=60,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"{table} patch: HTTP {resp.status_code} {resp.text[:150]}")


def pg_insert(url, key, table, body):
    resp = requests.post(
        f"{url}/rest/v1/{table}",
        headers=headers(key, {"Prefer": "return=minimal"}),
        json=body,
        timeout=60,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"{table} insert: HTTP {resp.status_code} {resp.text[:150]}")


def pg_upsert(url, key, table, rows, pk, batch=200):
    done = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        resp = requests.post(
            f"{url}/rest/v1/{table}",
            headers=headers(key, {"Prefer": "resolution=merge-duplicates,return=minimal"}),
            params={"on_conflict": pk},
            json=chunk,
            timeout=120,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"{table} upsert: HTTP {resp.status_code} {resp.text[:200]}")
        done += len(chunk)
    return done


def plan_summary(work):
    manifest = read_json(work / "manifest.json", {})
    print("Manifest:")
    print(f"  dibuat   : {manifest.get('created_at')}")
    print(f"  commit   : {manifest.get('commit')}")
    print(f"  supabase : {manifest.get('supabase_url')}")
    tables = manifest.get("tables") or {}
    for name in TABLE_ORDER:
        info = tables.get(name) or {}
        print(f"  tabel {name}: {info.get('rows', '?')} baris")
    print(f"  auth users: {manifest.get('auth_users')}")


def restore_db(url, key, work, dry_run, skip_auth, report, auth_password=None):
    db_dir = work / "db"
    auth_users = read_json(work / "auth" / "users.json", [])
    email_to_auth = {}
    passwords = {}

    if not dry_run and not skip_auth and auth_users:
        existing = auth_list(url, key)
        for user in auth_users:
            email = (user.get("email") or "").strip()
            if not email:
                continue
            existing_id = existing.get(email.lower())
            if existing_id:
                email_to_auth[email.lower()] = existing_id
                continue
            pwd = auth_password or gen_password()
            new_id = auth_create(url, key, email, pwd)
            if new_id:
                email_to_auth[email.lower()] = new_id
                if not auth_password:
                    passwords[email] = pwd
        report.append(f"auth users dibuat: {len(passwords)}, sudah ada: {len(email_to_auth) - len(passwords)}")

    profiles = read_json(db_dir / "users_profile.json", [])
    id_map = {}
    profile_rows = []
    for p in profiles:
        old_id = p.get("id")
        email = (p.get("email") or "").strip().lower()
        new_auth = email_to_auth.get(email) or p.get("auth_id")
        row = dict(p)
        row["auth_id"] = new_auth
        id_map[old_id] = old_id
        profile_rows.append(row)

    if not dry_run:
        existing_profiles = { (x.get("email") or "").lower(): x for x in pg_get(url, key, "users_profile", {"select": "id,email", "limit": 1000}) }
        for row in profile_rows:
            email = (row.get("email") or "").strip().lower()
            current = existing_profiles.get(email)
            if current and current.get("id") != row.get("id"):
                id_map[row.get("id")] = current.get("id")
                body = {k: v for k, v in row.items() if k != "id"}
                pg_patch(url, key, "users_profile", {"id": f"eq.{current.get('id')}"}, body)
            elif current:
                body = {k: v for k, v in row.items() if k != "id"}
                pg_patch(url, key, "users_profile", {"id": f"eq.{row.get('id')}"}, body)
            else:
                pg_insert(url, key, "users_profile", row)
    report.append(f"users_profile: {len(profile_rows)} baris" + ("" if not dry_run else " (rencana)"))

    for table in TABLE_ORDER:
        if table == "users_profile":
            continue
        rows = read_json(db_dir / f"{table}.json", [])
        if not rows:
            continue
        if not dry_run:
            mapped = []
            for row in rows:
                r = dict(row)
                if table in USER_REF_TABLES and r.get("user_id") in id_map:
                    r["user_id"] = id_map[r.get("user_id")]
                mapped.append(r)
            done = pg_upsert(url, key, table, mapped, TABLE_PK[table])
            report.append(f"{table}: {done} baris")
        else:
            report.append(f"{table}: {len(rows)} baris (rencana)")
    return passwords


def apply_github(work, new_repo, env_backup):
    variables = read_json(work / "github" / "variables.json", [])
    if isinstance(variables, list):
        for item in variables:
            name = item.get("name")
            value = item.get("value")
            if not name or value is None:
                continue
            subprocess.run(["gh", "variable", "set", name, "-R", new_repo, "--body", str(value)], check=False)
    for name, value in env_backup.items():
        if name in GITHUB_SECRET_ENV:
            subprocess.run(["gh", "secret", "set", name, "-R", new_repo, "--body", value], check=False)


def main():
    parser = argparse.ArgumentParser(description="Restore/duplikasi sistem BrandBisnis V5.0 dari arsip backup")
    parser.add_argument("--archive", help="File duplicator-*.tar.gz")
    parser.add_argument("--workdir", help="Folder hasil backup (tanpa arsip)")
    parser.add_argument("--target-url", default=os.getenv("SUPABASE_URL", ""), help="URL project Supabase tujuan")
    parser.add_argument("--target-service-key", default=os.getenv("SUPABASE_SERVICE_KEY", ""), help="Service key project tujuan")
    parser.add_argument("--dry-run", action="store_true", help="Hanya tampilkan rencana, tanpa menulis")
    parser.add_argument("--yes", action="store_true", help="Konfirmasi tulis ke project tujuan")
    parser.add_argument("--skip-auth", action="store_true", help="Jangan buat user auth (hanya data)")
    parser.add_argument("--new-repo", help="Repo GitHub tujuan (owner/nama) untuk set variables/secrets")
    parser.add_argument("--apply-github", action="store_true", help="Set variables/secrets ke --new-repo")
    parser.add_argument("--deploy-worker", action="store_true", help="Jalankan wrangler deploy dari cloudflare/bot-cron")
    parser.add_argument("--auth-password", default=os.getenv("RESTORE_TEMP_PASSWORD", ""), help="Password sementara seragam untuk user auth baru")
    args = parser.parse_args()

    work, tmp = resolve_workdir(args.archive, args.workdir)
    try:
        plan_summary(work)
        if not args.target_url or not args.target_service_key:
            raise SystemExit("Butuh --target-url dan --target-service-key (project tujuan)")
        target_url = args.target_url.rstrip("/")
        dry_run = args.dry_run or not args.yes
        print("")
        print(f"Target: {target_url}")
        print("Mode  : DRY-RUN" if dry_run else "Mode  : TULIS")
        env_backup = load_env_backup(work)
        report = []
        passwords = restore_db(target_url, args.target_service_key, work, dry_run, args.skip_auth, report, args.auth_password or None)
        print("")
        for line in report:
            print("  -", line)
        if passwords:
            out = work / "restored" / "auth_passwords.txt"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text("\n".join(f"{k}={v}" for k, v in passwords.items()) + "\n", encoding="utf-8")
            os.chmod(out, 0o600)
            print(f"  Password sementara auth user: {out}")
        elif args.auth_password and not dry_run and not args.skip_auth:
            print("  Password sementara user baru memakai nilai RESTORE_TEMP_PASSWORD")
        print("")
        if args.apply_github and args.new_repo:
            apply_github(work, args.new_repo, env_backup)
            print(f"GitHub variables/secrets diset ke {args.new_repo} (secret yang tidak tersedia dilewati)")
        if args.deploy_worker:
            repo_root = Path(__file__).resolve().parents[2]
            worker_dir = repo_root / "cloudflare" / "bot-cron"
            if worker_dir.exists():
                subprocess.run(["npx", "wrangler", "deploy"], cwd=str(worker_dir), check=False)
        print("")
        print("Langkah manual yang tersisa:")
        print("  1. Clone repo dari repo.bundle: git clone repo.bundle robot-otomatis && cd robot-otomatis")
        print("  2. gh repo create <owner>/<nama> --private --source=. --push")
        print("  3. Set secret Worker: GITHUB_PAT, TRIGGER_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID")
        print("  4. Simpan SETTINGS_ENC_KEY lama agar API key user bisa didekripsi")
        print("  5. Jalankan workflow cron-vst.yml untuk verifikasi")
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
