#!/bin/sh
set -eu

# This script deliberately writes to the source database and must only run in CI.
if [ "${CI_RESTORE_TEST:-}" != "1" ]; then
    echo "CI_RESTORE_TEST=1 is required for the disposable CI database" >&2
    exit 2
fi

restore_database="restore_smoke_$$"
created=0
cleanup() {
    if [ "$created" -eq 1 ]; then
        dropdb "$restore_database"
    fi
}
trap cleanup EXIT

psql -v ON_ERROR_STOP=1 -c "INSERT INTO users (id) VALUES ('00000000-0000-4000-8000-000000000001') ON CONFLICT DO NOTHING" > /dev/null
archive=$(sh /usr/local/bin/backup_once.sh)

createdb "$restore_database"
created=1
pg_restore --exit-on-error --no-owner --no-acl --dbname="$restore_database" "$archive"
rows=$(psql -v ON_ERROR_STOP=1 --dbname="$restore_database" -Atqc "SELECT count(*) FROM users WHERE id = '00000000-0000-4000-8000-000000000001'")
test "$rows" = 1
version=$(psql -v ON_ERROR_STOP=1 --dbname="$restore_database" -Atqc 'SELECT version_num FROM alembic_version')
test -n "$version"
echo "Restore smoke passed: seeded row and migration version $version found in isolated database"
