from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase

from finance.views import validate_expense_affordability
from fees.models import Expense


class ExpenseAffordabilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username="finance-admin", password="admin123")
        self.client = Client()
        self.client.login(username="finance-admin", password="admin123")
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM school_settings")
            cursor.execute(
                """
                INSERT INTO school_settings (setting_id, school_name, current_term, current_year, receipt_prefix, cashbook_opening_balance)
                VALUES (1, 'Raydon Test School', 'Term 2', 2026, 'RCT', 0)
                """
            )
            cursor.execute("DELETE FROM pupils")
            cursor.execute(
                """
                INSERT INTO pupils (admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, guardian_name, guardian_phone, address, admission_date, status)
                VALUES ('A26001', 'Test', 'Student', 'Female', '2016-01-01', 'Grade 6', 'A', 'Parent', '0771', 'Street', '2026-01-01', 'Active')
                """
            )
            pupil_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO payments (pupil_id, receipt_no, amount_paid, payment_date, payment_method, term, year)
                VALUES (%s, 'RCT202600001', 500.0, '2026-06-22', 'Cash', 'Term 2', 2026)
                """,
                [pupil_id],
            )

    def test_expense_cannot_make_cashbook_negative(self):
        with self.assertRaisesMessage(ValueError, "Expense denied"):
            validate_expense_affordability("7000", "2026-06-22")

    def test_record_expense_rejects_amount_above_available_balance(self):
        response = self.client.post(
            "/expenses/new",
            {
                "expense_date": "2026-06-22",
                "amount": "7000",
                "category": "Repairs",
                "description": "Impossible large expense",
                "payment_method": "bank transfer",
                "reference_no": "12whw",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Expense.objects.filter(reference_no="12whw").exists())

    def test_record_expense_allows_affordable_amount(self):
        response = self.client.post(
            "/expenses/new",
            {
                "expense_date": "2026-06-22",
                "amount": "200",
                "category": "Repairs",
                "description": "Affordable repair",
                "payment_method": "Cash",
                "reference_no": "OK-001",
                "notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Expense.objects.filter(reference_no="OK-001", amount=200).exists())
