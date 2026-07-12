#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -Eeuo pipefail

echo "=== Starting Raydon SMS Enterprise Deployment ==="

if [ -f ".env" ]; then
    echo "Loading deployment environment from .env..."
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

# 1. Pull latest images and build containers
echo "Building and pulling latest docker containers..."
docker compose build --pull

# 2. Stop application containers from any previous release
echo "Stopping existing application containers..."
docker compose stop web nginx || true

# 3. Start PostgreSQL first so migrations run once before web starts
echo "Starting database container..."
docker compose up -d db

# 4. Wait for PostgreSQL to be healthy
echo "Waiting for database container to be healthy..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' raydon_db)" == "healthy" ]; do
    echo "Database status is: $(docker inspect -f '{{.State.Health.Status}}' raydon_db). Retrying in 2 seconds..."
    sleep 2
done

# 5. Run database migrations in a one-off web container
echo "Running database migrations..."
docker compose run --rm --no-deps web python manage.py migrate --fake-initial --noinput

# 6. Optionally import legacy SQLite tables into PostgreSQL
if [ -n "${SQLITE_IMPORT_PATH:-}" ]; then
    if [ -d "$SQLITE_IMPORT_PATH" ]; then
        echo "SQLITE_IMPORT_PATH points to a directory, not a SQLite database file: $SQLITE_IMPORT_PATH"
        echo "Copy the localhost .db file to this exact path, then run deploy again."
        exit 1
    fi
    if [ ! -f "$SQLITE_IMPORT_PATH" ]; then
        echo "SQLITE_IMPORT_PATH is set but the SQLite database file does not exist: $SQLITE_IMPORT_PATH"
        exit 1
    fi
    echo "Importing legacy SQLite tables from $SQLITE_IMPORT_PATH..."
    REQUIRED_TABLES="${SQLITE_IMPORT_REQUIRED_TABLES:-users,pupils,school_settings}"
    docker compose run --rm --no-deps \
        -v "$SQLITE_IMPORT_PATH:/tmp/legacy.sqlite:ro" \
        web python manage.py import_sqlite_legacy /tmp/legacy.sqlite --replace --require-tables "$REQUIRED_TABLES"
fi

# 7. Collect static assets in the shared static volume
echo "Collecting static assets..."
docker compose run --rm --no-deps web python manage.py collectstatic --noinput

# 8. Re-create and run application containers in background
echo "Starting application containers..."
docker compose up -d --force-recreate web nginx

# 9. Check container health status
echo "Checking web application containers status..."
docker compose ps

# 10. Check endpoints using Python stdlib
echo "Querying internal application health check..."
for attempt in $(seq 1 30); do
    if docker compose exec -T web python - <<'PY'
from urllib.request import urlopen

print(urlopen("http://localhost:8000/health/", timeout=10).read().decode())
PY
    then
        break
    fi
    echo "Health check attempt ${attempt}/30 failed. Retrying in 2 seconds..."
    sleep 2
    if [ "$attempt" = "30" ]; then
        echo "Health check failed after 30 attempts."
        exit 1
    fi
done

echo "=== Deployment Completed Successfully ==="
