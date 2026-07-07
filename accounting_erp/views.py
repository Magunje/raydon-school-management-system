from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from accounting_erp.models import (
    AccountPortal,
    BankAccount,
    SchoolBudget,
    FixedAssetRegister,
    BankReconciliation,
    FinancialYear,
)
from accounting_erp.services import (
    depreciate_fixed_assets,
    generate_trial_balance,
    generate_income_statement,
)
from decimal import Decimal


@login_required
def chart_of_accounts_view(request):
    # Handle depreciation trigger
    if request.method == "POST" and request.POST.get("action") == "depreciate":
        fy = FinancialYear.objects.filter(is_closed=False).first()
        if fy:
            count = depreciate_fixed_assets(fy, request.user)
            messages.success(
                request,
                f"Successfully depreciated {count} fixed assets and posted journal lines.",
            )
        else:
            messages.error(
                request, "No open financial year available to run depreciation."
            )
        return redirect("accounting_reports")

    # Handle financial reports queries
    report_type = request.GET.get("report")
    if report_type == "trial_balance":
        tb = generate_trial_balance()
        return render(request, "accounting_trial_balance.html", {"tb": tb})
    elif report_type == "income_statement":
        fy = FinancialYear.objects.filter(is_closed=False).first()
        statement = generate_income_statement(fy)
        return render(
            request,
            "accounting_income_statement.html",
            {"statement": statement, "fy": fy},
        )
    elif report_type == "balance_sheet":
        assets = AccountPortal.objects.filter(account_type="ASSET")
        liabilities = AccountPortal.objects.filter(account_type="LIABILITY")
        equity = AccountPortal.objects.filter(account_type="EQUITY")
        total_assets = sum(a.current_balance for a in assets)
        total_liab = sum(l.current_balance for l in liabilities)
        total_eq = sum(e.current_balance for e in equity)
        return render(
            request,
            "accounting_balance_sheet.html",
            {
                "assets": assets,
                "liabilities": liabilities,
                "equity": equity,
                "total_assets": total_assets,
                "total_liabilities": total_liab,
                "total_equity": total_eq,
            },
        )

    # Default: render general ledger dashboard
    from student_registry.sync import sync_all_legacy_data
    sync_all_legacy_data()

    accounts = AccountPortal.objects.all()
    bank_accounts = BankAccount.objects.all()
    budgets = SchoolBudget.objects.all()
    assets = FixedAssetRegister.objects.all()
    reconciliations = BankReconciliation.objects.all()

    return render(
        request,
        "accounting_dashboard.html",
        {
            "accounts": accounts,
            "bank_accounts": bank_accounts,
            "budgets": budgets,
            "assets": assets,
            "reconciliations": reconciliations,
        },
    )
