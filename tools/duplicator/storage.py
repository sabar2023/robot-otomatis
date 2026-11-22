import argparse
import os
import sys
from pathlib import Path

import requests

DEFAULT_BUCKET = "system-backups"


def load_env():
    root = Path(__file__).resolve().parents[2]
    for path in (root / "vst" / ".env", root / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


load_env()


def conf(url, key):
    url = (url or os.getenv("SUPABASE_URL") or "https://jklbczruvbxscpwxxfud.supabase.co").rstrip("/")
    key = (key or os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY") or "").strip()
    if not url or not key:
        raise SystemExit("SUPABASE_URL dan service key wajib")
    return url, key


def auth(key):
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def ensure_bucket(url, key, bucket):
    resp = requests.post(
        f"{url}/storage/v1/bucket",
        headers={**auth(key), "Content-Type": "application/json"},
        json={"id": bucket, "name": bucket, "public": False},
        timeout=30,
    )
    if resp.status_code in (200, 201, 400, 409):
        return True
    return False


def upload(local_path, object_name, bucket=DEFAULT_BUCKET, url=None, key=None):
    url, key = conf(url, key)
    ensure_bucket(url, key, bucket)
    path = Path(local_path)
    with open(path, "rb") as fh:
        resp = requests.post(
            f"{url}/storage/v1/object/{bucket}/{object_name}",
            headers={
                **auth(key),
                "Content-Type": "application/gzip",
                "x-upsert": "true",
            },
            data=fh,
            timeout=300,
        )
    if resp.status_code >= 300:
        raise RuntimeError(f"upload gagal: HTTP {resp.status_code} {resp.text[:200]}")
    return f"{bucket}/{object_name}"


def download(object_name, out_path, bucket=DEFAULT_BUCKET, url=None, key=None):
    url, key = conf(url, key)
    resp = requests.get(
        f"{url}/storage/v1/object/{bucket}/{object_name}",
        headers=auth(key),
        timeout=300,
    )
    if resp.status_code >= 300:
        raise RuntimeError(f"download gagal: HTTP {resp.status_code} {resp.text[:200]}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(resp.content)
    return out


def main():
    parser = argparse.ArgumentParser(description="Upload/download arsip backup Supabase Storage")
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--url", default=None)
    parser.add_argument("--key", default=None)
    parser.add_argument("--upload", metavar="FILE")
    parser.add_argument("--object", default=None)
    parser.add_argument("--download", metavar="OBJECT")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.upload:
        name = args.object or Path(args.upload).name
        print(f"OBJECT_PATH={upload(args.upload, name, args.bucket, args.url, args.key)}")
    elif args.download:
        out = args.out or Path(args.download).name
        path = download(args.download, out, args.bucket, args.url, args.key)
        print(f"DOWNLOADED={path}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {str(exc)[:300]}", file=sys.stderr)
        sys.exit(1)
