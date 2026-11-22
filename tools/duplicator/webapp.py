import argparse
import datetime as dt
import json
import os
import secrets
import string
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = ROOT / "tools" / "duplicator" / "web"
BACKUP_DIR = ROOT / "backups"
LOCK = threading.Lock()
STATE = {"busy": False, "message": ""}


def archives():
    if not BACKUP_DIR.exists():
        return []
    items = []
    for path in sorted(BACKUP_DIR.glob("duplicator-*.tar.gz"), reverse=True):
        stat = path.stat()
        items.append({
            "name": path.name,
            "size": stat.st_size,
            "mtime": dt.datetime.fromtimestamp(stat.st_mtime, dt.timezone.utc).isoformat(),
        })
    return items


def run_script(args, timeout=1800):
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ.copy(),
    )
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    return proc.returncode, output.strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "Duplicator/1.0"
    token = ""

    def log_message(self, fmt, *args):
        return

    def _json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path, content_type):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self, token):
        return bool(self.token) and token == self.token

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path in ("/", "/index.html"):
            self._file(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/api/state":
            token = (query.get("token") or [""])[0] or self.headers.get("X-Token", "")
            if not self._authed(token):
                self._json(401, {"error": "token salah"})
                return
            self._json(200, {
                "backups": archives(),
                "busy": STATE["busy"],
                "message": STATE["message"],
                "repo": os.getenv("GITHUB_REPO", "sabar2023/robot-otomatis"),
            })
            return
        if parsed.path == "/download":
            token = (query.get("token") or [""])[0]
            name = (query.get("name") or [""])[0]
            if not self._authed(token):
                self._json(401, {"error": "token salah"})
                return
            target = BACKUP_DIR / name
            if not name.startswith("duplicator-") or not target.exists():
                self._json(404, {"error": "arsip tidak ditemukan"})
                return
            self._file(target, "application/gzip")
            return
        self._json(404, {"error": "tidak ditemukan"})

    def do_POST(self):
        parsed = urlparse(self.path)
        body = self._read_body()
        token = body.get("token") or self.headers.get("X-Token", "")
        if not self._authed(token):
            self._json(401, {"error": "token salah"})
            return
        if parsed.path == "/api/backup":
            if STATE["busy"]:
                self._json(409, {"error": "proses lain sedang berjalan"})
                return
            STATE["busy"] = True
            STATE["message"] = "membuat backup"
            try:
                code, output = run_script([sys.executable, "tools/duplicator/backup.py"])
                self._json(200, {"ok": code == 0, "output": output, "backups": archives()})
            except Exception as exc:
                self._json(500, {"ok": False, "output": str(exc)[:500]})
            finally:
                STATE["busy"] = False
                STATE["message"] = ""
            return
        if parsed.path == "/api/restore":
            archive = (body.get("archive") or "").strip()
            target_url = (body.get("target_url") or "").strip()
            target_key = (body.get("target_service_key") or "").strip()
            if not archive or not target_url or not target_key:
                self._json(400, {"error": "archive, target_url, target_service_key wajib"})
                return
            args = [
                sys.executable, "tools/duplicator/restore.py",
                "--archive", str(BACKUP_DIR / archive) if not os.path.isabs(archive) else archive,
                "--target-url", target_url,
                "--target-service-key", target_key,
            ]
            if body.get("skip_auth"):
                args.append("--skip-auth")
            if body.get("new_repo"):
                args += ["--new-repo", body["new_repo"].strip()]
            if body.get("apply_github"):
                args.append("--apply-github")
            if body.get("deploy_worker"):
                args.append("--deploy-worker")
            if not body.get("dry_run"):
                args.append("--yes")
            else:
                args.append("--dry-run")
            try:
                code, output = run_script(args)
                self._json(200, {"ok": code == 0, "output": output})
            except Exception as exc:
                self._json(500, {"ok": False, "output": str(exc)[:500]})
            return
        self._json(404, {"error": "tidak ditemukan"})


def main():
    parser = argparse.ArgumentParser(description="Web duplicator backup/restore BrandBisnis V5.0")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--token", default=os.getenv("DUPLICATOR_TOKEN", ""))
    args = parser.parse_args()

    token = args.token.strip()
    if not token:
        alphabet = string.ascii_letters + string.digits
        token = "".join(secrets.choice(alphabet) for _ in range(16))
    Handler.token = token

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Duplicator web berjalan di http://{args.host}:{args.port}/?token={token}")
    print("Token akses:", token)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
