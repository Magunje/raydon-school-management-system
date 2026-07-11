#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -Eeuo pipefail

echo "=== Starting Raydon SMS Enterprise Deployment ==="

# 1. Pull latest images and build containers
echo "Building and pulling latest docker containers..."
docker compose build --pull

# 2. Start PostgreSQL first so migrations run once before web starts
echo "Starting database container..."
docker compose up -d db

# 3. Wait for PostgreSQL to be healthy
echo "Waiting for database container to be healthy..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' raydon_db)" == "healthy" ]; do
    echo "Database status is: $(docker inspect -f '{{.State.Health.Status}}' raydon_db). Retrying in 2 seconds..."
    sleep 2
done

# 4. Run database migrations in a one-off web container
echo "Running database migrations..."
docker compose run --rm --no-deps web python manage.py migrate --fake-initial --noinput

# 5. Collect static assets in the shared static volume
echo "Collecting static assets..."
docker compose run --rm --no-deps web python manage.py collectstatic --noinput

# 6. Re-create and run application containers in background
echo "Starting application containers..."
docker compose up -d --force-recreate web nginx

# 7. Check container health status
echo "Checking web application containers status..."
docker compose ps

# 8. Check endpoints using Python stdlib
echo "Querying internal application health check..."
docker compose exec -T web python - <<'PY'
from urllib.request import urlopen

print(urlopen("http://localhost:8000/health/", timeout=10).read().decode())
PY

echo "=== Deployment Completed Successfully ==="
