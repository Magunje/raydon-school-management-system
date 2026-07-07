from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from fees_management.models import Payment
from accounting_erp.models import (
    JournalEntry,
    JournalLine,
    AccountPortal,
    FinancialYear,
)
from decimal import Decimal
import datetime


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

    # Find open Financial Year
    pay_date = instance.payment_date
    fy = FinancialYear.objects.filter(
        start_date__lte=pay_date, end_date__gte=pay_date, is_closed=False
    ).first()
    if not fy:
        # Create a default Financial Year if not existing
        fy = FinancialYear.objects.create(
            name=f"FY {pay_date.year}",
            start_date=datetime.date(pay_date.year, 1, 1),
            end_date=datetime.date(pay_date.year, 12, 31),
            is_closed=False,
        )

    with transaction.atomic():
        # Generate Journal Entry
        jv_num = f"JV-PAY-{instance.receipt_number}"
        entry = JournalEntry.objects.create(
            journal_number=jv_num,
            entry_date=pay_date,
            description=f"Auto-post fee collection receipt {instance.receipt_number}",
            financial_year=fy,
            approval_status="DRAFT",
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

        # Approve and save journal to update balances
        entry.approval_status = "APPROVED"
        entry.save()

        # Update chart of accounts balances
        cash_acct.current_balance += instance.amount_in_operating
        cash_acct.save()

        revenue_acct.current_balance += instance.amount_in_operating
        revenue_acct.save()
