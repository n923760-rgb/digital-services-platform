#!/bin/sh
set -eu

while :; do
    sh /backup-scripts/backup_once.sh
    sleep 86400
done
