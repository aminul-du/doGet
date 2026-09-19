# doGet

mCore local engine — backups, dashboard, health endpoints.

## Layout

| Path | Purpose |
|------|---------|
| scripts/mcore-full-backup.sh | Read-only system snapshot |
| engine/server.py             | Local HTTP status server |
| dashboard/                   | Static dashboard HTML |
| backups/                     | Manifest JSON (tarballs gitignored) |
| python/.venv/                | Python virtual environment (gitignored) |
| src/                         | Python source |
| tests/                       | Tests |

## Backup

    sudo bash scripts/mcore-full-backup.sh /srv/backups/mcore

SSH keys excluded by default. Encrypted opt-in:

    sudo BACKUP_SSH=1 BACKUP_PASS="your-passphrase" \\
        bash scripts/mcore-full-backup.sh

## Engine

    systemctl --user status mcore-local-engine
    curl http://127.0.0.1:8787/health

## Host

WSL2 Ubuntu 26.04 · Node 24.21.0 · pnpm 12.4.0 · Python 3.14.4
