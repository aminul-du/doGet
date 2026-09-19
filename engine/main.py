from fastapi import FastAPI
from pathlib import Path
from datetime import datetime, timezone
import json, os, subprocess

app = FastAPI(title="doGet Engine", version="0.2.0")
BACKUP_ROOT = Path("/srv/backups/mcore")
MCORE = Path("/srv/mcore")
DOGET = Path("/srv/doGet")

def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception as e:
        return f"error: {e}"

def git_state(p):
    if not (p / ".git").exists():
        return None
    return {
        "sha": run(["git", "-C", str(p), "rev-parse", "HEAD"]),
        "short": run(["git", "-C", str(p), "rev-parse", "--short", "HEAD"]),
        "branch": run(["git", "-C", str(p), "rev-parse", "--abbrev-ref", "HEAD"]),
        "remote": run(["git", "-C", str(p), "remote", "get-url", "origin"]),
    }

@app.get("/")
def root():
    return {"name": "doGet Engine", "version": "0.2.0",
            "endpoints": ["/health", "/status", "/backups", "/manifest", "/dashboard"]}

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat(), "pid": os.getpid()}

@app.get("/status")
def status():
    return {
        "host": run(["hostname"]),
        "kernel": run(["uname", "-r"]),
        "uptime": run(["uptime", "-p"]),
        "disk": run(["df", "-h", "/srv"]),
        "mcore": git_state(MCORE),
        "doget": git_state(DOGET),
    }

@app.get("/backups")
def backups():
    if not BACKUP_ROOT.exists():
        return {"backups": [], "note": "none yet"}
    items = []
    for f in sorted(BACKUP_ROOT.glob("mcore-full-*.tar.zst"), reverse=True):
        items.append({"name": f.name,
                      "size_mb": round(f.stat().st_size/1024/1024, 2),
                      "mtime": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat()})
    return {"count": len(items), "backups": items[:20]}

@app.get("/manifest")
def manifest():
    ms = sorted(BACKUP_ROOT.glob("mcore-manifest-*.json"), reverse=True)
    if not ms:
        return {"error": "no manifest"}
    return json.loads(ms[0].read_text())

@app.get("/dashboard")
def dashboard():
    idx = DOGET / "dashboard" / "index.html"
    if idx.exists():
        return {"dashboard": idx.read_text()[:200] + "..."}
    return {"dashboard": "not generated yet"}
