#!/usr/bin/env bash
# Nightly backup of the database.
#
#   sudo cp deploy/backup.sh /usr/local/bin/household-portal-backup
#   sudo chmod +x /usr/local/bin/household-portal-backup
#   sudo crontab -e
#     15 3 * * *  /usr/local/bin/household-portal-backup
#
# Uses SQLite's own backup command, so it is safe to run while the portal is
# in use - a plain `cp` of a live database can produce a corrupt copy.

set -euo pipefail

DB="${DB:-/opt/household-portal/instance/portal.db}"
DEST="${DEST:-/var/backups/household-portal}"
KEEP_DAYS="${KEEP_DAYS:-30}"

mkdir -p "$DEST"
STAMP=$(date +%Y-%m-%d)
OUT="$DEST/portal-$STAMP.db"

sqlite3 "$DB" ".backup '$OUT'"
gzip -f "$OUT"

find "$DEST" -name 'portal-*.db.gz' -mtime "+$KEEP_DAYS" -delete

echo "backed up to $OUT.gz"
