from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from .forms import PayrollAdjustmentForm
from .models import EmployeePayrollProfile, PayrollAdjustment, PayrollItemType, PayrollRun
from .services import build_bank_export, process_period, refresh_run_totals, transition_period, update_run_adjustments


class PayrollWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="admin", password="pass")
        self.profile = EmployeePayrollProfile.objects.create(
            full_name="Jane Teacher",
            employee_number="EMP001",
            job_title="Teacher",
            department="Academics",
            basic_salary=Decimal("500.00"),
            account_number="123456789",
            bank_name="School Bank",
            branch_name="Main",
        )

    def test_process_period_loads_active_employees_and_calculates_net(self):
        period, created_count = process_period(year=2026, month=6, user=self.user)
        run = PayrollRun.objects.get(period=period, employee_profile=self.profile)

        self.assertEqual(created_count, 1)
        self.assertEqual(run.basic_salary, Decimal("500.00"))
        self.assertEqual(run.gross_salary, Decimal("500.00"))
        self.assertEqual(run.total_deductions, Decimal("0.00"))
        self.assertEqual(run.net_salary, Decimal("500.00"))

    def test_adjustments_update_gross_deductions_and_net_salary(self):
        period, _ = process_period(year=2026, month=6, user=self.user)
        run = PayrollRun.objects.get(period=period)
        run.housing_allowance = Decimal("50.00")
        run.tax = Decimal("20.00")
        refresh_run_totals(run)

        run.refresh_from_db()
        self.assertEqual(run.gross_salary, Decimal("550.00"))
        self.assertEqual(run.total_deductions, Decimal("20.00"))
        self.assertEqual(run.net_salary, Decimal("530.00"))

    def test_copy_previous_month_carries_adjustments_without_overwriting_profile_salary(self):
        june, _ = process_period(year=2026, month=6, user=self.user)
        june_run = PayrollRun.objects.get(period=june)
        june_run.housing_allowance = Decimal("70.00")
        refresh_run_totals(june_run)
        PayrollAdjustment.objects.create(
            run=june_run,
            adjustment_type=PayrollItemType.EARNING,
            code="BONUS",
            description="Performance bonus",
            amount=Decimal("30.00"),
            created_by=self.user,
        )
        refresh_run_totals(june_run)

        self.profile.basic_salary = Decimal("600.00")
        self.profile.save()
        july, _ = process_period(year=2026, month=7, user=self.user, copy_previous=True)
        july_run = PayrollRun.objects.get(period=july)

        self.assertEqual(july_run.basic_salary, Decimal("600.00"))
        self.assertEqual(july_run.housing_allowance, Decimal("70.00"))
        self.assertEqual(july_run.adjustments.count(), 1)
        self.assertEqual(july_run.net_salary, Decimal("700.00"))

    def test_approved_period_locks_runs_and_blocks_changes(self):
        period, _ = process_period(year=2026, month=6, user=self.user)
        transition_period(period, "review", user=self.user)
        transition_period(period, "approve", user=self.user)
        run = PayrollRun.objects.get(period=period)

        self.assertTrue(PayrollRun.objects.get(pk=run.pk).locked)
        with self.assertRaises(ValidationError):
            update_run_adjustments(run, user=self.user)

    def test_bank_export_requires_approved_payroll(self):
        period, _ = process_period(year=2026, month=6, user=self.user)
        with self.assertRaises(ValidationError):
            build_bank_export(period, user=self.user)

        transition_period(period, "review", user=self.user)
        transition_period(period, "approve", user=self.user)
        file_name, buffer = build_bank_export(period, user=self.user)

        self.assertEqual(file_name, "bank-payroll-2026-06.xlsx")
        self.assertGreater(len(buffer.getvalue()), 100)

# Create your tests here.
