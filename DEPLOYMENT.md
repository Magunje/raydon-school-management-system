# Production Deployment & Infrastructure Guide

This guide details how to configure, deploy, and maintain the **Raydon School Management System Enterprise Edition** on a live Virtual Private Server (VPS) such as Contabo, DigitalOcean, AWS, or Azure.

---

## 🏗️ Technical Architecture
The system is built on a containerized Three-Tier Architecture:
1. **Presentation Layer**: Client web browser proxying through Nginx (port `80`/`443`).
2. **Application Layer**: Gunicorn WSGI workers driving the Django 5+ application (port `8000`).
3. **Data Layer**: Isolated multi-tenant PostgreSQL 16 database (port `5432`) and shared volumes.

---

## 📦 Container Services & Configuration
The orchestration relies on **Docker Compose**. The service layout consists of:
- **`db` (PostgreSQL 16)**: Houses school schemas and active tenant tables.
- **`web` (Gunicorn/Django)**: Runs business logic, schedules, and calculations.
- **`nginx` (Reverse Proxy)**: Compiles static files, routes endpoints, and forces host/SSL headers.

### 1. Nginx Routing
Nginx is configured to serve static assets and proxy all requests to Gunicorn. It dynamically forwards subdomain hosts (`raydonhigh.localhost`, `schoolname.raydonsystem.com`) to allow multi-tenant schema isolation in the database middleware.

### 2. PostgreSQL Connection Pooling
To optimize queries and conserve memory on the server, `CONN_MAX_AGE` is set to `600` seconds inside Django's [settings.py](file:///c:/Users/RAYDON/OneDrive/Imágenes/Desktop/SCHOOL%20SYSTEM/school_system_django/settings.py).

### 3. Production SQLite Ban
To preserve data integrity, the system strictly forbids SQLite in production. If `DEBUG=False` or `ENV=production`, the application checks for a `DATABASE_URL` and will raise an `ImproperlyConfigured` exception if it is missing, preventing accidental local database usage.

### 4. Legacy SQLite Data Import
Older Raydon SMS installations used unmanaged legacy tables in `school_system.db`.
Production now runs on PostgreSQL, so copy that SQLite file to the VPS and run:

```bash
SQLITE_IMPORT_PATH=/var/www/raydon-school-management-system/school_system.db ./deploy.sh
```

When `SQLITE_IMPORT_PATH` is set, `deploy.sh` imports only unmanaged legacy tables
from SQLite into PostgreSQL using `import_sqlite_legacy --replace`. Normal Django
migrations still own the managed PostgreSQL tables.

---

## ⚙️ Environment Configuration (`.env`)
Create a `.env` file in the project root directory. Here is a production configuration example:

```env
# Application Settings
SECRET_KEY="your-strong-production-random-key"
DEBUG=False
ENV=production
ALLOWED_HOSTS="localhost,127.0.0.1,.raydonsystem.com"

# PostgreSQL Configuration
DB_NAME=raydon_school
DB_USER=raydon_admin
DB_PASSWORD=SecurePasswordHere123

# Network Port
PORT=8000
```

---

## 🚀 Live VPS Setup & Deployment

### Step 1: Clone the Codebase
SSH into your VPS server and clone the updated repository:
```bash
git clone https://github.com/your-username/raydon-school-system.git /var/www/raydon-school-system
cd /var/www/raydon-school-system
```

### Step 2: Configure Permissions
Grant execution permissions to the automated deployment script:
```bash
chmod +x deploy.sh
```

### Step 3: Run the Automated Deploy Script
Execute the deployment workflow:
```bash
./deploy.sh
```
This script will automatically:
1. Pull standard Docker base images and compile container files.
2. Spin up containers in the background (`detached` mode).
3. Wait until the PostgreSQL database container health check reports `healthy`.
4. Execute Django database schema migrations.
5. Collect static assets for Nginx into a shared folder.
6. Verify and output internal application health statuses.

---

## 📈 Monitoring & Health Checks
- **Health Endpoint**: The application exposes a public, database-aware endpoint at `/health/` and `/django/health/`.
- **Verify status manually**:
  ```bash
  curl -i http://localhost/health/
  ```
  Returns `200 OK` and `{"status": "healthy", "database": "connected"}` if the system is fully operational.
