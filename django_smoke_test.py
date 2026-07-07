import os
os.environ['DATABASE_URL'] = ''
os.environ['SQLITE_NAME'] = r'scratch\fly_school_system.db'
os.environ['DEBUG'] = 'True'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "school_system_django.settings")

import django
from django.conf import settings
from django.test import Client


django.setup()


def check(client, path, label, expected=(200, 302)):
    response = client.get(path, secure=settings.SECURE_SSL_REDIRECT)
    if response.status_code not in expected:
        raise AssertionError(f"{label}: GET {path} returned {response.status_code}")
    print(f"OK {label}: {path}")


def main():
    public = Client()
    check(public, "/", "website", expected=(200,))
    check(public, "/staff/login", "staff login", expected=(200,))
    check(public, "/student-portal/login", "student login", expected=(200,))

    client = Client()
    response = client.post("/django/staff/login/", {"username": "admin", "password": "admin123"}, follow=True)
    if response.status_code != 200 or not any(url == "/dashboard" for url, _ in response.redirect_chain):
        raise AssertionError("admin login failed")

    paths = [
        ("/dashboard", "dashboard"),
        ("/users", "users"),
        ("/audit-trail", "audit trail"),
        ("/settings", "settings"),
        ("/classes", "classes"),
        ("/timetables/", "timetables"),
        ("/attendance", "attendance"),
        ("/attendance/monthly", "monthly attendance"),
        ("/pupils", "students"),
        ("/completed-students", "completed students"),
        ("/guardians", "parents"),
        ("/teachers", "teachers"),
        ("/teacher-attendance", "staff attendance"),
        ("/exams", "exams"),
        ("/notifications", "notifications"),
        ("/e-learning", "e-learning"),
        ("/library", "library"),
        ("/inventory", "inventory"),
        ("/uniform-pos", "uniform POS"),
        ("/payroll/", "payroll"),
        ("/backups", "backups"),
        ("/offline-sync", "offline sync"),
        ("/results", "results"),
        ("/performance-predictions", "performance predictions"),
        ("/fees-structure", "fees structure"),
        ("/reports", "reports"),
        ("/payments", "payments"),
        ("/payments/new", "record payment"),
        ("/portal-payment-requests", "portal payment requests"),
        ("/master-receipts", "master receipts"),
        ("/expenses", "expenses"),
        ("/expenses/new", "record expense"),
        ("/textbook-loans", "textbook loans"),
    ]
    for path, label in paths:
        expected_status = (200, 302) if path in {"/uniform-pos", "/payments/new", "/attendance/monthly", "/exams", "/performance-predictions"} else (200,)
        check(client, path, label, expected=expected_status)
    print("DJANGO SMOKE TEST COMPLETE")


if __name__ == "__main__":
    main()
