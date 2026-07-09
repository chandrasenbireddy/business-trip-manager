#!/bin/sh
set -eu

: "${POSTGRES_HOST:=postgres}"
: "${POSTGRES_PORT:=5432}"
: "${POSTGRES_DB:=btm}"
: "${POSTGRES_USER:=postgres}"
: "${POSTGRES_PASSWORD:=postgres}"
: "${BTM_APP_DB_PASSWORD:?BTM_APP_DB_PASSWORD must be set — it becomes the btm_app role's password in 0003_app_role.sql}"

export PGPASSWORD="$POSTGRES_PASSWORD"
PSQL="psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -v ON_ERROR_STOP=1"

echo "Waiting for Postgres at $POSTGRES_HOST:$POSTGRES_PORT..."
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
    sleep 1
done
echo "Postgres is ready."

# db/migrations/*.sql aren't idempotent on their own (plain CREATE
# TABLE/ROLE/POLICY, no IF NOT EXISTS) — this table records what's already
# applied so re-running this entrypoint (container restart, `docker compose
# up` again against the same postgres volume) doesn't fail the second time
# on "relation/role already exists".
$PSQL -c "CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());"

for f in $(ls /app/db/migrations/*.sql | sort); do
    name=$(basename "$f")
    already=$($PSQL -tAc "SELECT 1 FROM schema_migrations WHERE filename = '$name'")
    if [ "$already" = "1" ]; then
        echo "skipping $name (already applied)"
        continue
    fi

    echo "applying $name"
    if [ "$name" = "0003_app_role.sql" ]; then
        # 0003 creates the btm_app role via `CREATE ROLE btm_app LOGIN
        # PASSWORD :'btm_app_password'` — psql -v substitutes and quotes it
        # as a SQL string literal, never a hardcoded password (see that
        # file's own comment, and README.md's "Local development" section).
        $PSQL -v btm_app_password="$BTM_APP_DB_PASSWORD" -f "$f"
    else
        $PSQL -f "$f"
    fi
    $PSQL -c "INSERT INTO schema_migrations (filename) VALUES ('$name');"
done

echo "Starting uvicorn..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
