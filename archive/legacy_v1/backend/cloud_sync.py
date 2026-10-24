import logging

import httpx

import database as db

log = logging.getLogger("cloud_sync")


class CloudSync:
    def __init__(self, timeout=8.0):
        self.timeout = timeout
        self.last_status = "IDLE"
        self.last_sync = None
        self.last_error = ""

    def _endpoint(self, path):
        secrets = db.get_secrets()
        base = (secrets.get("worker_url") or "").rstrip("/")
        if not base:
            return None, None, secrets
        return f"{base}{path}", secrets, secrets

    def _headers(self, secrets):
        headers = {"Content-Type": "application/json"}
        if secrets.get("worker_token"):
            headers["Authorization"] = f"Bearer {secrets['worker_token']}"
        return headers

    def _guard(self):
        secrets = db.get_secrets()
        if not secrets.get("cloud_sync_enabled"):
            return None, "Cloud sync nonaktif"
        if not secrets.get("worker_url"):
            return None, "worker_url belum diatur"
        return secrets, None

    def pull_config(self):
        """Langkah 1 PRD: tarik global_kill_switch dari Cloudflare D1 sebelum analisis."""
        secrets, err = self._guard()
        if err:
            return None
        url = f"{(secrets['worker_url']).rstrip('/')}/api/config"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.get(url, headers=self._headers(secrets))
                res.raise_for_status()
                data = res.json()
                remote_kill = bool(data.get("global_kill_switch"))
                local = db.get_config()
                if remote_kill and not local["global_kill_switch"]:
                    db.update_config(global_kill_switch=True)
                    db.insert_agent_log("CLOUD", "Remote kill switch LOCKED dari D1 diterapkan.", "WARN")
                self.last_status = "OK"
                return data
        except Exception as exc:
            self.last_status = "ERROR"
            self.last_error = str(exc)
            log.warning("pull_config failed: %s", exc)
            return None

    def _post(self, path, payload):
        secrets, err = self._guard()
        if err:
            return False
        url = f"{(secrets['worker_url']).rstrip('/')}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                res = client.post(url, json=payload, headers=self._headers(secrets))
                res.raise_for_status()
                self.last_status = "OK"
                self.last_sync = db.utcnow()
                return True
        except Exception as exc:
            self.last_status = "ERROR"
            self.last_error = str(exc)
            log.warning("post %s failed: %s", path, exc)
            return False

    def push_config(self):
        cfg = db.get_secrets()
        return self._post(
            "/api/config",
            {
                "execution_mode": db.get_config()["execution_mode"],
                "global_kill_switch": db.get_config()["global_kill_switch"],
                "max_daily_drawdown": db.get_config()["max_daily_drawdown"],
            },
        )

    def push_batch(self, trades):
        """Langkah 4 PRD: kirim log JSON ke Workers untuk direkam ke D1."""
        if not trades:
            return True
        return self._post("/api/trades/batch", {"trades": trades})

    def push_agent_logs(self, logs):
        if not logs:
            return True
        return self._post("/api/logs/batch", {"logs": logs})

    def push_equity(self, snapshot):
        return self._post("/api/equity", snapshot)

    def backup_csv(self, filename, content):
        return self._post("/api/r2/backup", {"filename": filename, "content": content})

    def status(self):
        return {
            "last_status": self.last_status,
            "last_sync": self.last_sync,
            "last_error": self.last_error,
        }


sync = CloudSync()
