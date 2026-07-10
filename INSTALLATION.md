# Installation and Development Setup Guide

Follow this guide to install and configure the Raydon School Management System locally.

---

## 💻 System Prerequisites

Make sure your machine has the following tools installed:
- **Python 3.10+** (Verify via `python --version`)
- **Pip** (Python package installer)
- **Git**

---

## 🛠️ Step-by-Step Installation

### 1. Clone the Source Repository
Download the project using Git:
```bash
git clone https://github.com/raidonmagunje/raydon-school-management-system.git
cd raydon-school-management-system
```

### 2. Configure Virtual Environment
It is highly recommended to isolate Python dependencies within a virtual environment.

**On Windows (Command Prompt / PowerShell)**:
```powershell
python -m venv .venv
.venv\Scripts\activate
```

**On macOS / Linux**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python Dependencies
Install all required modules declared in `requirements.txt`:
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Setup Environment Variables File
Create your local environment settings by copying the template file:
```bash
copy .env.example .env
```
*(On macOS/Linux, run `cp .env.example .env`)*

Modify `.env` to configure project details such as `SECRET_KEY`, `DEBUG`, and database parameters.

---

## 🗄️ Database Integration

The system supports running on SQLite locally and migrating to PostgreSQL in staging and production.

### local Dev (SQLite)
To use local SQLite database file `school_system.db`, add this to your `.env`:
```env
SQLITE_NAME=school_system.db
```
Then run the Django database setup commands:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Staging/Production (PostgreSQL)
Install the PostgreSQL database driver if needed (`psycopg2-binary`) and define the postgres connection URL:
```env
DATABASE_URL=postgresql://db_user:db_password@localhost:5432/raydon_school_db
```
Apply migrations using Django commands.

---

## 👤 Creating the Admin Superuser

Access to the administrator backend requires a Django superuser. Create it by executing:
```bash
python manage.py createsuperuser
```
Follow the interactive CLI prompts to enter a username, email address, and a secure password.

---

## 🧪 Verification & Smoke Testing

To ensure the local configuration is fully operational, run:
```bash
# 1. Run standard Django validation checks
python manage.py check

# 2. Run Django unit test suite
python manage.py test

# 3. Run integrated smoke tests
python django_smoke_test.py
```
If all tests pass, the environment is successfully installed!

---

## 🚀 Running the Web Application

Start the local Django server:
```bash
python manage.py runserver 127.0.0.1:8006
```
Open a browser and navigate to:
- Public Home: `http://127.0.0.1:8006/`
- Admin Console: `http://127.0.0.1:8006/admin/`
