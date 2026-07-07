from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal
import datetime


class FeeCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "fees_mgt_categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class FeeStructure(models.Model):
    LEVEL_CHOICES = [
        ("O_LEVEL", "Ordinary Level (Form 1-4)"),
        ("A_LEVEL", "Advanced Level (Form 5-6)"),
    ]

    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear",
        on_delete=models.CASCADE,
        related_name="fee_structures",
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm",
        on_delete=models.CASCADE,
        related_name="fee_structures",
    )
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_deadline = models.DateField()
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "fees_mgt_structures"
        unique_together = ("academic_year", "academic_term", "level")

    def __str__(self):
        return f"{self.get_level_display()} - Year {self.academic_year.year} Term {self.academic_term.term_number} (${self.amount})"


class StudentFeeAccount(models.Model):
    student = models.OneToOneField(
        "student_registry.Student",
        on_delete=models.CASCADE,
        related_name="fee_account",
    )
    academic_year = models.ForeignKey(
        "academic_structure.AcademicYear",
        on_delete=models.CASCADE,
        related_name="fee_accounts",
    )
    academic_term = models.ForeignKey(
        "academic_structure.AcademicTerm",
        on_delete=models.CASCADE,
        related_name="fee_accounts",
    )
    fee_structure = models.ForeignKey(
        FeeStructure,
        on_delete=models.PROTECT,
        related_name="fee_accounts",
        null=True,
        blank=True,
    )
    total_charges = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    amount_paid = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    outstanding_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    arrears = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    credit_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "fees_mgt_student_accounts"

    def __str__(self):
        return f"Fee Account for {self.student.admission_no} ({self.student.full_name})"

    def clean(self):
        super().clean()
        # Verify arrears and credit balance are non-negative
        if self.arrears < Decimal("0.00"):
            raise ValidationError("Arrears cannot be negative.")
        if self.credit_balance < Decimal("0.00"):
            raise ValidationError("Credit balance cannot be negative.")

    def save(self, *args, **kwargs):
        # Recalculate balances
        net_outstanding = self.total_charges - self.amount_paid + self.arrears
        if net_outstanding < Decimal("0.00"):
            self.outstanding_balance = Decimal("0.00")
            self.credit_balance = abs(net_outstanding)
        else:
            self.outstanding_balance = net_outstanding
            self.credit_balance = Decimal("0.00")

        self.full_clean()
        super().save(*args, **kwargs)


class FinanceSetting(models.Model):
    zig_exchange_rate = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("1.0000")
    )
    operating_currency = models.CharField(
        max_length=10,
        choices=[("USD", "USD"), ("ZIG", "ZiG")],
        default="USD",
    )

    class Meta:
        db_table = "fees_mgt_finance_settings"

    def __str__(self):
        return f"Finance Setting (Rate: 1 USD = {self.zig_exchange_rate} ZiG)"


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    student_account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.CASCADE, related_name="invoices"
    )
    invoice_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    previous_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    current_charges = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    discounts = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    scholarships = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    total_amount_due = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "fees_mgt_invoices"
        ordering = ["-invoice_number"]

    def __str__(self):
        return self.invoice_number

    def clean(self):
        super().clean()
        inv_date = self.invoice_date or datetime.date.today()
        if self.due_date and self.due_date < inv_date:
            pass  # Allow past billing dates for historic entries, but print warning in UI.

    def save(self, *args, **kwargs):
        # Calculate total due: Previous balance + current charges - discounts - scholarships
        self.total_amount_due = (
            self.previous_balance
            + self.current_charges
            - self.discounts
            - self.scholarships
        )
        self.full_clean()
        super().save(*args, **kwargs)


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="items"
    )
    category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "fees_mgt_invoice_items"

    def __str__(self):
        return f"{self.category.name} - ${self.amount}"


