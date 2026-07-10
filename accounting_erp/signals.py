from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from fees_management.models import Invoice, Payment
from accounting_erp.models import (
    JournalEntry,
    JournalLine,
    AccountPortal,
    FinancialYear,
)
from accounting_erp.services import post_journal_entry
from decimal import Decimal
import datetime


def get_open_financial_year(txn_date):
    fy = FinancialYear.objects.filter(
        start_date__lte=txn_date,
        end_date__gte=txn_date,
        is_closed=False,
    ).exclude(status__in=["CLOSED", "LOCKED"]).first()
    if not fy:
        fy = FinancialYear.objects.create(
            name=f"FY {txn_date.year}",
            start_date=datetime.date(txn_date.year, 1, 1),
            end_date=datetime.date(txn_date.year, 12, 31),
            is_closed=False,
            status="OPEN",
        )
    return fy


@receiver(post_save, sender=Invoice)
def auto_post_fee_invoice_journal(sender, instance, created, **kwargs):
    """Posts fee invoices as Accounts Receivable against Fee Income."""
    if not created or instance.status == "VOID":
        return

    receivable_acct, _ = AccountPortal.objects.get_or_create(
        code="1100",
        defaults={
            "name": "Accounts Receivable",
            "account_type": "ASSET",
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
        },
    )
    revenue_acct, _ = AccountPortal.objects.get_or_create(
        code="4010",
        defaults={
            "name": "Tuition Fees",
            "account_type": "REVENUE",
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
        },
    )

    inv_date = instance.invoice_date or datetime.date.today()
    fy = get_open_financial_year(inv_date)

    with transaction.atomic():
        entry = JournalEntry.objects.create(
            journal_number=f"JV-INV-{instance.invoice_number}",
            entry_date=inv_date,
            description=f"Auto-post fee invoice {instance.invoice_number}",
            financial_year=fy,
            approval_status="DRAFT",
            source_module="Fees Management",
            reference_number=instance.invoice_number,
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=receivable_acct,
            debit_amount=instance.total_amount_due,
            credit_amount=Decimal("0.00"),
            description="Student fee invoice receivable",
        )
        JournalLine.objects.create(
            journal_entry=entry,
            account=revenue_acct,
            debit_amount=Decimal("0.00"),
            credit_amount=instance.total_amount_due,
            description="Student fee income",
        )
        entry.approval_status = "APPROVED"
        entry.save()
        post_journal_entry(entry)


@receiver(post_save, sender=Payment)
def auto_post_fee_payment_journal(sender, instance, created, **kwargs):
    """Automatically records balanced journal entries in the General Ledger upon

    student fee payments.
    """
    if not created or instance.is_reversed:
        return

    # Find or create corresponding accounts
    # Asset account: Cash at Bank
    cash_acct, _ = AccountPortal.objects.get_or_create(
        code="1010",
        defaults={
            "name": "Cash at Bank",
            "account_type": "ASSET",
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
        },
    )

    # Revenue account: Tuition Fees
    revenue_acct, _ = AccountPortal.objects.get_or_create(
        code="4010",
        defaults={
            "name": "Tuition Fees",
            "account_type": "REVENUE",
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
        },
    )

    pay_date = instance.payment_date
    fy = get_open_financial_year(pay_date)

    with transaction.atomic():
        # Generate Journal Entry
        jv_num = f"JV-PAY-{instance.receipt_number}"
        entry = JournalEntry.objects.create(
            journal_number=jv_num,
            entry_date=pay_date,
            description=f"Auto-post fee collection receipt {instance.receipt_number}",
            financial_year=fy,
            approval_status="DRAFT",
            source_module="Fees Management",
            reference_number=instance.receipt_number,
        )

        # Debit cash account
        JournalLine.objects.create(
            journal_entry=entry,
            account=cash_acct,
            debit_amount=instance.amount_in_operating,
            credit_amount=Decimal("0.00"),
            currency=instance.currency,
            exchange_rate=instance.exchange_rate,
        )

        # Credit revenue account
        JournalLine.objects.create(
            journal_entry=entry,
            account=revenue_acct,
            debit_amount=Decimal("0.00"),
            credit_amount=instance.amount_in_operating,
            currency=instance.currency,
            exchange_rate=instance.exchange_rate,
        )

        # Approve and post journal to update ledger and balances
        entry.approval_status = "APPROVED"
        entry.save()
        post_journal_entry(entry, user=instance.received_by)
