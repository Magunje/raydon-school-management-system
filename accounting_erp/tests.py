from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from fees_management.models import StudentFeeAccount, FeeStructure
from fees_management.services import record_payment
from academic_structure.models import AcademicYear, Form, Stream, AcademicClass
from student_registry.models import Student
from accounting_erp.models import (
    FinancialYear,
    AccountPortal,
    JournalEntry,
    JournalLine,
    FixedAssetRegister,
)
from accounting_erp.services import (
    depreciate_fixed_assets,
    generate_trial_balance,
    generate_income_statement,
)
from decimal import Decimal
import datetime

User = get_user_model()


class AccountingErpTestCase(TestCase):
    def setUp(self):
        # Admin
        self.admin = User.objects.create_superuser(
            username="finance_auditor", password="password123"
        )

        # Financial Year
        self.fy = FinancialYear.objects.create(
            name="FY 2026",
            start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31),
            is_closed=False,
        )

        # Chart of accounts
        self.cash_acct = AccountPortal.objects.create(
            code="1010",
            name="Cash at Bank",
            account_type="ASSET",
            opening_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )
        self.revenue_acct = AccountPortal.objects.create(
            code="4010",
            name="Tuition Fees",
            account_type="REVENUE",
            opening_balance=Decimal("0.00"),
            current_balance=Decimal("0.00"),
        )

    def test_double_entry_validation(self):
        # 1. Balanced Journal entry (should succeed)
        entry = JournalEntry.objects.create(
            journal_number="JV-001",
            entry_date=datetime.date(2026, 2, 1),
            description="Test balance",
            financial_year=self.fy,
            approval_status="DRAFT",
        )

        JournalLine.objects.create(
            journal_entry=entry,
            account=self.cash_acct,
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("0.00"),
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=self.revenue_acct,
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("100.00"),
        )

        # Approve (must not raise ValidationError)
        entry.approval_status = "APPROVED"
        entry.save()
        self.assertEqual(entry.approval_status, "APPROVED")

        # 2. Unbalanced Journal entry (should raise ValidationError on approval)
        entry_unbalanced = JournalEntry.objects.create(
            journal_number="JV-002",
            entry_date=datetime.date(2026, 2, 1),
            description="Test unbalance",
            financial_year=self.fy,
            approval_status="DRAFT",
        )
        JournalLine.objects.create(
            journal_entry=entry_unbalanced,
            account=self.cash_acct,
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("0.00"),
        )
        JournalLine.objects.create(
            journal_entry=entry_unbalanced,
            account=self.revenue_acct,
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("50.00"),  # Unbalanced credit
        )

        entry_unbalanced.approval_status = "APPROVED"
        with self.assertRaises(ValidationError):
            entry_unbalanced.save()

    def test_locked_closed_financial_periods(self):
        self.fy.is_closed = True
        self.fy.save()

        # Try to post journal to closed FY -> should raise ValidationError
        entry = JournalEntry(
            journal_number="JV-003",
            entry_date=datetime.date(2026, 2, 1),
            description="Closed period post",
            financial_year=self.fy,
        )
        with self.assertRaises(ValidationError):
            entry.save()

    def test_automatic_fees_postings_to_gl(self):
        # Create student and trigger billing
        year = AcademicYear.objects.create(year=2026, is_active=True)
        term = year.terms.create(term_number=1, is_active=True)
        form = Form.objects.create(form_number=1, name="Form 1")
        stream = Stream.objects.create(name="A")
        aclass = AcademicClass.objects.create(
            academic_year=year, form=form, stream=stream
        )

        student = Student.objects.create(
            first_name="Rutendo",
            surname="Chipo",
            gender="Female",
            date_of_birth=datetime.date(2011, 4, 12),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=aclass,
            status="Active Student",
        )

        account = StudentFeeAccount.objects.get(student=student)

        # Clear initial values of accounts
        self.cash_acct.current_balance = Decimal("0.00")
        self.cash_acct.save()
        self.revenue_acct.current_balance = Decimal("0.00")
        self.revenue_acct.save()

        # Record payment (triggers auto post signal)
        record_payment(
            student_account=account,
            amount=Decimal("80.00"),
            currency="USD",
            payment_method="CASH",
            cashier=self.admin,
        )

        # Verify journal entry was generated and approved automatically
        jv_exists = JournalEntry.objects.filter(
            approval_status="APPROVED",
            description__icontains="Auto-post fee collection receipt",
        ).exists()
        self.assertTrue(jv_exists)

        # Verify Chart of Accounts balances updated automatically
        self.cash_acct.refresh_from_db()
        self.revenue_acct.refresh_from_db()
        self.assertEqual(self.cash_acct.current_balance, Decimal("80.00"))
        self.assertEqual(self.revenue_acct.current_balance, Decimal("80.00"))

    def test_fixed_asset_depreciation_and_reports(self):
        # Register fixed asset
        asset = FixedAssetRegister.objects.create(
            asset_code="AST-BUS-01",
            asset_name="School Bus",
            category="Vehicles",
            purchase_date=datetime.date(2026, 1, 1),
            purchase_cost=Decimal("12000.00"),
            depreciation_method="STRAIGHT_LINE",
            depreciation_rate=Decimal("10.00"),  # 10% annual depreciation
            current_value=Decimal("12000.00"),
            status="Active",
        )

        # Execute depreciation
        depreciate_fixed_assets(financial_year=self.fy, user=self.admin)

        # Asset value depreciated: 12000 * 10% = 1200
        asset.refresh_from_db()
        self.assertEqual(asset.current_value, Decimal("10800.00"))

        # Verify Trial Balance report balance
        tb = generate_trial_balance()
        self.assertTrue(tb["is_balanced"])

        # Verify Income statement report
        report = generate_income_statement(self.fy)
        self.assertEqual(report["total_expenses"], Decimal("1200.00"))  # Depreciation expense
