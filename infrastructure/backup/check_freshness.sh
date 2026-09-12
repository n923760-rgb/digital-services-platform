#!/bin/sh
set -eu
: "${BACKUP_STATUS_DIR:?Set BACKUP_STATUS_DIR}"
marker="${BACKUP_STATUS_DIR}/latest"
test -s "$marker"
now=$(date +%s)
modified=$(stat -c %Y "$marker")
age=$((now - modified))
test "$age" -ge 0 && test "$age" -lt 93600
