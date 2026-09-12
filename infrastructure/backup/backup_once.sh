#!/bin/sh
set -eu
umask 077

: "${BACKUP_DIR:?Set BACKUP_DIR}"
: "${BACKUP_RETENTION_DAYS:?Set BACKUP_RETENTION_DAYS}"
case "$BACKUP_RETENTION_DAYS" in
    *[!0-9]*|"") echo "BACKUP_RETENTION_DAYS must be a positive integer" >&2; exit 2 ;;
esac
if [ "$BACKUP_RETENTION_DAYS" -lt 1 ]; then
    echo "BACKUP_RETENTION_DAYS must be at least 1" >&2
    exit 2
fi

temporary=$(mktemp "${BACKUP_DIR}/.snapshot.XXXXXX")
trap 'rm -f "$temporary"' EXIT
trap 'exit 1' HUP INT TERM

pg_dump --format=custom --no-owner --no-acl --file="$temporary"
pg_restore --list "$temporary" > /dev/null
archive="${BACKUP_DIR}/platform-$(date -u +%Y%m%dT%H%M%SZ)-${temporary##*.}.dump"
mv "$temporary" "$archive"
trap - EXIT

if [ -n "${BACKUP_STATUS_DIR:-}" ]; then
    marker=$(mktemp "${BACKUP_STATUS_DIR}/.latest.XXXXXX")
    trap 'rm -f "$marker"' EXIT
    date -u +%Y-%m-%dT%H:%M:%SZ > "$marker"
    mv "$marker" "${BACKUP_STATUS_DIR}/latest"
    trap - EXIT
fi

find "$BACKUP_DIR" -maxdepth 1 -type f -name 'platform-*.dump' -mmin "+$((BACKUP_RETENTION_DAYS * 1440))" -exec rm -f {} \;
echo "$archive"
