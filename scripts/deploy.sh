#!/bin/bash
set -e

echo "🚀 Deploying AI Code Review System..."

# Build and push Docker images
docker-compose build
docker-compose push

# Run database migrations
docker-compose run --rm backend python manage.py migrate

# Collect static files
docker-compose run --rm backend python manage.py collectstatic --noinput

# Restart services
docker-compose up -d

echo "✅ Deployment complete!"
