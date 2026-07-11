#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Starting Raydon SMS Enterprise Deployment ==="

# 1. Pull latest images and build containers
echo "Building and pulling latest docker containers..."
docker compose build --pull

# 2. Re-create and run containers in background
echo "Starting containers in detached mode..."
docker compose up -d

# 3. Wait for PostgreSQL to be healthy
echo "Waiting for database container to be healthy..."
until [ "$(docker inspect -f '{{.State.Health.Status}}' raydon_db)" == "healthy" ]; do
    echo "Database status is: $(docker inspect -f '{{.State.Health.Status}}' raydon_db). Retrying in 2 seconds..."
    sleep 2
done

# 4. Run database migrations inside the web container
echo "Running database migrations..."
docker compose exec -T web python manage.py migrate --fake-initial --noinput

# 5. Collect static assets
echo "Collecting static assets..."
docker compose exec -T web python manage.py collectstatic --noinput

# 6. Check container health status
echo "Checking web application containers status..."
docker compose ps

# 7. Check endpoints using curl (Health Check)
echo "Querying internal application health check..."
docker compose exec -T web curl -s http://localhost:8000/health/

echo "=== Deployment Completed Successfully ==="
