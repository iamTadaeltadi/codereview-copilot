# Docker Deployment Guide

## Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

## Quick Start
```bash
# Clone repository
git clone <repo-url>
cd ai-code-review-system

# Copy environment file
cp .env.example .env

# Start services
docker-compose up -d

# Run migrations
docker-compose exec backend python manage.py migrate

# Create superuser
docker-compose exec backend python manage.py createsuperuser
```

## Production Deployment
See production.md for production-specific configuration.
