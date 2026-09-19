# doGet

mCore local engine — backups, dashboard, health endpoints.

## Layout

- `scripts/mcore-full-backup.sh` — read-only system snapshot
- `engine/` — local HTTP service (FastAPI or stdlib)
- `dashboard/` — static dashboard HTML
- `backups/` — manifests only (tarballs gitignored)

## Backup


SSH keys are excluded by default. To include them, encrypted:


## Engine

See `engine/README.md` after running web-ready.sh.

## Host

WSL2 Ubuntu 26.04 · Node 24.21.0 · pnpm 12.4.0 · Python 3.14.4
