#!/usr/bin/env python3
"""mCore Local Engine — read-only status server on 127.0.0.1:8787."""
import json
import os
import subprocess
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

BACKUP_ROOT = Path("/srv/backups/mcore")
DOGET = Path("/srv/doGet")
MCORE = Path("/srv/mcore")
PORT = int(os.environ.get("MCORE_ENGINE_PORT", "8787"))


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception as e:
        return f"error: {e}"


def _git(path):
    if not (path / ".git").exists():
        return None
    return {
        "sha": _run(["git", "-C", str(path), "rev-parse", "HEAD"]),
        "short": _run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"]),
        "branch": _run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"]),
        "remote": _run(["git", "-C", str(path), "remote", "get-url", "origin"]),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a, **kw):
        pass

    def _send(self, code, body, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if isinstance(body, (dict, list)):
            self.wfile.write(json.dumps(body, indent=2).encode())
        else:
            self.wfile.write(body.encode() if isinstance(body, str) else body)

    def do_GET(self):
        p = self.path.split("?")[0]

        if p == "/health":
            return self._send(200, {
                "status": "ok",
                "time": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
            })

        if p == "/status":
            return self._send(200, {
                "host": _run(["hostname"]),
                "kernel": _run(["uname", "-r"]),
                "uptime": _run(["uptime", "-p"]),
                "disk": _run(["df", "-h", "/srv"]),
                "mcore": _git(MCORE),
                "doget": _git(DOGET),
            })

        if p == "/backups":
            if not BACKUP_ROOT.exists():
                return self._send(200, {"backups": [], "note": "no backups yet"})
            items = []
            for f in sorted(BACKUP_ROOT.glob("mcore-full-*.tar.zst"), reverse=True):
                items.append({
                    "name": f.name,
                    "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
                    "mtime": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(),
                })
            return self._send(200, {"count": len(items), "backups": items[:20]})

        if p == "/manifest":
            manifests = sorted(BACKUP_ROOT.glob("mcore-manifest-*.json"), reverse=True)
            if not manifests:
                return self._send(404, {"error": "no manifest"})
            return self._send(200, json.loads(manifests[0].read_text()))

        if p == "/dashboard":
            idx = DOGET / "dashboard" / "index.html"
            if idx.exists():
                return self._send(200, idx.read_bytes(), "text/html")
            return self._send(200, "<h1>mCore Engine</h1><p>No dashboard yet.</p>", "text/html")

        if p == "/":
            return self._send(200, {
                "name": "mCore Local Engine",
                "version": "0.1.0",
                "endpoints": ["/health", "/status", "/backups", "/manifest", "/dashboard"],
            })

        return self._send(404, {"error": "not found", "path": p})


if __name__ == "__main__":
    addr = ("127.0.0.1", PORT)
    print(f"mCore Local Engine listening on http://{addr[0]}:{addr[1]}", flush=True)
    HTTPServer(addr, Handler).serve_forever()
