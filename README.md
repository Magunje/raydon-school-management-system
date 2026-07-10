# Raydon School Management System

[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11-blue.svg)](https://www.python.org/)
[![Django Framework](https://img.shields.io/badge/framework-django-green.svg)](https://www.djangoproject.com/)
[![Repository Visibility](https://img.shields.io/badge/repo-private-red.svg)](#)

An enterprise-grade, multi-tenant (SaaS) School Management System built using Python and Django. Designed for modern educational institutions to record, manage, monitor, and report academic, financial, administrative, and clinical activities across the student lifecycle.

---

## 🌟 Key Features

### 🏢 SaaS Multi-School Tenants
- Isolated multi-school data environments.
- Subscription billing, invoices, and plan management.

### 🧑‍🎓 Student & Guardian Registry
- Automated admission numbering.
- Comprehensive student lifecycle profiles, subjects, grades, and sibling mapping.
- Permanently archived academic history mapped by admission number.

### 📚 Academics & Timetabling
- Grade structures, class assignments, and course registration.
- Weekly scheduler grids for classes and teachers.
- Study note distribution and assignments portal.

### 📝 Results Centre & Assessments
- Score input, grades computation, and automatic rank reports.
- Comprehensive report card generation.

### 💳 Fees Structure & Finance ERP
- Integrated accounts receivable (A/R) ledger.
- Receipt tracking, cash book records, expense categories, and balance sheet reporting.

### 💼 Human Resources & Payroll
- Detailed employee profiles, ranks, and departments.
- Salary components definition, formula evaluation, payslip generation, and bank export schedules.

### 🛡️ Student Discipline & Behaviour
- Behavioral incident logs, counseling registries, behavior reports, and warning escalations.

### 🏥 Medical Clinic
- Health records, clinical visit logs, allergy registries, and prescription tracking.

---

## 🛠️ Technologies Used
- **Core Framework**: Python 3 (3.10+ recommended) & Django 5.x
- **Frontend Layer**: Vanilla CSS, Bootstrap 5, HTML5 & JavaScript (Vanilla JS)
- **Database Engine**: SQLite (Local development), PostgreSQL (Production/Staging ready)
- **Deployment & Containers**: Docker, Fly.io, and Gunicorn WSGI.

---

## 🚀 Getting Started

### 📋 Prerequisites
Ensure you have the following installed locally:
- Python 3.10 or higher
- Git

### 🔧 Installation

For detailed steps, refer to [INSTALLATION.md](file:///c:/Users/RAYDON/OneDrive/Imágenes/Desktop/SCHOOL SYSTEM/INSTALLATION.md).

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/raidonmagunje/raydon-school-management-system.git
   cd raydon-school-management-system
   ```

2. **Set up Virtual Environment**:
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Settings**:
   Copy the sample environment file to `.env`:
   ```bash
   copy .env.example .env
   ```

---

## 🗄️ Database Setup & Migrations

### Local SQLite Development
By default, the application runs on a local SQLite database named `school_system.db`.
To prepare migrations and run on the SQLite backend:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Production PostgreSQL Setup
Configure the `DATABASE_URL` in `.env` to target your production PostgreSQL database:
```env
DATABASE_URL=postgresql://db_user:db_password@localhost:5432/raydon_school_db
```
Then run the migration command to populate the database tables.

---

## ⚙️ Environment Variables

| Variable | Description | Default / Example |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection URL | `postgresql://user:pass@host:port/dbname` |
| `SQLITE_NAME` | SQLite database file (Local dev) | `school_system.db` |
| `SECRET_KEY` | Django unique cryptographic key | `django-insecure-...` |
| `DEBUG` | Enable debug logs & stack traces | `False` |
| `ALLOWED_HOSTS` | Allowed HTTP Host headers | `127.0.0.1,localhost,raydon-school.com` |

---

## 🖥️ Running the Application

1. **Start the Django Development Server**:
   ```bash
   python manage.py runserver 127.0.0.1:8006
   ```

2. **Default Portals Access URLs**:
   - **Public Website Landing**: [http://127.0.0.1:8006/](http://127.0.0.1:8006/)
   - **Staff & Admin Login**: [http://127.0.0.1:8006/staff/login](http://127.0.0.1:8006/staff/login)
   - **Student & Parent Portal**: [http://127.0.0.1:8006/student-portal/login](http://127.0.0.1:8006/student-portal/login)

3. **Default Admin User Creation**:
   To create a Superuser with access to Django Administration panel:
   ```bash
   python manage.py createsuperuser
   ```

---

## 📸 Screenshots
*(To include screenshots, place mock-up screens in a `media/screenshots/` folder and link them here)*

---

## 🔒 Security & Policy
This codebase is a private proprietary project. Ensure all environment secrets (`.env`) are kept out of commit logs. Do not expose passwords or private keys.

For detailed guidelines, refer to [DEPLOYMENT.md](file:///c:/Users/RAYDON/OneDrive/Imágenes/Desktop/SCHOOL SYSTEM/DEPLOYMENT.md).

---

## ✉️ Contact
- **Project Owner**: Raidon Magunje
- **Email**: [raidonmagunje@gmail.com](mailto:raidonmagunje@gmail.com)
- **GitHub**: [@raidonmagunje](https://github.com/raidonmagunje)
