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
    LOAN_CREATED = "loan_created", "Loan created"
    LOAN_DEDUCTED = "loan_deducted", "Loan deducted"
    PAYROLL_POSTED = "payroll_posted", "Payroll posted"
    BANK_FILE_GENERATED = "bank_file_generated", "Bank file generated"


def money_field(default=MONEY_DEFAULT):
    return models.DecimalField(max_digits=12, decimal_places=2, default=default)


class EmployeePayrollProfile(models.Model):
    hr_employee = models.OneToOneField(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="payroll_profile",
    )
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    full_name = models.CharField(max_length=180)
    employee_number = models.CharField(max_length=50, unique=True)
    job_title = models.CharField(max_length=120)
    department = models.CharField(max_length=120, default="School")
    basic_salary = money_field()
    account_number = models.CharField(max_length=80, blank=True)
    bank_name = models.CharField(max_length=120, blank=True)
    branch_name = models.CharField(max_length=120, blank=True)
    account_name = models.CharField(max_length=180, blank=True)
    mobile_money_number = models.CharField(max_length=50, blank=True)
    salary_grade = models.CharField(max_length=80, blank=True)
    tax_status = models.CharField(max_length=80, default="Taxable")
    pension_scheme = models.CharField(max_length=120, blank=True)
    medical_aid_scheme = models.CharField(max_length=120, blank=True)
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
    FREQUENCY_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("WEEKLY", "Weekly"),
        ("FORTNIGHT", "Fortnight"),
    ]

    month = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(12)])
    year = models.PositiveIntegerField(validators=[MinValueValidator(2000)])
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="MONTHLY")
    approval_status = models.CharField(max_length=30, default="Pending")
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
    account_name = models.CharField(max_length=180, blank=True)
    mobile_money_number = models.CharField(max_length=50, blank=True)

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
    medical_aid = money_field()
    union_subscription = money_field()
    insurance = money_field()
    savings_scheme = money_field()
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
        deductions = (
            self.tax
            + self.nssa
            + self.pension
            + self.loan
            + self.advance
            + self.unpaid_leave
            + self.medical_aid
            + self.union_subscription
            + self.insurance
            + self.savings_scheme
            + self.other_deductions
        )

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
    qr_code_payload = models.TextField(blank=True)
    electronic_stamp = models.CharField(max_length=120, default="Electronic School Stamp")
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    generated_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self):
        return self.slip_number


class SalaryStructure(models.Model):
    name = models.CharField(max_length=120, unique=True)
    basic_salary = money_field()
    housing_allowance = money_field()
    transport_allowance = money_field()
    responsibility_allowance = money_field()
    other_allowances = money_field()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PayrollComponentDefinition(models.Model):
    COMPONENT_CHOICES = [
        ("ALLOWANCE", "Allowance"),
        ("DEDUCTION", "Deduction"),
        ("STATUTORY", "Statutory Deduction"),
    ]

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=120)
    component_type = models.CharField(max_length=20, choices=COMPONENT_CHOICES)
    taxable = models.BooleanField(default=True)
    fixed_amount = money_field()
    percentage_rate = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.0000"))
    formula = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["component_type", "code"]


class PayrollFormula(models.Model):
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    expression = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]


class OvertimeRecord(models.Model):
    OVERTIME_CHOICES = [
        ("HOURLY", "Hourly Overtime"),
        ("DAILY", "Daily Overtime"),
        ("WEEKEND", "Weekend Overtime"),
        ("PUBLIC_HOLIDAY", "Public Holiday Overtime"),
    ]

    employee_profile = models.ForeignKey(EmployeePayrollProfile, on_delete=models.PROTECT, related_name="overtime_records")
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="overtime_records")
    overtime_type = models.CharField(max_length=30, choices=OVERTIME_CHOICES)
    hours = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))
    hourly_rate = money_field()
    amount = money_field()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ["period", "employee_profile"]

    def save(self, *args, **kwargs):
        self.amount = (self.hours * self.hourly_rate).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class StaffLoan(models.Model):
    LOAN_CHOICES = [
        ("STAFF_LOAN", "Staff Loan"),
        ("SALARY_ADVANCE", "Salary Advance"),
        ("EMERGENCY_LOAN", "Emergency Loan"),
    ]

    loan_number = models.CharField(max_length=50, unique=True)
    employee_profile = models.ForeignKey(EmployeePayrollProfile, on_delete=models.PROTECT, related_name="loans")
    loan_type = models.CharField(max_length=30, choices=LOAN_CHOICES)
    loan_amount = money_field()
    interest_rate = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal("0.0000"))
    repayment_period = models.PositiveIntegerField()
    monthly_deduction = money_field()
    outstanding_balance = money_field()
    status = models.CharField(max_length=30, default="ACTIVE")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class PayrollAccountingPosting(models.Model):
    period = models.OneToOneField(PayrollPeriod, on_delete=models.CASCADE, related_name="accounting_posting")
    journal_number = models.CharField(max_length=80, unique=True)
    posted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    posted_at = models.DateTimeField(auto_now_add=True)
    total_gross = money_field()
    total_deductions = money_field()
    total_net = money_field()

    class Meta:
        ordering = ["-posted_at"]


class BankTransferFile(models.Model):
    period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name="bank_transfer_files")
    file_name = models.CharField(max_length=180)
    file_format = models.CharField(max_length=30, default="Excel")
    total_records = models.PositiveIntegerField(default=0)
    total_amount = money_field()
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]


class BankTransferLine(models.Model):
    bank_file = models.ForeignKey(BankTransferFile, on_delete=models.CASCADE, related_name="lines")
    employee_name = models.CharField(max_length=180)
    employee_number = models.CharField(max_length=50)
    bank_name = models.CharField(max_length=120, blank=True)
    account_number = models.CharField(max_length=80, blank=True)
    amount = money_field()


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
