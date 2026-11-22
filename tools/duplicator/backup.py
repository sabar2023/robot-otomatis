import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
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

ENV_KEYS = [
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_PAT",
    "SETTINGS_ENC_KEY",
    "BINGX_API_KEY",
    "BINGX_SECRET_KEY",
    "BINGX_BACKUP_API_KEY",
    "BINGX_BACKUP_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "CLOUDFLARE_API_TOKEN",
    "VST_LIVE",
    "VST_TIMEFRAME",
    "VST_EXEC_MODE",
    "VST_MARGIN_PCT",
    "VST_FIXED_MARGIN_PCT",
    "VST_LEVERAGE_MAX",
    "VST_SL_PCT",
    "VST_TP_PCT",
    "VST_TP1_PCT",
    "VST_TP1_FRACTION",
    "VST_MIN_ORDER_USDT",
    "VST_WATCHLIST_SIZE",
    "VST_DATA_EXCHANGES",
    "VST_RISK_MODE",
]

AUTH_DROP = {
    "encrypted_password",
    "confirmation_token",
    "recovery_token",
    "email_change_token_new",
    "email_change_token_current",
    "email_change",
    "phone_change",
    "phone_change_token",
    "reauthentication_token",
}


def root_dir():
    return Path(__file__).resolve().parents[2]


