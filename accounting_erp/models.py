from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings
from decimal import Decimal
import datetime


class FinancialYear(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_closed = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=[
            ("OPEN", "Open"),
            ("CLOSED", "Closed"),
            ("LOCKED", "Locked"),
            ("REOPENED", "Reopened"),
        ],
        default="OPEN",
    )

    class Meta:
        db_table = "accounting_financial_years"

    def __str__(self):
        status = self.get_status_display() if self.status else ("Closed" if self.is_closed else "Open")
        return f"{self.name} ({status})"

    def clean(self):
        super().clean()
        if self.start_date >= self.end_date:
            raise ValidationError("Start date must be strictly earlier than end date.")


class AccountPortal(models.Model):
    TYPE_CHOICES = [
        ("ASSET", "Asset"),
        ("LIABILITY", "Liability"),
        ("EQUITY", "Equity"),
        ("REVENUE", "Revenue"),
        ("EXPENSE", "Expense"),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    parent_account = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="child_accounts",
    )
    description = models.TextField(blank=True, null=True)
    currency = models.CharField(max_length=10, default="USD")
    is_active = models.BooleanField(default=True)
    opening_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    current_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounts_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounting_chart_of_accounts"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_account_type_display()})"


class JournalEntry(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("APPROVED", "Approved"),
        ("POSTED", "Posted"),
        ("REJECTED", "Rejected"),
        ("REVERSED", "Reversed"),
    ]

    journal_number = models.CharField(max_length=50, unique=True)
    entry_date = models.DateField()
    description = models.TextField()
    financial_year = models.ForeignKey(
        FinancialYear, on_delete=models.PROTECT, related_name="journals"
    )
    approval_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="DRAFT"
    )
    source_module = models.CharField(max_length=80, blank=True, null=True)
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    prepared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prepared_journals",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_journals",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_journals",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    reversed_entry = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reversal_entries",
    )
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounting_journal_entries"
        ordering = ["-entry_date", "-journal_number"]

    def __str__(self):
        return f"{self.journal_number} - {self.description[:40]}"

    def clean(self):
        super().clean()
        # Enforce that closed accounting periods are read-only
        if self.financial_year.is_closed or self.financial_year.status in ["CLOSED", "LOCKED"]:
            raise ValidationError(
                "Financial operations are locked for this closed financial period."
            )

        # Skip debit/credit balancing verification for Draft state
        if self.approval_status in ["APPROVED", "POSTED"]:
            # Debit must equal Credit
            lines = self.lines.all()
            total_debits = sum(line.debit_amount for line in lines)
            total_credits = sum(line.credit_amount for line in lines)
            if total_debits != total_credits:
                raise ValidationError(
                    f"Double-entry mismatch: Total debits (${total_debits}) "
                    f"must equal total credits (${total_credits})."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class JournalLine(models.Model):
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(AccountPortal, on_delete=models.PROTECT)
    debit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    credit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    currency = models.CharField(max_length=10, default="USD")
    exchange_rate = models.DecimalField(
        max_digits=12, decimal_places=4, default=Decimal("1.0000")
    )
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "accounting_journal_lines"

    def __str__(self):
        return f"Line for {self.journal_entry.journal_number}: {self.account.name}"


class GeneralLedgerEntry(models.Model):
    journal_line = models.OneToOneField(
        JournalLine, on_delete=models.CASCADE, related_name="ledger_entry"
    )
    transaction_date = models.DateField()
    posting_date = models.DateField()
    account = models.ForeignKey(AccountPortal, on_delete=models.PROTECT)
    debit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    currency = models.CharField(max_length=10, default="USD")
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=4, default=Decimal("1.0000"))
    source_module = models.CharField(max_length=80, blank=True, null=True)
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries_created",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounting_general_ledger"
        ordering = ["-posting_date", "-id"]


class BankAccount(models.Model):
    bank_name = models.CharField(max_length=100)
    branch = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50, unique=True)
    account_name = models.CharField(max_length=150, blank=True, null=True)
    currency = models.CharField(max_length=10, default="USD")
    ledger_account = models.ForeignKey(
        AccountPortal,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_accounts",
    )
    opening_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    current_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(
        max_length=20,
        choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")],
        default="ACTIVE",
    )

    class Meta:
        db_table = "accounting_bank_accounts"

    def __str__(self):
        return f"{self.bank_name} ({self.account_number})"


class BankReconciliation(models.Model):
    STATUS_CHOICES = [
        ("UNRECONCILED", "Unreconciled"),
        ("MATCHED", "Matched"),
        ("PARTIALLY_MATCHED", "Partially Matched"),
        ("DISPUTED", "Disputed"),
        ("RECONCILED", "Reconciled"),
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
    ]

    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    reconciliation_date = models.DateField()
    statement_balance = models.DecimalField(max_digits=12, decimal_places=2)
    system_balance = models.DecimalField(max_digits=12, decimal_places=2)
    difference = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="DRAFT"
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "accounting_bank_reconciliations"
        unique_together = ("bank_account", "reconciliation_date")

    def __str__(self):
        return f"Reconciliation for {self.bank_account} on {self.reconciliation_date}"

    def save(self, *args, **kwargs):
        self.difference = self.statement_balance - self.system_balance
        super().save(*args, **kwargs)


