#!/bin/sh
set -eu

while :; do
    sh /usr/local/bin/backup_once.sh
    sleep 86400
done
