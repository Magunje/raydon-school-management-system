from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


MONEY_DEFAULT = Decimal("0.00")


class PayrollStatus(models.TextChoices):
    DRAFT = "Draft", "Draft"
    REVIEWED = "Reviewed", "Reviewed"
    APPROVED = "Approved", "Approved"
    PAID = "Paid", "Paid"


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = "Bank transfer", "Bank transfer"
    CASH = "Cash", "Cash"
    CHEQUE = "Cheque", "Cheque"
    ECOCASH = "EcoCash", "EcoCash"


class EmploymentStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    ON_LEAVE = "On leave", "On leave"
    SUSPENDED = "Suspended", "Suspended"
    TERMINATED = "Terminated", "Terminated"


class PayrollItemType(models.TextChoices):
    EARNING = "Earning", "Earning"
    DEDUCTION = "Deduction", "Deduction"


class PayrollAuditAction(models.TextChoices):
    PROFILE_CREATED = "profile_created", "Profile created"
    PROFILE_UPDATED = "profile_updated", "Profile updated"
    PERIOD_PROCESSED = "period_processed", "Period processed"
    RUN_UPDATED = "run_updated", "Run updated"
    STATUS_CHANGED = "status_changed", "Status changed"
    EXPORTED = "exported", "Exported"
    PAYSLIP_GENERATED = "payslip_generated", "Payslip generated"


def money_field(default=MONEY_DEFAULT):
    return models.DecimalField(max_digits=12, decimal_places=2, default=default)


class EmployeePayrollProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    full_name = models.CharField(max_length=180)
    employee_number = models.CharField(max_length=50, unique=True)
    job_title = models.CharField(max_length=120)
    department = models.CharField(max_length=120, default="School")
    basic_salary = money_field()
    account_number = models.CharField(max_length=80, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    branch_name = models.CharField(max_length=120, blank=True)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    employment_status = models.CharField(max_length=30, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        permissions = [
            ("can_process_payroll", "Can process payroll"),
            ("can_approve_payroll", "Can approve payroll"),
            ("can_export_payroll", "Can export payroll"),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.employee_number})"


class PayrollPeriod(models.Model):
    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.PositiveIntegerField(validators=[MinValueValidator(2000)])
    status = models.CharField(max_length=20, choices=PayrollStatus.choices, default=PayrollStatus.DRAFT)
    locked = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="created_payroll_periods")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="reviewed_payroll_periods")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="approved_payroll_periods")
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="paid_payroll_periods")
    reviewed_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month"]
        unique_together = [("year", "month")]

    @property
    def period_code(self):
        return f"{self.year:04d}-{self.month:02d}"

    @property
    def label(self):
        return self.period_code

    def __str__(self):
        return self.period_code


class PayrollRun(models.Model):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="runs")
    employee_profile = models.ForeignKey(EmployeePayrollProfile, on_delete=models.PROTECT, related_name="payroll_runs")
    copied_from = models.ForeignKey("self", on_delete=models.SET_NULL, blank=True, null=True, related_name="copied_runs")

    employee_name = models.CharField(max_length=180)
    employee_number = models.CharField(max_length=50)
    job_title = models.CharField(max_length=120)
    department = models.CharField(max_length=120)
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices)
    account_number = models.CharField(max_length=80, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    branch_name = models.CharField(max_length=120, blank=True)

    basic_salary = money_field()
    housing_allowance = money_field()
    transport_allowance = money_field()
    bonus = money_field()
    overtime = money_field()
    other_allowance = money_field()

    tax = money_field()
    nssa = money_field()
    pension = money_field()
    loan = money_field()
    advance = money_field()
    unpaid_leave = money_field()
    other_deductions = money_field()

    gross_salary = money_field()
    total_deductions = money_field()
    net_salary = money_field()
    status = models.CharField(max_length=20, choices=PayrollStatus.choices, default=PayrollStatus.DRAFT)
    locked = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="created_payroll_runs")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name="updated_payroll_runs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["employee_name"]
        unique_together = [("period", "employee_profile")]
        indexes = [
            models.Index(fields=["period", "department"]),
            models.Index(fields=["employee_number"]),
        ]

    def calculate_totals(self, include_adjustments=False):
        earnings = (
            self.basic_salary
            + self.housing_allowance
            + self.transport_allowance
            + self.bonus
            + self.overtime
            + self.other_allowance
        )
        deductions = self.tax + self.nssa + self.pension + self.loan + self.advance + self.unpaid_leave + self.other_deductions

        if include_adjustments and self.pk:
            adjustment_totals = self.adjustments.values("adjustment_type").annotate(total=models.Sum("amount"))
            for row in adjustment_totals:
                if row["adjustment_type"] == PayrollItemType.EARNING:
                    earnings += row["total"] or MONEY_DEFAULT
                elif row["adjustment_type"] == PayrollItemType.DEDUCTION:
                    deductions += row["total"] or MONEY_DEFAULT

        self.gross_salary = earnings
        self.total_deductions = deductions
        self.net_salary = earnings - deductions

    def save(self, *args, **kwargs):
        self.calculate_totals(include_adjustments=bool(self.pk))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee_name} - {self.period.period_code}"


class PayrollAdjustment(models.Model):
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="adjustments")
    adjustment_type = models.CharField(max_length=20, choices=PayrollItemType.choices)
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=180)
    amount = money_field()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["adjustment_type", "code", "id"]

    def __str__(self):
        return f"{self.run} {self.description}: {self.amount}"


class PayrollItem(models.Model):
    run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE, related_name="items")
    item_type = models.CharField(max_length=20, choices=PayrollItemType.choices)
    code = models.CharField(max_length=50)
    label = models.CharField(max_length=180)
    amount = money_field()
    source = models.CharField(max_length=40, default="run")
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["item_type", "sort_order", "label"]

    def __str__(self):
        return f"{self.label}: {self.amount}"


class PayrollApproval(models.Model):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="approvals")
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    action = models.CharField(max_length=40)
    notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.period} {self.from_status} -> {self.to_status}"


class PayrollExportLog(models.Model):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="export_logs")
    file_name = models.CharField(max_length=180)
    total_records = models.PositiveIntegerField(default=0)
    total_net = money_field()
    exported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file_name} ({self.total_records})"


class Payslip(models.Model):
    run = models.OneToOneField(PayrollRun, on_delete=models.CASCADE, related_name="payslip")
    slip_number = models.CharField(max_length=80, unique=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    generated_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return self.slip_number


class PayrollAuditLog(models.Model):
    action = models.CharField(max_length=60, choices=PayrollAuditAction.choices)
    period = models.ForeignKey(PayrollPeriod, on_delete=models.SET_NULL, blank=True, null=True)
    run = models.ForeignKey(PayrollRun, on_delete=models.SET_NULL, blank=True, null=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} at {self.created_at:%Y-%m-%d %H:%M}"

# Create your models here.