class BankStatementTransaction(models.Model):
    bank_account = models.ForeignKey(
        BankAccount, on_delete=models.CASCADE, related_name="statement_transactions"
    )
    transaction_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    deposit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    withdrawal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    matched_ledger_entry = models.ForeignKey(
        GeneralLedgerEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="matched_bank_statement_transactions",
    )
    match_status = models.CharField(
        max_length=30,
        choices=[
            ("UNRECONCILED", "Unreconciled"),
            ("MATCHED", "Matched"),
            ("PARTIALLY_MATCHED", "Partially Matched"),
            ("DISPUTED", "Disputed"),
        ],
        default="UNRECONCILED",
    )

    class Meta:
        db_table = "accounting_bank_statement_transactions"
        ordering = ["-transaction_date"]


class SchoolBudget(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("APPROVED", "Approved"),
        ("REVISED", "Revised"),
        ("CLOSED", "Closed"),
    ]

    name = models.CharField(max_length=150)
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    account = models.ForeignKey(
        AccountPortal, on_delete=models.SET_NULL, null=True, blank=True
    )
    accounting_period = models.CharField(max_length=80, blank=True, null=True)
    department = models.CharField(max_length=100)
    budget_amount = models.DecimalField(max_digits=12, decimal_places=2)
    actual_expenditure = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="DRAFT")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="budgets_approved",
    )
    revised_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounting_budgets"

    def __str__(self):
        return f"{self.name} - {self.department} ({self.financial_year.name})"

    @property
    def variance(self):
        return self.budget_amount - self.actual_expenditure


class AccountingPeriod(models.Model):
    financial_year = models.ForeignKey(
        FinancialYear, on_delete=models.CASCADE, related_name="periods"
    )
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=[
            ("OPEN", "Open"),
            ("CLOSED", "Closed"),
            ("LOCKED", "Locked"),
            ("REOPENED", "Reopened"),
        ],
        default="OPEN",
    )
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_periods_closed",
    )
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounting_periods"
        unique_together = ("financial_year", "name")

    def __str__(self):
        return f"{self.financial_year.name} - {self.name}"


class FixedAssetRegister(models.Model):
    DEPRECIATION_CHOICES = [
        ("STRAIGHT_LINE", "Straight Line"),
        ("REDUCING_BALANCE", "Reducing Balance"),
        ("NONE", "No Depreciation"),
    ]

    asset_code = models.CharField(max_length=50, unique=True)
    asset_name = models.CharField(max_length=150)
    category = models.CharField(max_length=100)
    purchase_date = models.DateField()
    purchase_cost = models.DecimalField(max_digits=12, decimal_places=2)
    depreciation_method = models.CharField(
        max_length=30, choices=DEPRECIATION_CHOICES, default="STRAIGHT_LINE"
    )
    depreciation_rate = models.DecimalField(
        max_digits=5, decimal_places=2
    )  # e.g., 10.00%
    current_value = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, default="Active")

    class Meta:
        db_table = "accounting_fixed_assets"

    def __str__(self):
        return f"{self.asset_code} - {self.asset_name}"


class ApprovalWorkflow(models.Model):
    target_type = models.CharField(max_length=80)
    target_id = models.PositiveIntegerField()
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_approval_requests",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="accounting_approvals",
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("REQUESTED", "Requested"),
            ("APPROVED", "Approved"),
            ("REJECTED", "Rejected"),
        ],
        default="REQUESTED",
    )
    comments = models.TextField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "accounting_approval_workflows"
        ordering = ["-created_at"]


class NumberSequence(models.Model):
    name = models.CharField(max_length=80, unique=True)
    prefix = models.CharField(max_length=20)
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "accounting_number_sequences"

    def next_number(self):
        self.last_number += 1
        self.save(update_fields=["last_number"])
        return f"{self.prefix}-{self.last_number:05d}"


class AccountingAuditLog(models.Model):
    module = models.CharField(max_length=80, default="Accounting")
    action = models.CharField(max_length=120)
    transaction_number = models.CharField(max_length=120, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device_identifier = models.CharField(max_length=120, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounting_audit_logs"
        ordering = ["-created_at"]


class OfflineAccountingQueue(models.Model):
    STATUS_CHOICES = [
        ("QUEUED", "Queued"),
        ("VALIDATED", "Validated"),
        ("POSTED", "Posted"),
        ("CONFLICT", "Conflict"),
        ("FAILED", "Failed"),
    ]

    operation = models.CharField(max_length=80)
    payload = models.JSONField()
    device_identifier = models.CharField(max_length=120, blank=True, null=True)
    local_timestamp = models.DateTimeField()
    server_timestamp = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="QUEUED")
    validation_errors = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "accounting_offline_queue"
        ordering = ["server_timestamp"]
