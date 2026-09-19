from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pathlib import Path
from datetime import datetime, timezone
import json, os, subprocess

app = FastAPI(title="doGet Engine", version="0.3.0")

BACKUP_ROOT = Path("/srv/backups/mcore")
MCORE = Path("/srv/mcore")
DOGET = Path("/srv/doGet")

REPOS = [
    {"name": "mCore",         "path": "/srv/mcore"},
    {"name": "mCore Library", "path": "/srv/mcore/platform/mCore-Library"},
    {"name": "mCore 365",     "path": "/srv/mCore365"},
    {"name": "doGet Engine",  "path": "/srv/doGet"},
]


def run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception:
        return ""


def git_state(path):
    p = Path(path)
    if not (p / ".git").exists():
        return {"status": "no-repo"}
    branch = run(["git", "-C", path, "rev-parse", "--abbrev-ref", "HEAD"]) or "?"
    head = run(["git", "-C", path, "rev-parse", "--short", "HEAD"]) or "?"
    remote = run(["git", "-C", path, "remote", "get-url", "origin"]) or "local only"
    status_raw = run(["git", "-C", path, "status", "--short"])
    dirty_lines = [l for l in status_raw.splitlines() if l.strip()]
    log_raw = run(["git", "-C", path, "log",
                   "--pretty=format:%h|%ad|%an|%s", "-25", "--date=iso-strict"])
    commits = []
    for line in log_raw.splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "sha": parts[0], "date": parts[1],
                "author": parts[2], "subject": parts[3],
            })
    behind = ahead = 0
    ab = run(["git", "-C", path, "rev-list", "--left-right",
              "--count", f"origin/{branch}...HEAD"])
    if ab and " " in ab:
        try:
            behind, ahead = map(int, ab.split())
        except Exception:
            pass
    return {
        "status": "ok",
        "branch": branch,
        "head": head,
        "remote": remote,
        "dirty": bool(dirty_lines),
        "dirty_count": len(dirty_lines),
        "behind": behind,
        "ahead": ahead,
        "commits": commits,
        "commit_count": len(commits),
    }


@app.get("/")
def root():
    return {
        "name": "doGet Engine",
        "version": "0.3.0",
        "endpoints": ["/health", "/status", "/backups", "/manifest",
                      "/dashboard", "/goGit", "/api/gogit"],
    }


@app.get("/health")
def health():
    return {"status": "ok",
            "time": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid()}


@app.get("/status")
def status():
    return {
        "host": run(["hostname"]),
        "kernel": run(["uname", "-r"]),
        "uptime": run(["uptime", "-p"]),
        "disk": run(["df", "-h", "/srv"]),
        "mcore": git_state(str(MCORE)),
        "doget": git_state(str(DOGET)),
    }


@app.get("/backups")
def backups():
    if not BACKUP_ROOT.exists():
        return {"backups": [], "note": "none yet"}
    items = []
    for f in sorted(BACKUP_ROOT.glob("mcore-full-*.tar.zst"), reverse=True):
        items.append({
            "name": f.name,
            "size_mb": round(f.stat().st_size / 1024 / 1024, 2),
            "mtime": datetime.fromtimestamp(f.stat().st_mtime, timezone.utc).isoformat(),
        })
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


@app.get("/api/gogit")
def api_gogit():
    repos_out = []
    total_commits = 0
    total_dirty = 0
    total_ahead = 0
    for r in REPOS:
        state = git_state(r["path"])
        entry = {**r, **state}
        repos_out.append(entry)
        if state.get("status") == "ok":
            total_commits += state.get("commit_count", 0)
            if state.get("dirty"):
                total_dirty += 1
            total_ahead += state.get("ahead", 0)
    return {
        "updated": datetime.now(timezone.utc).isoformat(),
        "totals": {
            "repos": len(REPOS),
            "commits_sampled": total_commits,
            "dirty_repos": total_dirty,
            "ahead_total": total_ahead,
        },
        "repos": repos_out,
    }


HTML_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>goGit — git work history</title>
<style>
:root{
  --bg:#0d1117;--panel:#161b22;--panel2:#1c2128;--border:#30363d;
  --text:#c9d1d9;--text2:#8b949e;--text3:#6e7681;
  --accent:#58a6ff;--ok:#3fb950;--warn:#d29922;--err:#f85149;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);
  font:14px/1.5 -apple-system,"Segoe UI",Roboto,sans-serif;min-height:100vh}
.header{padding:24px 32px;border-bottom:1px solid var(--border);
  background:var(--panel);position:sticky;top:0;z-index:10}
.header h1{margin:0;font-size:22px;font-weight:600;letter-spacing:-.01em}
.header .sub{margin-top:4px;color:var(--text2);font-size:13px}
.wrap{padding:24px 32px;max-width:1400px;margin:0 auto}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
  gap:12px;margin-bottom:24px}
.stat{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:16px}
.stat .lbl{color:var(--text3);font-size:11px;text-transform:uppercase;
  letter-spacing:.06em;font-weight:600}
.stat .val{font-size:26px;font-weight:300;margin-top:6px;
  font-variant-numeric:tabular-nums;color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:16px}
.card{background:var(--panel);border:1px solid var(--border);
  border-radius:8px;overflow:hidden}
.card-h{padding:16px 18px;border-bottom:1px solid var(--border);
  display:flex;justify-content:space-between;align-items:flex-start;gap:12px}
.card-h .name{font-size:15px;font-weight:600;color:#fff}
.card-h .path{font-family:var(--mono);font-size:11px;
  color:var(--text3);margin-top:3px}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:8px}
