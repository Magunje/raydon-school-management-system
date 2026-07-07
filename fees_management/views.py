from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from fees_management.models import StudentFeeAccount
from student_registry.sync import sync_all_legacy_data


@login_required
def fee_account_list_view(request):
    sync_all_legacy_data()
    accounts = StudentFeeAccount.objects.all()
    rows = []
    for a in accounts:
        rows.append(
            {
                "data": [
                    a.student.admission_no,
                    f"{a.student.first_name} {a.student.surname}",
                    f"${a.total_charges:.2f}",
                    f"${a.amount_paid:.2f}",
                    f"${a.outstanding_balance:.2f}",
                    f"${a.arrears:.2f}",
                    f"${a.credit_balance:.2f}",
                ],
                "actions": [],
            }
        )
    return render(
        request,
        "erp_dashboard.html",
        {
            "title": "Fees Management & Billing",
            "subtitle": "Managed student billing structures, invoices, sponsorships, discounts, and outstanding balances.",
            "headers": [
                "Admission No",
                "Student Name",
                "Total Billed",
                "Total Paid",
                "Outstanding",
                "Arrears",
                "Credit Balance",
            ],
            "rows": rows,
            "has_actions": False,
        },
    )
