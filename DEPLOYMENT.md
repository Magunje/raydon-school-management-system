# Production Deployment Guide

This document describes how to deploy the Raydon School Management System to production environments.

---

## 🔒 Production Security Checklist

Prior to moving to a live production environment, make sure to audit the following configurations:

1. **Secret Key**: Never expose the default `SECRET_KEY` in git. Generate a strong unique key in `.env`.
2. **Debug Mode**: Always set `DEBUG=False` in production to prevent stack traces from leaking data structure internals to end users.
3. **Allowed Hosts**: Define domain boundaries clearly in `ALLOWED_HOSTS`. Do not use wildcards (`*`).
4. **Database Credentials**: Set a secure PostgreSQL database server. Never use dev SQLite backend for persistent production multi-tenant setups.
5. **HTTPS (SSL)**: Secure connections using HTTPS by routing traffic through Nginx, Cloudflare, or setting up SSL let's encrypt certificates. Set `SECURE_SSL_REDIRECT=True` in settings.

---

## 📦 Deployment Environments

### 1. Fly.io Deployment
The application is pre-configured to build via Docker and deploy on Fly.io using `fly.toml`:

```bash
# Log in to Fly CLI
fly auth login

# Set production environment secrets
fly secrets set SECRET_KEY="your-random-production-key"
fly secrets set DEBUG="False"
fly secrets set DATABASE_URL="postgresql://user:pass@host:port/dbname"

# Deploy
fly deploy
```

### 2. Docker / Container Deployment
To build and test the production Docker container locally:

```bash
# Build the Docker image
docker build -t raydon-school-system:latest .

# Run container with environment configuration
docker run -d -p 8000:8000 --env-file .env raydon-school-system:latest
```

---

## 🗄️ Database Migrations in Production

Always run migrations on the live production database before starting the WSGI workers to ensure schema changes are safely updated:

```bash
python manage.py migrate --noinput
```

If static assets are modified, compile them:
```bash
python manage.py collectstatic --noinput
```

---

## ⚙️ WSGI Server Execution

In production, avoid running on Django's `runserver` development command. Instead, use a high-performance WSGI server such as **Gunicorn**:

```bash
gunicorn school_project.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
```

Recommended workers formula: `(2 * CPU cores) + 1`.
