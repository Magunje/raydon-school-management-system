from django.db import transaction
from django.core.exceptions import ValidationError
from accounting_erp.models import (
    FixedAssetRegister,
    JournalEntry,
    JournalLine,
    AccountPortal,
    FinancialYear,
    GeneralLedgerEntry,
    AccountingAuditLog,
    NumberSequence,
)
from decimal import Decimal
import datetime


def log_accounting_action(
    action,
    transaction_number=None,
    user=None,
    previous_value=None,
    new_value=None,
    reason=None,
):
    return AccountingAuditLog.objects.create(
        action=action,
        transaction_number=transaction_number,
        user=user,
        previous_value=previous_value,
        new_value=new_value,
        reason=reason,
    )


def next_sequence(name, prefix):
    sequence, _ = NumberSequence.objects.get_or_create(
        name=name, defaults={"prefix": prefix}
    )
    return sequence.next_number()


def post_journal_entry(journal_entry, user=None):
    """Posts an approved journal into the general ledger exactly once."""
    if journal_entry.approval_status not in ["APPROVED", "POSTED"]:
        raise ValidationError("Only approved journal entries can be posted.")
    if journal_entry.posted_at:
        return journal_entry

    lines = list(journal_entry.lines.select_related("account"))
    total_debits = sum(line.debit_amount for line in lines)
    total_credits = sum(line.credit_amount for line in lines)
    if total_debits != total_credits:
        raise ValidationError("Total debits must equal total credits before posting.")

    with transaction.atomic():
        for line in lines:
            GeneralLedgerEntry.objects.get_or_create(
                journal_line=line,
                defaults={
                    "transaction_date": journal_entry.entry_date,
                    "posting_date": datetime.date.today(),
                    "account": line.account,
                    "debit_amount": line.debit_amount,
                    "credit_amount": line.credit_amount,
                    "currency": line.currency,
                    "exchange_rate": line.exchange_rate,
                    "source_module": journal_entry.source_module,
                    "reference_number": journal_entry.reference_number
                    or journal_entry.journal_number,
                    "description": line.description or journal_entry.description,
                    "created_by": journal_entry.prepared_by,
                    "approved_by": journal_entry.approved_by or user,
                },
            )

            account = line.account
            if account.account_type in ["ASSET", "EXPENSE"]:
                account.current_balance += line.debit_amount - line.credit_amount
            else:
                account.current_balance += line.credit_amount - line.debit_amount
            account.save(update_fields=["current_balance"])

        journal_entry.approval_status = "POSTED"
        journal_entry.posted_at = datetime.datetime.now(datetime.timezone.utc)
        journal_entry.save(update_fields=["approval_status", "posted_at"])

        log_accounting_action(
            "Journal posting",
            transaction_number=journal_entry.journal_number,
            user=user or journal_entry.approved_by,
            new_value={
                "total_debits": str(total_debits),
                "total_credits": str(total_credits),
                "source_module": journal_entry.source_module,
            },
        )

    return journal_entry


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

            # Approve and post Journal
            entry.approval_status = "APPROVED"
            entry.approved_by = user
            entry.save()
            post_journal_entry(entry, user=user)

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


def generate_balance_sheet():
    assets = AccountPortal.objects.filter(account_type="ASSET")
    liabilities = AccountPortal.objects.filter(account_type="LIABILITY")
    equity = AccountPortal.objects.filter(account_type="EQUITY")
    return {
        "assets": [{"name": acc.name, "balance": acc.current_balance} for acc in assets],
        "liabilities": [
            {"name": acc.name, "balance": acc.current_balance}
            for acc in liabilities
        ],
        "equity": [{"name": acc.name, "balance": acc.current_balance} for acc in equity],
        "total_assets": sum(acc.current_balance for acc in assets),
        "total_liabilities": sum(acc.current_balance for acc in liabilities),
        "total_equity": sum(acc.current_balance for acc in equity),
    }


def generate_cash_flow_statement(financial_year):
    ledger_entries = GeneralLedgerEntry.objects.filter(
        transaction_date__gte=financial_year.start_date,
        transaction_date__lte=financial_year.end_date,
        account__account_type="ASSET",
    )
    cash_movements = []
    net_cash = Decimal("0.00")
    for entry in ledger_entries:
        movement = entry.debit_amount - entry.credit_amount
        cash_movements.append(
            {
                "date": entry.transaction_date,
                "account": entry.account.name,
                "reference": entry.reference_number,
                "movement": movement,
            }
        )
        net_cash += movement
    return {"cash_movements": cash_movements, "net_cash_movement": net_cash}