.badge{font-size:11px;padding:2px 8px;border-radius:999px;font-weight:500;
  background:var(--panel2);color:var(--text2);font-family:var(--mono)}
.badge.ok{background:rgba(63,185,80,.12);color:var(--ok)}
.badge.warn{background:rgba(210,153,34,.12);color:var(--warn)}
.badge.err{background:rgba(248,81,73,.12);color:var(--err)}
.badge.acc{background:rgba(88,166,255,.12);color:var(--accent)}
.meta{padding:12px 18px;border-bottom:1px solid var(--border);
  display:grid;grid-template-columns:auto 1fr;gap:4px 14px;font-size:12px}
.meta dt{color:var(--text3);font-family:var(--mono)}
.meta dd{margin:0;color:var(--text);font-family:var(--mono);word-break:break-all}
.commits{max-height:420px;overflow-y:auto;padding:4px 0}
.commit{padding:8px 18px;border-bottom:1px solid rgba(48,54,61,.5);
  display:grid;grid-template-columns:auto 1fr;gap:4px 12px;font-size:12px}
.commit:last-child{border-bottom:0}
.commit .sha{font-family:var(--mono);color:var(--accent);font-size:11px}
.commit .msg{color:var(--text);word-break:break-word}
.commit .meta2{grid-column:2;color:var(--text3);font-size:11px;font-family:var(--mono)}
.commit:hover{background:var(--panel2)}
.empty{padding:24px;text-align:center;color:var(--text3);font-size:12px}
.footer{padding:16px 32px;color:var(--text3);font-size:11px;
  text-align:center;font-family:var(--mono);border-top:1px solid var(--border);
  margin-top:32px}
.pulse{display:inline-block;width:6px;height:6px;border-radius:50%;
  background:var(--ok);margin-right:6px;animation:p 2s infinite}
@keyframes p{0%,100%{opacity:1}50%{opacity:.35}}
</style>
</head>
<body>
<div class="header">
  <h1><span class="pulse"></span>goGit</h1>
  <div class="sub">live git work history · <span id="updated">loading…</span></div>
</div>
<div class="wrap">
  <div class="summary" id="summary"></div>
  <div class="grid" id="grid"></div>
</div>
<div class="footer">127.0.0.1:8787/goGit · refreshes every 30s · local only</div>
<script>
function esc(s){return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}[c]))}
function ago(iso){
  try{
    const d=new Date(iso),n=new Date(),s=(n-d)/1000;
    if(s<60)return Math.floor(s)+"s ago";
    if(s<3600)return Math.floor(s/60)+"m ago";
    if(s<86400)return Math.floor(s/3600)+"h ago";
    return Math.floor(s/86400)+"d ago";
  }catch(e){return iso}
}
function render(data){
  document.getElementById("updated").textContent="updated "+ago(data.updated);
  const t=data.totals;
  document.getElementById("summary").innerHTML=`
    <div class="stat"><div class="lbl">Repositories</div><div class="val">${t.repos}</div></div>
    <div class="stat"><div class="lbl">Commits sampled</div><div class="val">${t.commits_sampled}</div></div>
    <div class="stat"><div class="lbl">Clean repos</div><div class="val">${t.repos-t.dirty_repos}/${t.repos}</div></div>
    <div class="stat"><div class="lbl">Ahead of remote</div><div class="val">${t.ahead_total}</div></div>
  `;
  const grid=document.getElementById("grid");
  grid.innerHTML=data.repos.map(r=>{
    if(r.status!=="ok"){
      return `<div class="card"><div class="card-h"><div><div class="name">${esc(r.name)}</div><div class="path">${esc(r.path)}</div></div><span class="badge err">no repo</span></div><div class="empty">Not a git repository yet.</div></div>`;
    }
    const treeBadge=r.dirty
      ?`<span class="badge warn">dirty · ${r.dirty_count}</span>`
      :`<span class="badge ok">clean</span>`;
    const syncBadge=r.ahead>0
      ?`<span class="badge err">ahead ${r.ahead}</span>`
      :r.behind>0
        ?`<span class="badge warn">behind ${r.behind}</span>`
        :`<span class="badge ok">synced</span>`;
    const commits=r.commits.length?r.commits.map(c=>`
      <div class="commit">
        <span class="sha">${esc(c.sha)}</span>
        <span class="msg">${esc(c.subject)}</span>
        <span class="meta2">${esc(c.author)} · ${ago(c.date)}</span>
      </div>`).join(""):`<div class="empty">No commits yet.</div>`;
    return `
      <div class="card">
        <div class="card-h">
          <div>
            <div class="name">${esc(r.name)}</div>
            <div class="path">${esc(r.path)}</div>
            <div class="badges">
              <span class="badge acc">${esc(r.branch)}</span>
              <span class="badge">${esc(r.head)}</span>
              ${treeBadge}${syncBadge}
            </div>
          </div>
        </div>
        <dl class="meta"><dt>remote</dt><dd>${esc(r.remote)}</dd></dl>
        <div class="commits">${commits}</div>
      </div>`;
  }).join("");
}
async function load(){
  try{
    const r=await fetch("/api/gogit",{cache:"no-store"});
    if(!r.ok)throw new Error("HTTP "+r.status);
    render(await r.json());
  }catch(e){
    document.getElementById("updated").textContent="error: "+e.message;
  }
}
load();
setInterval(load,30000);
</script>
</body>
</html>"""


@app.get("/goGit", response_class=HTMLResponse)
def goGit():
    return HTML_PAGE
