# RAYDON SCHOOL MANAGEMENT SYSTEM

RAYDON SCHOOL MANAGEMENT SYSTEM is now a Django-only school management system.

## Main Modules

- Public school website
- Staff/admin authentication
- Student portal
- Dashboard
- User accounts and roles
- Students and guardians
- Staff and teacher profiles
- Classes, subjects, timetables, and e-learning
- Student and staff attendance
- Examination setup, results, and reports
- Fees structure, payments, receipts, expenses, and financial reports
- Payroll profiles, monthly payroll processing, approvals, bank Excel export, payslips, and payroll reports
- Audit logs, settings, backups, and offline sync tracking

## Project Structure

- `manage.py`
- `school_project/`
- `accounts/`
- `students/`
- `parents/`
- `staff/`
- `teachers/`
- `academics/`
- `attendance/`
- `exams/`
- `examinations/`
- `fees/`
- `finance/`
- `payroll/`
- `portals/`
- `reports/`
- `settings_app/`
- `website/`
- `notifications/`
- `django_templates/`
- `static/`

## Setup

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Copy environment settings:

```powershell
Copy-Item .env.example .env
```

Configure a production PostgreSQL database in `.env`:

```text
DATABASE_URL=postgresql://USER:PASSWORD@localhost:5432/raydon_school
```

For local development with the existing SQLite data file:

```powershell
$env:SQLITE_NAME="school_system.db"
```

Apply migrations:

```powershell
python manage.py migrate
```

Run the server:

```powershell
python manage.py runserver 127.0.0.1:8005
```

Open:

```text
http://127.0.0.1:8005/
```

Staff login:

```text
http://127.0.0.1:8005/staff/login
```

Student portal:

```text
http://127.0.0.1:8005/student-portal/login
```

## Verification

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
python django_smoke_test.py
```

## Deployment

The production WSGI application is:

```text
school_project.wsgi:application
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection URL (e.g. `postgresql://user:pass@host:port/dbname`) | None (required if `SQLITE_NAME` not set) |
| `SQLITE_NAME` | SQLite database file name (for fallback/local dev) | None |
| `SECRET_KEY` | Django unique secret key | Local fallback key |
| `DEBUG` | Django debug flag | `True` |
| `ALLOWED_HOSTS` | Allowed HTTP Host headers | `127.0.0.1,localhost,.localhost,testserver` |

## License

This software is commercial proprietary and remains the private intellectual property of the author.

## Contact

For support, inquiries, or contributions:
* Email: [raidonmagunje@gmail.com](mailto:raidonmagunje@gmail.com)