def load_env(root):
    for path in (root / "vst" / ".env", root / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def supabase_conf():
    url = (os.getenv("SUPABASE_URL") or "https://jklbczruvbxscpwxxfud.supabase.co").rstrip("/")
    key = (os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    return url, key


def api_headers(key):
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def fetch_table(url, key, table, page_size=1000):
    rows = []
    start = 0
    while True:
        headers = api_headers(key)
        headers["Range"] = f"{start}-{start + page_size - 1}"
        headers["Prefer"] = "count=exact"
        resp = requests.get(
            f"{url}/rest/v1/{table}",
            headers=headers,
            params={"select": "*"},
            timeout=60,
        )
        if resp.status_code not in (200, 206):
            raise RuntimeError(f"{table}: HTTP {resp.status_code} {resp.text[:150]}")
        chunk = resp.json()
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        start += page_size
    return rows


def fetch_auth_users(url, key, page_size=200):
    users = []
    page = 1
    while True:
        resp = requests.get(
            f"{url}/auth/v1/admin/users",
            headers=api_headers(key),
            params={"page": page, "per_page": page_size},
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"auth users: HTTP {resp.status_code} {resp.text[:150]}")
        data = resp.json()
        batch = data.get("users") if isinstance(data, dict) else data
        batch = batch or []
        for user in batch:
            users.append({k: v for k, v in user.items() if k not in AUTH_DROP})
        if len(batch) < page_size:
            break
        page += 1
    return users


def gh_json(args):
    try:
        proc = subprocess.run(
            ["gh", *args],
            capture_output=True,
            text=True,
            timeout=90,
        )
        if proc.returncode != 0:
            return {"error": (proc.stderr or proc.stdout).strip()[:200]}
        return json.loads(proc.stdout or "[]")
    except Exception as exc:
        return {"error": str(exc)[:200]}


def run(cmd, cwd=None, timeout=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def git_commit(root):
    proc = run(["git", "-C", str(root), "rev-parse", "HEAD"])
    return (proc.stdout or "").strip()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")


def write_secret_file(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def build_worker_info(root):
    worker_dir = root / "cloudflare" / "bot-cron"
    info = {
        "dir": str(worker_dir.relative_to(root)) if worker_dir.exists() else None,
        "wrangler": None,
        "secrets": None,
    }
    toml = worker_dir / "wrangler.toml"
    if toml.exists():
        info["wrangler"] = toml.read_text(encoding="utf-8", errors="ignore")
    if worker_dir.exists():
        wrangler = shutil.which("wrangler")
        cmd = [wrangler, "secret", "list", "--name", "bot-cron"] if wrangler else ["npx", "wrangler", "secret", "list", "--name", "bot-cron"]
        proc = run(cmd, cwd=str(worker_dir), timeout=120)
        text = (proc.stdout or proc.stderr or "").strip()
        info["secrets"] = text[:2000]
    return info


def main():
    parser = argparse.ArgumentParser(description="Backup lengkap sistem BrandBisnis V5.0 untuk duplikasi")
    parser.add_argument("--out-dir", default=None, help="Folder arsip backup (default: backups/)")
    parser.add_argument("--repo", default=os.getenv("GITHUB_REPO", "sabar2023/robot-otomatis"))
    parser.add_argument("--skip-gh", action="store_true", help="Lewati export variabel/secret GitHub")
    parser.add_argument("--skip-worker", action="store_true", help="Lewati cek secret Cloudflare Worker")
    parser.add_argument("--no-git-bundle", action="store_true", help="Lewati git bundle")
    parser.add_argument("--upload-supabase", action="store_true", help="Unggah arsip ke Supabase Storage privat")
    parser.add_argument("--bucket", default=storage.DEFAULT_BUCKET, help="Nama bucket Supabase Storage")
    args = parser.parse_args()

    root = root_dir()
    load_env(root)
    out_root = Path(args.out_dir) if args.out_dir else (root / "backups")
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    work = out_root / f"duplicator-{stamp}"
    work.mkdir(parents=True, exist_ok=True)

    url, key = supabase_conf()
    manifest = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "system": "BrandBisnis V5.0",
        "commit": git_commit(root),
        "repo": args.repo,
        "supabase_url": url,
        "tables": {},
        "auth_users": 0,
    }

    print(f"[1/7] Git bundle")
    if not args.no_git_bundle:
        bundle = work / "repo.bundle"
        proc = run(["git", "-C", str(root), "bundle", "create", str(bundle), "--all"])
        if proc.returncode != 0:
            print(f"  WARN git bundle: {(proc.stderr or '').strip()[:200]}")
        else:
            manifest["repo_bundle"] = bundle.name
            print(f"  {bundle.name} ({bundle.stat().st_size / 1024:.0f} KB)")

    print("[2/7] Supabase tables")
    if not (url and key):
        raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY tidak tersedia")
    for table in TABLE_ORDER:
        try:
            rows = fetch_table(url, key, table)
            save_json(work / "db" / f"{table}.json", rows)
            manifest["tables"][table] = {"rows": len(rows), "pk": TABLE_PK[table]}
            print(f"  {table}: {len(rows)} baris")
        except Exception as exc:
            manifest["tables"][table] = {"error": str(exc)[:200], "pk": TABLE_PK[table]}
            print(f"  {table}: ERROR {str(exc)[:120]}")

    print("[3/7] Supabase auth users")
    try:
        users = fetch_auth_users(url, key)
        save_json(work / "auth" / "users.json", users)
        manifest["auth_users"] = len(users)
        print(f"  {len(users)} auth user (password tidak dapat diekspor)")
    except Exception as exc:
        manifest["auth_users_error"] = str(exc)[:200]
        print(f"  ERROR {str(exc)[:120]}")

    print("[4/7] GitHub variables/secrets/workflows")
    if not args.skip_gh:
        variables = gh_json(["variable", "list", "-R", args.repo, "--json", "name,value"])
        secrets = gh_json(["secret", "list", "-R", args.repo, "--json", "name,updatedAt"])
        workflows = gh_json(["workflow", "list", "-R", args.repo, "--json", "name,path,state"])
        save_json(work / "github" / "variables.json", variables)
        save_json(work / "github" / "secrets.json", secrets)
        save_json(work / "github" / "workflows.json", workflows)
        vcount = len(variables) if isinstance(variables, list) else 0
        scount = len(secrets) if isinstance(secrets, list) else 0
        print(f"  variables={vcount} secrets(nama saja)={scount}")

    print("[5/7] Cloudflare Worker")
    if not args.skip_worker:
        worker = build_worker_info(root)
        save_json(work / "cloudflare" / "worker.json", worker)
        print(f"  dir={worker.get('dir')}")

    print("[6/7] Env rahasia")
    env_lines = []
    for name in ENV_KEYS:
        value = os.getenv(name)
        if value:
            env_lines.append(f"{name}={value}")
    write_secret_file(work / "secrets" / "env.backup", env_lines)
    os.chmod(work / "secrets", 0o700)
    manifest["env_keys"] = [line.split("=", 1)[0] for line in env_lines]
    print(f"  {len(env_lines)} variabel disimpan di secrets/env.backup (mode 600)")

    save_json(work / "manifest.json", manifest)

    print("[7/7] Arsip tar.gz")
    archive = out_root / f"duplicator-{stamp}.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(work, arcname=work.name)
    digest = sha256_file(archive)
    (out_root / f"duplicator-{stamp}.sha256").write_text(f"{digest}  {archive.name}\n", encoding="utf-8")

    print("")
    print(f"SELESAI: {archive}")
    print(f"SHA256 : {digest}")
    print(f"Folder : {work}")
    print("Arsip ini memuat rahasia. Jangan commit/push; simpan di tempat aman.")

    if args.upload_supabase:
        try:
            object_name = archive.name
            object_path = storage.upload(archive, object_name, args.bucket, url, key)
            sha_object = f"{object_name}.sha256"
            storage.upload(out_root / f"duplicator-{stamp}.sha256", sha_object, args.bucket, url, key)
            print(f"OBJECT_PATH={object_path}")
        except Exception as exc:
            print(f"UPLOAD_ERROR={str(exc)[:250]}")
            sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
