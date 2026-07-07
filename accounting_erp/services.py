from django.db import transaction
from django.core.exceptions import ValidationError
from accounting_erp.models import (
    FixedAssetRegister,
    JournalEntry,
    JournalLine,
    AccountPortal,
    FinancialYear,
)
from decimal import Decimal
import datetime


def depreciate_fixed_assets(financial_year, user=None):
    """Automatically depreciates school assets based on configured rates and generates journal lines."""
    assets = FixedAssetRegister.objects.filter(status="Active")
    posted_entries = 0

    # Retrieve or create depreciation expense account
    depr_expense, _ = AccountPortal.objects.get_or_create(
        code="5050",
        defaults={
            "name": "Depreciation Expense",
            "account_type": "EXPENSE",
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
        },
    )

    # Retrieve or create accumulated depreciation contra-asset account
    accum_depr, _ = AccountPortal.objects.get_or_create(
        code="1080",
        defaults={
            "name": "Accumulated Depreciation",
            "account_type": "ASSET",
            "opening_balance": Decimal("0.00"),
            "current_balance": Decimal("0.00"),
        },
    )

    with transaction.atomic():
        for asset in assets:
            if asset.depreciation_method == "NONE":
                continue

            rate = asset.depreciation_rate / Decimal("100.00")
            if asset.depreciation_method == "STRAIGHT_LINE":
                depr_amount = (asset.purchase_cost * rate).quantize(
                    Decimal("0.01")
                )
            elif asset.depreciation_method == "REDUCING_BALANCE":
                depr_amount = (asset.current_value * rate).quantize(
                    Decimal("0.01")
                )
            else:
                depr_amount = Decimal("0.00")

            if depr_amount <= Decimal("0.00"):
                continue

            # Cap depreciation at remaining value
            if depr_amount > asset.current_value:
                depr_amount = asset.current_value

            # Update asset value
            asset.current_value -= depr_amount
            asset.save()

            # Record Journal entry
            jv_num = f"JV-DEPR-{asset.asset_code}-{datetime.date.today().year}"
            entry = JournalEntry.objects.create(
                journal_number=jv_num,
                entry_date=datetime.date.today(),
                description=f"Auto-post depreciation for asset {asset.asset_name}",
                financial_year=financial_year,
                approval_status="DRAFT",
            )

            # Debit Expense
            JournalLine.objects.create(
                journal_entry=entry,
                account=depr_expense,
                debit_amount=depr_amount,
                credit_amount=Decimal("0.00"),
            )

            # Credit Accum Depreciation
            JournalLine.objects.create(
                journal_entry=entry,
                account=accum_depr,
                debit_amount=Decimal("0.00"),
                credit_amount=depr_amount,
            )

            # Approve Journal
            entry.approval_status = "APPROVED"
            entry.approved_by = user
            entry.save()

            # Update account balances
            depr_expense.current_balance += depr_amount
            depr_expense.save()

            accum_depr.current_balance -= depr_amount  # Contra asset reduces balance
            accum_depr.save()

            posted_entries += 1

    return posted_entries


def generate_trial_balance():
    """Generates a Trial Balance report checking ledger debit/credit status."""
    accounts = AccountPortal.objects.all()
    records = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for account in accounts:
        bal = account.current_balance
        debit = Decimal("0.00")
        credit = Decimal("0.00")

        # Determine balance placement by type
        if account.account_type in ["ASSET", "EXPENSE"]:
            if bal >= Decimal("0.00"):
                debit = bal
            else:
                credit = abs(bal)
        else:
            if bal >= Decimal("0.00"):
                credit = bal
            else:
                debit = abs(bal)

        total_debit += debit
        total_credit += credit

        records.append(
            {
                "code": account.code,
                "name": account.name,
                "type": account.account_type,
                "debit": debit,
                "credit": credit,
            }
        )

    return {
        "records": records,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": total_debit == total_credit,
    }


def generate_income_statement(financial_year):
    """Produces the Income Statement (Revenue vs Expenses)."""
    revenue_accounts = AccountPortal.objects.filter(account_type="REVENUE")
    expense_accounts = AccountPortal.objects.filter(account_type="EXPENSE")

    revenue_total = sum(acc.current_balance for acc in revenue_accounts)
    expense_total = sum(acc.current_balance for acc in expense_accounts)
    net_surplus = revenue_total - expense_total

    return {
        "revenue_items": [
            {"name": acc.name, "balance": acc.current_balance}
            for acc in revenue_accounts
        ],
        "expense_items": [
            {"name": acc.name, "balance": acc.current_balance}
            for acc in expense_accounts
        ],
        "total_revenue": revenue_total,
        "total_expenses": expense_total,
        "net_surplus": net_surplus,
    }
