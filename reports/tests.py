from decimal import Decimal

from django.db import connection
from django.test import TestCase

from reports.views import add_cashbook_running_balances, cashbook_reconciliation_rows


class BankReconciliationReportTests(TestCase):
    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM school_settings")
            cursor.execute(
                """
                INSERT INTO school_settings (setting_id, school_name, current_term, current_year, receipt_prefix, cashbook_opening_balance)
                VALUES (1, 'Raydon Test School', 'Term 2', 2026, 'RCT', 50.0)
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
                INSERT INTO payments (pupil_id, receipt_no, amount_paid, payment_date, payment_method, term, year, reference_no)
                VALUES (%s, 'RCT202600123', 100.0, '2026-06-20', 'Cash', 'Term 2', 2026, NULL)
                """,
                [pupil_id],
            )
            cursor.execute(
                """
                INSERT INTO payments (pupil_id, receipt_no, amount_paid, payment_date, payment_method, term, year, reference_no)
                VALUES (%s, 'RCT202600124', 70.0, '2026-06-20', 'Cash', 'Term 2', 2026, NULL)
                """,
                [pupil_id],
            )
            cursor.execute(
                """
                INSERT INTO expenses (expense_date, amount, category, description, payment_method, reference_no, created_at)
                VALUES ('2026-06-21', 30.0, 'Stationery', 'Books', 'Cash', 'EXP-001', '2026-06-21 10:00:00')
                """
            )

    def test_fee_collection_uses_receipt_number_as_reference(self):
        rows = cashbook_reconciliation_rows("2026-06-20", "2026-06-21")
        fee_row = next(row for row in rows if row["source"] == "Fee Collection")
        self.assertEqual(fee_row["reference_no"], "RCT202600123")

    def test_running_balance_is_added_to_cashbook_rows(self):
        rows = cashbook_reconciliation_rows("2026-06-20", "2026-06-21")
        add_cashbook_running_balances(rows, Decimal("50.00"))

        fee_row = next(row for row in rows if row["source"] == "Fee Collection")
        expense_row = next(row for row in rows if row["source"] == "Expense Payment")

        self.assertEqual(fee_row["balance"], Decimal("150.00"))
        self.assertEqual(expense_row["balance"], Decimal("190.00"))

    def test_cashbook_rows_are_chronological_so_visible_balances_progress(self):
        rows = cashbook_reconciliation_rows("2026-06-20", "2026-06-21")
        add_cashbook_running_balances(rows, Decimal("50.00"))

        balances = [row["balance"] for row in rows]

        self.assertEqual([row["reference_no"] for row in rows], ["RCT202600123", "RCT202600124", "EXP-001"])
        self.assertEqual(balances, [Decimal("150.00"), Decimal("220.00"), Decimal("190.00")])