class Payment(models.Model):
    CURRENCY_CHOICES = [
        ("USD", "USD"),
        ("ZIG", "ZiG"),
    ]

    METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("POS", "POS"),
        ("MOBILE_MONEY", "Mobile Money"),
    ]

    receipt_number = models.CharField(max_length=50, unique=True)
    student_account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.CASCADE, related_name="payments"
    )
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(
        max_length=10, choices=CURRENCY_CHOICES, default="USD"
    )
    exchange_rate = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("1.0000")
    )
    amount_in_operating = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    payment_method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    transaction_reference = models.CharField(
        max_length=150, blank=True, null=True
    )
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_received",
    )
    is_reversed = models.BooleanField(default=False)

    class Meta:
        db_table = "fees_mgt_payments"
        ordering = ["-receipt_number"]

    def __str__(self):
        return self.receipt_number


class PaymentPlan(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("COMPLETED", "Completed"),
        ("DEFAULTED", "Defaulted"),
    ]

    student_account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.CASCADE, related_name="payment_plans"
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    instalment_amount = models.DecimalField(max_digits=12, decimal_places=2)
    number_of_instalments = models.IntegerField()
    start_date = models.DateField()
    due_dates_json = models.JSONField()  # Store list of dates in JSON
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="ACTIVE"
    )

    class Meta:
        db_table = "fees_mgt_payment_plans"

    def __str__(self):
        return f"Payment Plan for {self.student_account.student.admission_no} (${self.total_amount})"


class Sponsorship(models.Model):
    SPONSORSHIP_CHOICES = [
        ("FULL_SCHOLARSHIP", "Full Scholarship"),
        ("PARTIAL_SCHOLARSHIP", "Partial Scholarship"),
        ("GOVERNMENT", "Government Sponsorship"),
        ("NGO", "NGO Sponsorship"),
        ("CORPORATE", "Corporate Sponsorship"),
        ("PARENT", "Parent Sponsorship"),
    ]

    student_account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.CASCADE, related_name="sponsorships"
    )
    sponsor_name = models.CharField(max_length=150)
    sponsorship_type = models.CharField(
        max_length=40, choices=SPONSORSHIP_CHOICES
    )
    coverage_percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    coverage_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    start_date = models.DateField()
    end_date = models.DateField()
    conditions = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "fees_mgt_sponsorships"

    def __str__(self):
        return f"{self.sponsor_name} - {self.get_sponsorship_type_display()}"


class Discount(models.Model):
    DISCOUNT_CHOICES = [
        ("PERCENTAGE", "Percentage Discount"),
        ("FIXED_AMOUNT", "Fixed Amount Discount"),
        ("WAIVER", "Fee Waiver"),
    ]

    student_account = models.ForeignKey(
        StudentFeeAccount, on_delete=models.CASCADE, related_name="discounts"
    )
    discount_type = models.CharField(max_length=30, choices=DISCOUNT_CHOICES)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    percentage = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    reason = models.TextField()
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="fee_discounts_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fees_mgt_discounts"

    def __str__(self):
        return f"{self.discount_type} - {self.student_account.student.admission_no}"


class ReceiptControl(models.Model):
    receipt_prefix = models.CharField(max_length=10, default="REC")
    invoice_prefix = models.CharField(max_length=10, default="INV")
    last_receipt_no = models.IntegerField(default=0)
    last_invoice_no = models.IntegerField(default=0)

    class Meta:
        db_table = "fees_mgt_receipt_control"


class ReconciliationRecord(models.Model):
    STATUS_CHOICES = [
        ("RECONCILED", "Reconciled"),
        ("DISCREPANCY", "Discrepancy"),
    ]

    reconciliation_date = models.DateField()
    payment_method = models.CharField(max_length=50)
    system_total = models.DecimalField(max_digits=12, decimal_places=2)
    actual_total = models.DecimalField(max_digits=12, decimal_places=2)
    discrepancy = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="RECONCILED"
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliations_resolved",
    )
    resolution_notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "fees_mgt_reconciliations"
        unique_together = ("reconciliation_date", "payment_method")

    def __str__(self):
        return f"Reconciled {self.payment_method} on {self.reconciliation_date}"
