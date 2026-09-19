#!/usr/bin/env bash
# mCore full backup — read-only on source, no SSH keys by default
set -euo pipefail
BACKUP_ROOT="${1:-/srv/backups/mcore}"
STAMP=$(date +"%Y%m%d-%H%M%S")
SNAP_DIR="$BACKUP_ROOT/$STAMP"
TARBALL="$BACKUP_ROOT/mcore-full-${STAMP}.tar.zst"
MANIFEST="$BACKUP_ROOT/mcore-manifest-${STAMP}.json"
SUMS="$BACKUP_ROOT/SHA256SUMS-${STAMP}"
mkdir -p "$SNAP_DIR"
echo "Backup: $STAMP"

for t in tar zstd jq sha256sum; do
  command -v "$t" >/dev/null 2>&1 || { echo "missing: $t"; exit 1; }
done

# System metadata
{
  echo "ISO:     $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "Host:    $(hostname)"
  echo "Kernel:  $(uname -r)"
  echo "Distro:  $(grep PRETTY_NAME /etc/os-release | cut -d'"' -f2)"
  echo "Node:    $(node --version 2>/dev/null || echo n/a)"
  echo "pnpm:    $(pnpm --version 2>/dev/null || echo n/a)"
  echo "Python:  $(python3 --version 2>/dev/null || echo n/a)"
  echo ""
  echo "Disk:"
  df -hT / /srv 2>/dev/null
  echo ""
  echo "Git /srv/mcore:"
  git -C /srv/mcore rev-parse HEAD 2>/dev/null || echo "n/a"
  git -C /srv/mcore status -s 2>/dev/null | head -20 || true
} > "$SNAP_DIR/system-info.txt"

# Source tree — no node_modules, no .next, no SSH keys
if [ -d /srv/mcore ]; then
  rsync -aH \
    --exclude='node_modules' --exclude='.next' --exclude='.turbo' \
    --exclude='dist' --exclude='build' --exclude='.cache' \
    --exclude='.venv' --exclude='coverage' \
    /srv/mcore/ "$SNAP_DIR/srv-mcore/"
  echo "  srv-mcore/ done"
fi

# System configs
mkdir -p "$SNAP_DIR/system-configs"
for p in /etc/nginx /etc/cloudflared /etc/hosts /etc/hostname /etc/fstab; do
  [ -e "$p" ] && cp -a "$p" "$SNAP_DIR/system-configs/" 2>/dev/null || true
done

# SSH keys — OPT IN ONLY, encrypted
if [ "${BACKUP_SSH:-0}" = "1" ] && [ -n "${BACKUP_PASS:-}" ]; then
  if [ -d /root/.ssh ]; then
    tar -cf - -C /root .ssh | \
      gpg --symmetric --cipher-algo AES256 --batch \
          --passphrase "$BACKUP_PASS" \
          -o "$SNAP_DIR/root-ssh.tar.gpg"
    echo "  root-ssh.tar.gpg written (encrypted)"
  fi
else
  echo "  SSH keys skipped (set BACKUP_SSH=1 and BACKUP_PASS=... to include)"
fi

# Package list
dpkg --get-selections > "$SNAP_DIR/dpkg-selections.txt" 2>/dev/null || true
apt-mark showmanual > "$SNAP_DIR/apt-manual.txt" 2>/dev/null || true

# Manifest
jq -n \
  --arg iso "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg host "$(hostname)" \
  --arg kernel "$(uname -r)" \
  --arg git "$(git -C /srv/mcore rev-parse --short HEAD 2>/dev/null || echo n/a)" \
  '{iso:$iso,host:$host,kernel:$kernel,git:$git,sshIncluded:(env.BACKUP_SSH=="1")}' \
  > "$MANIFEST"

# Compress
tar --zstd -cf "$TARBALL" -C "$BACKUP_ROOT" "$STAMP"
( cd "$BACKUP_ROOT" && sha256sum "$(basename "$TARBALL")" "$(basename "$MANIFEST")" ) > "$SUMS"

# Retention: keep last 7 tarballs
cd "$BACKUP_ROOT"
ls -1t mcore-full-*.tar.zst 2>/dev/null | tail -n +8 | while read -r old; do
  echo "  removing old: $old"
  rm -f "$old"
done

echo "Tarball: $TARBALL"
echo "Manifest: $MANIFEST"
echo "SHA256: $SUMS"
