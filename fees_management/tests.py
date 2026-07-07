from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academic_structure.models import AcademicYear, Form, Stream, AcademicClass
from student_registry.models import Student
from fees_management.models import (
    StudentFeeAccount,
    FeeStructure,
    Invoice,
    Payment,
    PaymentPlan,
    Sponsorship,
    Discount,
    FinanceSetting,
    ReconciliationRecord,
)
from fees_management.services import (
    record_payment,
    apply_sponsorship,
    apply_discount,
    reconcile_payments,
)
from decimal import Decimal
import datetime

User = get_user_model()


class FeesManagementTestCase(TestCase):
    def setUp(self):
        # Create administrative users
        self.admin = User.objects.create_superuser(
            username="finance_admin", password="password123"
        )
        self.cashier = User.objects.create_user(
            username="cashier1", password="password123"
        )

        # Academic context
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.term_1 = self.year.terms.create(term_number=1, is_active=True)

        # Forms
        self.form_1 = Form.objects.create(form_number=1, name="Form 1")  # O Level
        self.form_5 = Form.objects.create(form_number=5, name="Form 5")  # A Level
        self.stream_a = Stream.objects.create(name="A")
        self.stream_sci = Stream.objects.create(name="Sciences")

        # Classes
        self.class_form1 = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_1, stream=self.stream_a
        )
        self.class_form5 = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_5, stream=self.stream_sci
        )

        # Setup base currency setting: 1 USD = 25.0000 ZiG
        self.finance_settings = FinanceSetting.objects.create(
            zig_exchange_rate=Decimal("25.0000"), operating_currency="USD"
        )

    def test_auto_billing_and_level_structure_assignment(self):
        # 1. Register student in Form 1 (O_LEVEL) -> should bill USD 100
        student_o = Student.objects.create(
            first_name="Tinashe",
            surname="Maposa",
            gender="Male",
            date_of_birth=datetime.date(2011, 4, 12),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form1,
            status="Active Student",
        )

        # Verify fee account was automatically created
        account_o = StudentFeeAccount.objects.get(student=student_o)
        self.assertEqual(account_o.fee_structure.level, "O_LEVEL")
        self.assertEqual(account_o.total_charges, Decimal("100.00"))
        self.assertEqual(account_o.outstanding_balance, Decimal("100.00"))

        # Verify invoice was automatically generated
        invoice_o = Invoice.objects.get(student_account=account_o)
        self.assertEqual(invoice_o.current_charges, Decimal("100.00"))
        self.assertEqual(invoice_o.total_amount_due, Decimal("100.00"))

        # 2. Register student in Form 5 (A_LEVEL) -> should bill USD 150
        student_a = Student.objects.create(
            first_name="Vimbai",
            surname="Chihuri",
            gender="Female",
            date_of_birth=datetime.date(2009, 8, 22),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form5,
            status="Active Student",
        )

        account_a = StudentFeeAccount.objects.get(student=student_a)
        self.assertEqual(account_a.fee_structure.level, "A_LEVEL")
        self.assertEqual(account_a.total_charges, Decimal("150.00"))
        self.assertEqual(account_a.outstanding_balance, Decimal("150.00"))

    def test_payment_processing_and_currency_conversion(self):
        student = Student.objects.create(
            first_name="Farai",
            surname="Dube",
            gender="Male",
            date_of_birth=datetime.date(2011, 5, 20),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form1,
            status="Active Student",
        )

        account = StudentFeeAccount.objects.get(student=student)

        # Record payment in ZIG (500.00 ZIG)
        # With exchange rate 25.0000, this conversion equals USD 20.00
        pay_date = datetime.date(2026, 2, 10)
        payment = record_payment(
            student_account=account,
            amount=Decimal("500.00"),
            currency="ZIG",
            payment_method="MOBILE_MONEY",
            transaction_reference="TXN-MOBILE-99",
            cashier=self.cashier,
            payment_date=pay_date,
        )

        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount_in_operating, Decimal("20.00"))

        # Check balance updates immediately
        account.refresh_from_db()
        self.assertEqual(account.amount_paid, Decimal("20.00"))
        self.assertEqual(account.outstanding_balance, Decimal("80.00"))

    def test_sponsorships_and_discounts(self):
        student = Student.objects.create(
            first_name="Nyarai",
            surname="Moyo",
            gender="Female",
            date_of_birth=datetime.date(2011, 10, 5),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form1,
            status="Active Student",
        )

        account = StudentFeeAccount.objects.get(student=student)

        # Apply a scholarship coverage of 50%
        apply_sponsorship(
            student_account=account,
            sponsor_name="NGO Trust Fund",
            sponsorship_type="NGO",
            coverage_percentage=Decimal("50.00"),
        )

        # Checks balance: total_charges = 100, 50% paid/covered -> outstanding = 50
        account.refresh_from_db()
        self.assertEqual(account.amount_paid, Decimal("50.00"))
        self.assertEqual(account.outstanding_balance, Decimal("50.00"))

        # Apply a Fixed Waiver discount of USD 10.00
        apply_discount(
            student_account=account,
            discount_type="WAIVER",
            approved_by=self.admin,
            amount=Decimal("10.00"),
            reason="Sports waiver",
        )

        account.refresh_from_db()
        self.assertEqual(account.amount_paid, Decimal("60.00"))
        self.assertEqual(account.outstanding_balance, Decimal("40.00"))

    def test_payment_reconciliation(self):
        student = Student.objects.create(
            first_name="Tatenda",
            surname="Hove",
            gender="Male",
            date_of_birth=datetime.date(2011, 7, 18),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form1,
            status="Active Student",
        )

        account = StudentFeeAccount.objects.get(student=student)

        # Record payment
        pay_date = datetime.date(2026, 3, 5)
        record_payment(
            student_account=account,
            amount=Decimal("30.00"),
            currency="USD",
            payment_method="CASH",
            transaction_reference="REF-CASH-7",
            cashier=self.cashier,
            payment_date=pay_date,
        )

        # Reconciliation: Cash collected = USD 30.00 (Match)
        recon_match = reconcile_payments(
            reconciliation_date=pay_date,
            payment_method="CASH",
            actual_total=Decimal("30.00"),
            resolved_by=self.admin,
        )
        self.assertEqual(recon_match.status, "RECONCILED")
        self.assertEqual(recon_match.discrepancy, Decimal("0.00"))

        # Reconciliation with discrepancy: Bank statement = USD 40.00 (Discrepancy)
        recon_disc = reconcile_payments(
            reconciliation_date=pay_date,
            payment_method="CASH",
            actual_total=Decimal("40.00"),
            resolved_by=self.admin,
        )
        self.assertEqual(recon_disc.status, "DISCREPANCY")
        self.assertEqual(recon_disc.discrepancy, Decimal("10.00"))
