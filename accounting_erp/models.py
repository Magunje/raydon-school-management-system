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

    class Meta:
        db_table = "accounting_financial_years"

    def __str__(self):
        status = "Closed" if self.is_closed else "Open"
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
    opening_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    current_balance = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "accounting_chart_of_accounts"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.get_account_type_display()})"


class JournalEntry(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
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
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_journals",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "accounting_journal_entries"
        ordering = ["-entry_date", "-journal_number"]

    def __str__(self):
        return f"{self.journal_number} - {self.description[:40]}"

    def clean(self):
        super().clean()
        # Enforce that closed accounting periods are read-only
        if self.financial_year.is_closed:
            raise ValidationError(
                "Financial operations are locked for this closed financial period."
            )

        # Skip debit/credit balancing verification for Draft state
        if self.approval_status == "APPROVED":
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

    class Meta:
        db_table = "accounting_journal_lines"

    def __str__(self):
        return f"Line for {self.journal_entry.journal_number}: {self.account.name}"


class BankAccount(models.Model):
    bank_name = models.CharField(max_length=100)
    branch = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50, unique=True)
    currency = models.CharField(max_length=10, default="USD")
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
        ("DRAFT", "Draft"),
        ("APPROVED", "Approved"),
    ]

    bank_account = models.ForeignKey(BankAccount, on_delete=models.CASCADE)
    reconciliation_date = models.DateField()
    statement_balance = models.DecimalField(max_digits=12, decimal_places=2)
    system_balance = models.DecimalField(max_digits=12, decimal_places=2)
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


class SchoolBudget(models.Model):
    name = models.CharField(max_length=150)
    financial_year = models.ForeignKey(FinancialYear, on_delete=models.PROTECT)
    department = models.CharField(max_length=100)
    budget_amount = models.DecimalField(max_digits=12, decimal_places=2)
    actual_expenditure = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "accounting_budgets"

    def __str__(self):
        return f"{self.name} - {self.department} ({self.financial_year.name})"


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
