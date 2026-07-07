import csv
from io import BytesIO, StringIO
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render

from accounts.permissions import permission_required
from fees.services import pupil_by_admission, statement_payment_rows, student_balance_rows, student_financial_summary
from school_system_django.native import academic_grade_option, dict_rows, export_rows, insert_record, legacy_user_id, now_text, one_row, render_rows_page, render_table_page, school_settings, simple_pdf, table_exists, today_text


REPORTS = {
    "payments": {
        "title": "Payment Reports",
        "table": "payments",
        "columns": ["receipt_no", "amount_paid", "payment_date", "payment_method", "term", "year"],
        "subtitle": "Financial payment report.",
        "order_by": "payment_date DESC",
    },
    "expenses": {
        "title": "Expense Reports",
        "table": "expenses",
        "columns": ["expense_date", "amount", "category", "description", "payment_method"],
        "subtitle": "Expense report.",
        "order_by": "expense_date DESC",
    },
    "results": {
        "title": "Academic Reports",
        "table": "result_sheets",
        "columns": ["pupil_id", "term", "year", "status", "average_mark", "class_position", "grade_position"],
        "subtitle": "Academic result report.",
        "order_by": "year DESC",
    },
    "pupils": {
        "title": "Student Reports",
        "table": "pupils",
        "columns": ["admission_no", "first_name", "surname", "grade", "class_stream", "status"],
        "subtitle": "Learner report.",
        "order_by": "surname, first_name",
    },
}


def normalized_header(value):
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def first_value(row, names, default=""):
    for name in names:
        value = row.get(name)
        if value not in {None, ""}:
            return value
    return default


def parse_decimal(value):
    text = str(value or "").strip().replace(",", "").replace("$", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        return Decimal(text or "0").quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def parse_statement_row(raw):
    row = {normalized_header(key): value for key, value in raw.items()}
    amount = parse_decimal(first_value(row, ["amount", "transaction_amount"]))
    debit = parse_decimal(first_value(row, ["debit", "withdrawal", "money_out", "paid_out"]))
    credit = parse_decimal(first_value(row, ["credit", "deposit", "money_in", "paid_in"]))
    if amount < 0 and not debit:
        debit = abs(amount)
    elif amount > 0 and not credit:
        credit = amount
    return {
        "transaction_date": first_value(row, ["transaction_date", "date", "posting_date", "value_date"]),
        "description": first_value(row, ["description", "details", "narration", "narrative", "particulars"]),
        "reference_no": first_value(row, ["reference_no", "reference", "ref", "bank_reference", "bank_reference_no"]),
        "money_in": credit,
        "money_out": debit,
    }


def import_bank_statement(request, uploaded_file):
    if not uploaded_file:
        return 0
    text = uploaded_file.read().decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(StringIO(text))
    imported = 0
    for raw in reader:
        row = parse_statement_row(raw)
        if not row["transaction_date"] or (row["money_in"] <= 0 and row["money_out"] <= 0):
            continue
        duplicate = one_row(
            """
            SELECT entry_id
            FROM bank_statement_entries
            WHERE transaction_date = %s
              AND COALESCE(reference_no, '') = COALESCE(%s, '')
              AND COALESCE(money_in, 0) = %s
              AND COALESCE(money_out, 0) = %s
            """,
            [row["transaction_date"], row["reference_no"], row["money_in"], row["money_out"]],
        )
        if duplicate:
            continue
        insert_record(
            request,
            "bank_statement_entries",
            {
                **row,
                "match_status": "Unmatched",
                "matched_source": "",
                "matched_id": None,
                "imported_at": now_text(),
                "imported_by": legacy_user_id(request),
            },
        )
        imported += 1
    return imported


def cashbook_reconciliation_rows(start="", end=""):
    clauses = []
    expense_clauses = []
    payment_params = []
    expense_params = []
    if start:
        clauses.append("payment_date >= %s")
        expense_clauses.append("expense_date >= %s")
        payment_params.append(start)
        expense_params.append(start)
    if end:
        clauses.append("payment_date <= %s")
        expense_clauses.append("expense_date <= %s")
        payment_params.append(end)
        expense_params.append(end)
    payment_where = "WHERE " + " AND ".join(clauses) if clauses else ""
    expense_where = "WHERE " + " AND ".join(expense_clauses) if expense_clauses else ""
    collections = dict_rows(
        f"""
        SELECT payment_id AS source_id, payment_date AS entry_date, 'Fee Collection' AS source, 'payments' AS source_table,
               payment_method AS method, receipt_no, receipt_no AS reference_no, amount_paid AS debit, 0 AS credit
        FROM payments
        {payment_where}
        """,
        payment_params,
    )
    pos_sales = []
    if table_exists("pos_sales"):
        pos_sales = dict_rows(
            f"""
            SELECT sale_id AS source_id, sale_date AS entry_date, 'POS Collection' AS source, 'pos_sales' AS source_table,
                   payment_method AS method, receipt_no, receipt_no AS reference_no, total_amount AS debit, 0 AS credit
            FROM pos_sales
            {payment_where.replace('payment_date', 'sale_date')}
            """,
            payment_params,
        )
    expenses = dict_rows(
        f"""
        SELECT expense_id AS source_id, expense_date AS entry_date, 'Expense Payment' AS source, 'expenses' AS source_table,
               payment_method AS method, '' AS receipt_no, reference_no, 0 AS debit, amount AS credit
        FROM expenses
        {expense_where}
        """,
        expense_params,
    )
    return sorted(collections + pos_sales + expenses, key=cashbook_ledger_sort_key)


def cashbook_ledger_sort_key(row):
    source_order = {
        "payments": 1,
        "pos_sales": 2,
        "expenses": 3,
    }
    return (
        str(row.get("entry_date") or ""),
        source_order.get(str(row.get("source_table") or ""), 99),
        int(row.get("source_id") or 0),
    )


def add_cashbook_running_balances(rows, opening_balance):
    running_balance = parse_decimal(opening_balance)
    for row in sorted(rows, key=cashbook_ledger_sort_key):
        running_balance += parse_decimal(row.get("debit")) - parse_decimal(row.get("credit"))
        row["balance"] = running_balance
    return rows


def auto_match_bank_statement(rows):
    if not table_exists("bank_statement_entries"):
        return {}
    bank_rows = dict_rows("SELECT * FROM bank_statement_entries WHERE COALESCE(match_status, '') != 'Cleared'")
    matched = {}
    used_bank_ids = set()
    for cashbook in rows:
        reference = str(cashbook.get("reference_no") or "").strip()
        if not reference:
            continue
        cash_in = parse_decimal(cashbook.get("debit"))
        cash_out = parse_decimal(cashbook.get("credit"))
        for bank in bank_rows:
            if bank["entry_id"] in used_bank_ids:
                continue
            if str(bank.get("reference_no") or "").strip().upper() != reference.upper():
                continue
            if parse_decimal(bank.get("money_in")) != cash_in or parse_decimal(bank.get("money_out")) != cash_out:
                continue
            matched[(cashbook["source_table"], cashbook["source_id"])] = bank
            used_bank_ids.add(bank["entry_id"])
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE bank_statement_entries
                    SET match_status = 'Cleared', matched_source = %s, matched_id = %s
                    WHERE entry_id = %s
                    """,
                    [cashbook["source_table"], cashbook["source_id"], bank["entry_id"]],
                )
            break
    cleared = dict_rows("SELECT * FROM bank_statement_entries WHERE match_status = 'Cleared'")
    for bank in cleared:
        matched[(bank.get("matched_source"), bank.get("matched_id"))] = bank
    return matched


@permission_required("reports.view")
def reports(request):
    report = request.GET.get("report", "balances")
    if report == "balances":
        return balance_report(request)
    if report == "payments":
        return payment_report(request)
    if report == "reconciliation":
        return reconciliation_report(request)
    if report == "pupils":
        return pupil_report(request)
    config = REPORTS.get(report, REPORTS["pupils"])
    if request.path.endswith("/pdf"):
        rows = dict_rows(f"SELECT {', '.join(config['columns'])} FROM {config['table']} ORDER BY {config['order_by']} LIMIT 300")
        return export_rows(config["title"], rows, config["columns"], "pdf")
    return render_table_page(
        request,
        config["title"],
        config["table"],
        config["columns"],
        config["subtitle"],
        order_by=config["order_by"],
        actions=[
            {"label": "Students", "href": "/reports?report=pupils", "icon": "bi-mortarboard"},
            {"label": "Balances", "href": "/reports?report=balances", "icon": "bi-wallet2"},
            {"label": "Payments", "href": "/reports?report=payments", "icon": "bi-cash"},
            {"label": "Expenses", "href": "/reports?report=expenses", "icon": "bi-wallet2"},
            {"label": "Reconciliation", "href": "/reports?report=reconciliation", "icon": "bi-bank2"},
            {"label": "Results", "href": "/reports?report=results", "icon": "bi-clipboard-data"},
            {"label": "Print", "href": f"/reports/pdf?report={report}", "icon": "bi-printer"},
        ],
    )


@permission_required("statements.view")
def statement(request):
    admission_no = (request.GET.get("admission_no") or "").strip()
    settings = school_settings()
    if not admission_no:
        return render(request, "reports/student_statement.html", {"summary": None, "payments": [], "today": today_text(), "settings": settings})
    pupil = pupil_by_admission(admission_no)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/reports/statement")
    summary = student_financial_summary(pupil=pupil)
    payments = statement_payment_rows(pupil["pupil_id"], limit=500)
    statement_no = statement_number(pupil)
    export_type = (request.GET.get("export") or "").lower()
    if request.path.endswith("/pdf") or export_type == "pdf":
        return statement_pdf_response(pupil, summary, payments, settings, statement_no)
    if export_type in {"xlsx", "excel"}:
        return statement_excel(pupil, summary, payments, settings, statement_no)
    return render(
        request,
        "reports/student_statement.html",
        {"pupil": pupil, "summary": summary, "payments": payments, "today": today_text(), "settings": settings, "statement_no": statement_no},
    )


def balance_report(request):
    q = (request.GET.get("q") or "").strip()
    grade = (request.GET.get("grade") or "").strip()
    academic_level = (request.GET.get("academic_level") or "").strip()
    status = (request.GET.get("status") or "").strip()
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        page = 1
    try:
        per_page = max(10, min(100, int(request.GET.get("per_page", "25"))))
    except ValueError:
        per_page = 25
    rows, total = student_balance_rows(q=q, grade=grade, status=status, academic_level=academic_level, limit=per_page, offset=(page - 1) * per_page)
    export_type = (request.GET.get("export") or "").lower()
    columns = ["admission_no", "student_name", "grade", "class_stream", "academic_level", "total_fees_charged", "total_paid", "arrears", "current_balance", "credit_balance"]
    if export_type:
        export_rows_data, _total = student_balance_rows(q=q, grade=grade, status=status, academic_level=academic_level, limit=5000, offset=0)
        return export_rows("Student Balance Report", export_rows_data, columns, export_type)
    filters = [
        {"name": "grade", "label": "Class", "value": grade, "options": [academic_grade_option(row["grade"]) for row in dict_rows("SELECT DISTINCT grade FROM pupils WHERE grade IS NOT NULL AND TRIM(grade) != '' ORDER BY grade")]},
        {"name": "academic_level", "label": "Academic Level", "value": academic_level, "options": ["O Level", "A Level"]},
        {"name": "status", "label": "Balance Status", "value": status, "options": ["arrears", "paid", "credit"]},
    ]
    return render_rows_page(
        request,
        "Student Balance Report",
        rows,
        columns,
        "Fees arrears, payments, balances, and credit balances.",
        actions=[
            {"label": "Students", "href": "/reports?report=pupils", "icon": "bi-mortarboard"},
            {"label": "Payments", "href": "/reports?report=payments", "icon": "bi-cash"},
            {"label": "Reconciliation", "href": "/reports?report=reconciliation", "icon": "bi-bank2"},
            {"label": "Excel", "href": "?report=balances&export=xlsx", "icon": "bi-file-earmark-excel"},
            {"label": "PDF", "href": "?report=balances&export=pdf", "icon": "bi-file-earmark-pdf"},
        ],
        row_actions=[
            {"label": "Statement", "href": "/reports/statement?admission_no={admission_no}", "icon": "bi-file-text", "class": "btn-outline-primary"},
        ],
        total=total,
        page=page,
        per_page=per_page,
        filters=filters,
    )


def payment_report(request):
    q = (request.GET.get("q") or "").strip()
    method = (request.GET.get("method") or "").strip()
    term = (request.GET.get("term") or "").strip()
    year = (request.GET.get("year") or "").strip()
    academic_level = (request.GET.get("academic_level") or "").strip()
    clauses = []
    params = []
    if q:
        clauses.append("(p.receipt_no LIKE %s OR p.reference_no LIKE %s OR pu.admission_no LIKE %s OR pu.first_name LIKE %s OR pu.surname LIKE %s)")
        params.extend([f"%{q}%"] * 5)
    if method:
        clauses.append("p.payment_method = %s")
        params.append(method)
    if term:
        clauses.append("p.term = %s")
        params.append(term)
    if year:
        clauses.append("CAST(p.year AS TEXT) = %s")
        params.append(year)
    if academic_level == "O Level":
        clauses.append("(pu.grade_id BETWEEN 1 AND 4 OR pu.grade_id = 7 OR pu.grade LIKE %s OR pu.grade LIKE %s)")
        params.extend(["%Completed O%", "%O Level%"])
    elif academic_level == "A Level":
        clauses.append("(pu.grade_id BETWEEN 5 AND 6 OR pu.grade_id = 8 OR pu.grade LIKE %s OR pu.grade LIKE %s)")
        params.extend(["%Completed A%", "%A Level%"])
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = dict_rows(
        f"""
        SELECT p.receipt_no,
               pu.admission_no,
               pu.first_name || ' ' || pu.surname AS student_name,
               pu.grade,
               pu.grade_id,
               pu.class_stream,
               CASE
                 WHEN pu.grade_id BETWEEN 1 AND 4 OR pu.grade_id = 7 OR pu.grade LIKE '%%Completed O%%' OR pu.grade LIKE '%%O Level%%' THEN 'O Level'
                 WHEN pu.grade_id BETWEEN 5 AND 6 OR pu.grade_id = 8 OR pu.grade LIKE '%%Completed A%%' OR pu.grade LIKE '%%A Level%%' THEN 'A Level'
                 ELSE ''
               END AS academic_level,
               p.payment_date,
               p.term,
               p.year,
               p.payment_method,
               p.reference_no,
               p.amount_paid
        FROM payments p
        JOIN pupils pu ON pu.pupil_id = p.pupil_id
        {where}
        ORDER BY p.payment_date DESC, p.payment_id DESC
        LIMIT 5000
        """,
        params,
    )
    columns = ["receipt_no", "admission_no", "student_name", "class_label", "academic_level", "payment_date", "term", "year", "payment_method", "reference_no", "amount_paid"]
    export_type = (request.GET.get("export") or "").lower()
    if request.path.endswith("/pdf"):
        export_type = "pdf"
    if export_type:
        return export_rows("Payment Reports", rows, columns, export_type)
    filters = [
        {"name": "method", "label": "Method", "value": method, "options": [row["payment_method"] for row in dict_rows("SELECT DISTINCT payment_method FROM payments WHERE payment_method IS NOT NULL ORDER BY payment_method")]},
        {"name": "term", "label": "Term", "value": term, "options": [row["term"] for row in dict_rows("SELECT DISTINCT term FROM payments WHERE term IS NOT NULL ORDER BY term")]},
        {"name": "year", "label": "Year", "value": year, "options": [row["year"] for row in dict_rows("SELECT DISTINCT year FROM payments WHERE year IS NOT NULL ORDER BY year DESC")]},
        {"name": "academic_level", "label": "Academic Level", "value": academic_level, "options": ["O Level", "A Level"]},
    ]
    return render_rows_page(
        request,
        "Payment Reports",
        rows,
        columns,
        "Receipts by date, term, method, pupil, and reference.",
        actions=[
            {"label": "Balances", "href": "/reports?report=balances", "icon": "bi-wallet2"},
            {"label": "Excel", "href": "?report=payments&export=xlsx", "icon": "bi-file-earmark-excel"},
            {"label": "PDF", "href": "?report=payments&export=pdf", "icon": "bi-file-earmark-pdf"},
        ],
        row_actions=[{"label": "Receipt", "href": "/receipt/{receipt_no}", "icon": "bi-receipt", "class": "btn-outline-primary"}],
        filters=filters,
        total=len(rows),
    )


def reconciliation_report(request):
    start = (request.GET.get("start") or "").strip()
    end = (request.GET.get("end") or "").strip()
    if request.method == "POST":
        imported = import_bank_statement(request, request.FILES.get("statement_file"))
        messages.success(request, f"Imported {imported} new bank statement line(s).")
        return redirect(f"/reports?report=reconciliation&start={start}&end={end}")

    rows = cashbook_reconciliation_rows(start, end)
    matched_map = auto_match_bank_statement(rows)
    for row in rows:
        key = (row.get("source_table"), row.get("source_id"))
        if key in matched_map:
            row["reconciliation_status"] = "Cleared"
            row["bank_entry_id"] = matched_map[key].get("entry_id")
        elif not row.get("reference_no"):
            row["reconciliation_status"] = "No reference"
            row["bank_entry_id"] = ""
        else:
            row["reconciliation_status"] = "Outstanding"
            row["bank_entry_id"] = ""

    # Financial reconciliation calculations
    settings = school_settings()
    from finance.views import money
    base_opening = money(settings.get("cashbook_opening_balance", 0))
    
    if start:
        # Sum payments before start date
        pay_before = one_row("SELECT COALESCE(SUM(amount_paid), 0) AS total FROM payments WHERE payment_date < %s", [start])
        # Sum POS before start date
        pos_before = one_row("SELECT COALESCE(SUM(total_amount), 0) AS total FROM pos_sales WHERE sale_date < %s", [start]) if table_exists("pos_sales") else {"total": 0}
        # Sum expenses before start date
        exp_before = one_row("SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE expense_date < %s", [start])
        
        debits_before = money(pay_before["total"]) + money(pos_before["total"])
        credits_before = money(exp_before["total"])
        
        opening_balance = base_opening + debits_before - credits_before
    else:
        opening_balance = base_opening
        
    total_debit = sum((money(row.get("debit")) for row in rows), Decimal("0.00"))
    total_credit = sum((money(row.get("credit")) for row in rows), Decimal("0.00"))
    closing_balance = opening_balance + total_debit - total_credit
    rows = add_cashbook_running_balances(rows, opening_balance)
    cleared_total = sum((money(row.get("debit")) - money(row.get("credit")) for row in rows if row.get("reconciliation_status") == "Cleared"), Decimal("0.00"))
    outstanding_total = sum((money(row.get("debit")) - money(row.get("credit")) for row in rows if row.get("reconciliation_status") == "Outstanding"), Decimal("0.00"))
    bank_rows = dict_rows(
        """
        SELECT *
        FROM bank_statement_entries
        WHERE (%s = '' OR transaction_date >= %s)
          AND (%s = '' OR transaction_date <= %s)
        ORDER BY transaction_date DESC, entry_id DESC
        """,
        [start, start, end, end],
    ) if table_exists("bank_statement_entries") else []
    unmatched_bank_rows = [row for row in bank_rows if row.get("match_status") != "Cleared"]
    bank_statement_balance = sum((money(row.get("money_in")) - money(row.get("money_out")) for row in bank_rows), Decimal("0.00"))
    unmatched_bank_total = sum((money(row.get("money_in")) - money(row.get("money_out")) for row in unmatched_bank_rows), Decimal("0.00"))
    reconciliation_difference = closing_balance - bank_statement_balance

    columns = ["entry_date", "source", "method", "reference_no", "debit", "credit", "balance"]
    export_type = (request.GET.get("export") or "").lower()
    if request.path.endswith("/pdf"):
        export_type = "pdf"
    if export_type:
        return export_rows("Bank Reconciliation Statement", rows, columns, export_type)
        
    context = {
        "title": "Bank Reconciliation",
        "subtitle": "Compare cash book collections and expenses against bank references.",
        "rows": rows,
        "columns": columns,
        "start_date": start,
        "end_date": end,
        "opening_balance": opening_balance,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "closing_balance": closing_balance,
        "cleared_total": cleared_total,
        "outstanding_total": outstanding_total,
        "bank_rows": bank_rows,
        "unmatched_bank_rows": unmatched_bank_rows,
        "bank_statement_balance": bank_statement_balance,
        "unmatched_bank_total": unmatched_bank_total,
        "reconciliation_difference": reconciliation_difference,
        "settings": settings,
    }
    return render(request, "reports/bank_reconciliation.html", context)


def statement_number(pupil):
    return f"STMT-{pupil['admission_no']}-{today_text().replace('-', '')}"


def money_label(value):
    return f"USD {float(value or 0):,.2f}"


def statement_lines(pupil, summary, payments):
    settings = school_settings()
    lines = [
        f"School: {settings.get('school_name', '')}",
        f"Statement No: {statement_number(pupil)}",
        f"Admission No: {pupil['admission_no']}",
        f"Student: {pupil['first_name']} {pupil['surname']}",
        f"Class: {pupil.get('grade')} {pupil.get('class_stream')}",
        f"Opening Balance / Previous Arrears: USD {summary.get('previous_arrears', 0)}",
        f"Fees Charged: USD {summary.get('total_fees_charged', 0)}",
        f"Payments Made: USD {summary.get('total_paid', 0)}",
        f"Adjustments: USD {summary.get('manual_adjustments', 0)}",
        f"Closing Balance: USD {summary.get('overall_balance', 0)}",
        f"Credit Balance: USD {summary.get('credit_balance', 0)}",
    ]
    for payment in payments:
        lines.append(
            f"{payment['payment_date']}: {payment['receipt_no']} USD {payment['amount_paid']} "
            f"{payment['payment_method']} {payment['term']} {payment['year']} "
            f"arrears {payment.get('arrears_paid', 0)} current {payment.get('current_paid', 0)}"
        )
    return lines


def statement_pdf_response(pupil, summary, payments, settings, statement_no):
    import os
    from django.conf import settings as django_settings
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from students.services import ensure_student_photo, student_age_text

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    from school_system_django.native import get_pdf_header
    story = [
        get_pdf_header(settings, 186 * mm),
        Spacer(1, 10),
    ]
    meta = [
        ["Statement No", statement_no, "Generated", today_text()],
        ["Admission No", pupil["admission_no"], "Class", f"{pupil.get('grade') or ''} {pupil.get('class_stream') or ''}".strip()],
        ["Student", f"{pupil['first_name']} {pupil['surname']}", "Guardian", pupil.get("guardian_name") or "-"],
        ["Date of Birth", pupil.get("date_of_birth") or "-", "Age", student_age_text(pupil.get("date_of_birth")) or "-"],
    ]
    meta_table = Table(meta, colWidths=[28 * mm, 62 * mm, 28 * mm, 62 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 10)])
    summary_rows = [
        ["Opening Balance", money_label(summary.get("previous_arrears")), "Fees Charged", money_label(summary.get("total_fees_charged"))],
        ["Payments Made", money_label(summary.get("total_paid")), "Adjustments", money_label(summary.get("manual_adjustments"))],
        ["Closing Balance", money_label(summary.get("overall_balance")), "Credit Balance", money_label(summary.get("credit_balance"))],
    ]
    summary_table = Table(summary_rows, colWidths=[38 * mm, 52 * mm, 38 * mm, 52 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf7f5")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 12), Paragraph("Term Summary", styles["Heading2"])])
    term_data = [["Term", "Fees", "Adjustments", "Allocated", "Balance"]]
    for row in summary.get("periods", []):
        term_data.append(
            [
                f"{row.get('term')} {row.get('year')}",
                money_label(row.get("fees_charged")),
                money_label(row.get("adjustments")),
                money_label(row.get("paid_allocated")),
                money_label(row.get("balance")),
            ]
        )
    term_table = Table(term_data, colWidths=[34 * mm, 36 * mm, 36 * mm, 36 * mm, 36 * mm], repeatRows=1)
    term_table.setStyle(statement_table_style())
    story.extend([term_table, Spacer(1, 12), Paragraph("Receipts and Payments", styles["Heading2"])])
    payment_data = [["Receipt", "Date", "Method", "Term", "Paid", "Arrears", "Current", "Credit"]]
    for payment in payments:
        payment_data.append(
            [
                payment.get("receipt_no"),
                payment.get("payment_date"),
                payment.get("payment_method"),
                f"{payment.get('term')} {payment.get('year')}",
                money_label(payment.get("amount_paid")),
                money_label(payment.get("arrears_paid")),
                money_label(payment.get("current_paid")),
                money_label(payment.get("credit_balance")),
            ]
        )
    payment_table = Table(payment_data, colWidths=[24 * mm, 20 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 22 * mm, 20 * mm], repeatRows=1)
    payment_table.setStyle(statement_table_style(font_size=7))
    story.extend([payment_table, Spacer(1, 18)])
    story.append(Paragraph("Prepared by: ____________________    Parent/Guardian: ____________________    School Stamp: ____________________", styles["Normal"]))
    document.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="statement-{pupil["admission_no"]}.pdf"'
    return response


def statement_table_style(font_size=8):
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle

    return TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102a43")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )


def statement_excel(pupil, summary, payments, settings=None, statement_no=None):
    from openpyxl import Workbook

    settings = settings or school_settings()
    statement_no = statement_no or statement_number(pupil)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Statement"
    sheet.append(["School", settings.get("school_name") or "Student Fees Statement"])
    sheet.append(["Statement Number", statement_no])
    sheet.append(["Admission Number", pupil["admission_no"]])
    sheet.append(["Student", f"{pupil['first_name']} {pupil['surname']}"])
    sheet.append(["Class", f"{pupil.get('grade')} {pupil.get('class_stream')}"])
    sheet.append(["Guardian", pupil.get("guardian_name") or ""])
    sheet.append([])
    sheet.append(["Opening Balance", summary.get("previous_arrears", 0)])
    sheet.append(["Fees Charged", summary.get("total_fees_charged", 0)])
    sheet.append(["Payments Made", summary.get("total_paid", 0)])
    sheet.append(["Adjustments", summary.get("manual_adjustments", 0)])
    sheet.append(["Closing Balance", summary.get("overall_balance", 0)])
    sheet.append(["Credit Balance", summary.get("credit_balance", 0)])
    sheet.append([])
    sheet.append(["Receipt No", "Payment Date", "Method", "Reference", "Term", "Year", "Amount", "Arrears Paid", "Current Fees Paid", "Credit"])
    for payment in payments:
        sheet.append(
            [
                payment["receipt_no"],
                payment["payment_date"],
                payment["payment_method"],
                payment.get("reference_no") or "",
                payment["term"],
                payment["year"],
                payment["amount_paid"],
                payment.get("arrears_paid", 0),
                payment.get("current_paid", 0),
                payment.get("credit_balance", 0),
            ]
        )
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="statement-{pupil["admission_no"]}.xlsx"'
    workbook.save(response)
    return response


def pupil_report(request):
    q = (request.GET.get("q") or "").strip()
    grade = (request.GET.get("grade") or "").strip()
    academic_level = (request.GET.get("academic_level") or "").strip()
    try:
        page = max(1, int(request.GET.get("page", "1")))
    except ValueError:
        page = 1
    try:
        per_page = max(10, min(100, int(request.GET.get("per_page", "25"))))
    except ValueError:
        per_page = 25
    
    clauses = []
    params = []
    if q:
        clauses.append("(p.admission_no LIKE %s OR p.first_name LIKE %s OR p.surname LIKE %s OR p.guardian_name LIKE %s)")
        params.extend([f"%{q}%"] * 4)
    if grade:
        clauses.append("p.grade = %s")
        params.append(grade)
    if academic_level == "O Level":
        clauses.append("(p.grade_id BETWEEN 1 AND 4 OR p.grade_id = 7 OR p.grade LIKE %s OR p.grade LIKE %s)")
        params.extend(["%Completed O%", "%O Level%"])
    elif academic_level == "A Level":
        clauses.append("(p.grade_id BETWEEN 5 AND 6 OR p.grade_id = 8 OR p.grade LIKE %s OR p.grade LIKE %s)")
        params.extend(["%Completed A%", "%A Level%"])
    
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    
    sql = f"""
        SELECT p.pupil_id,
               p.photo_path,
               p.date_of_birth,
               p.admission_no,
               p.first_name,
               p.surname,
               p.grade,
               p.grade_id,
               p.class_stream,
               CASE
                 WHEN p.grade_id BETWEEN 1 AND 4 OR p.grade_id = 7 OR p.grade LIKE '%%Completed O%%' OR p.grade LIKE '%%O Level%%' THEN 'O Level'
                 WHEN p.grade_id BETWEEN 5 AND 6 OR p.grade_id = 8 OR p.grade LIKE '%%Completed A%%' OR p.grade LIKE '%%A Level%%' THEN 'A Level'
                 ELSE ''
               END AS academic_level,
               p.status,
               (COALESCE(charges.total, 0) + COALESCE(adjustments.total, 0) - COALESCE(payments.total, 0)) AS balance
        FROM pupils p
        LEFT JOIN (SELECT pupil_id, SUM(amount_billed) AS total FROM term_bills GROUP BY pupil_id) charges ON charges.pupil_id = p.pupil_id
        LEFT JOIN (SELECT pupil_id, SUM(amount) AS total FROM balance_adjustments GROUP BY pupil_id) adjustments ON adjustments.pupil_id = p.pupil_id
        LEFT JOIN (SELECT pupil_id, SUM(amount_paid) AS total FROM payments GROUP BY pupil_id) payments ON payments.pupil_id = p.pupil_id
        {where}
        ORDER BY p.surname, p.first_name
        LIMIT %s OFFSET %s
    """
    count_sql = f"SELECT COUNT(*) AS total FROM pupils p {where}"
    
    rows = dict_rows(sql, params + [per_page, (page - 1) * per_page])
    total_row = one_row(count_sql, params)
    total = int(total_row["total"] or 0) if total_row else 0
    
    columns = ["admission_no", "first_name", "surname", "age", "grade", "class_stream", "academic_level", "status", "balance"]
    export_columns = ["admission_no", "first_name", "surname", "age", "grade", "class_stream", "academic_level", "status", "balance"]
    
    export_type = (request.GET.get("export") or "").lower()
    if request.path.endswith("/pdf"):
        export_type = "pdf"
    if export_type:
        export_sql = f"""
            SELECT p.pupil_id,
                   p.photo_path,
                   p.date_of_birth,
                   p.admission_no,
                   p.first_name,
                   p.surname,
                   p.grade,
                   p.grade_id,
                   p.class_stream,
                   CASE
                     WHEN p.grade_id BETWEEN 1 AND 4 OR p.grade_id = 7 OR p.grade LIKE '%%Completed O%%' OR p.grade LIKE '%%O Level%%' THEN 'O Level'
                     WHEN p.grade_id BETWEEN 5 AND 6 OR p.grade_id = 8 OR p.grade LIKE '%%Completed A%%' OR p.grade LIKE '%%A Level%%' THEN 'A Level'
                     ELSE ''
                   END AS academic_level,
                   p.status,
                   (COALESCE(charges.total, 0) + COALESCE(adjustments.total, 0) - COALESCE(payments.total, 0)) AS balance
            FROM pupils p
            LEFT JOIN (SELECT pupil_id, SUM(amount_billed) AS total FROM term_bills GROUP BY pupil_id) charges ON charges.pupil_id = p.pupil_id
            LEFT JOIN (SELECT pupil_id, SUM(amount) AS total FROM balance_adjustments GROUP BY pupil_id) adjustments ON adjustments.pupil_id = p.pupil_id
            LEFT JOIN (SELECT pupil_id, SUM(amount_paid) AS total FROM payments GROUP BY pupil_id) payments ON payments.pupil_id = p.pupil_id
            {where}
            ORDER BY p.surname, p.first_name
            LIMIT 5000
        """
        export_rows_data = dict_rows(export_sql, params)
        from school_system_django.native import hydrate_student_display_fields
        export_rows_data = hydrate_student_display_fields(export_rows_data)
        return export_rows("Student Report", export_rows_data, export_columns, export_type)
        
    filters = [
        {"name": "grade", "label": "Class", "value": grade, "options": [academic_grade_option(row["grade"]) for row in dict_rows("SELECT DISTINCT grade FROM pupils WHERE grade IS NOT NULL AND TRIM(grade) != '' ORDER BY grade")]},
        {"name": "academic_level", "label": "Academic Level", "value": academic_level, "options": ["O Level", "A Level"]},
    ]
    
    return render_rows_page(
        request,
        "Student Reports",
        rows,
        columns,
        "Learner profile registry with current fee balances.",
        actions=[
            {"label": "Balances", "href": "/reports?report=balances", "icon": "bi-wallet2"},
            {"label": "Payments", "href": "/reports?report=payments", "icon": "bi-cash"},
            {"label": "Excel", "href": "?report=pupils&export=xlsx", "icon": "bi-file-earmark-excel"},
            {"label": "PDF", "href": "?report=pupils&export=pdf", "icon": "bi-file-earmark-pdf"},
        ],
        row_actions=[
            {"label": "Statement", "href": "/reports/statement?admission_no={admission_no}", "icon": "bi-file-text", "class": "btn-outline-primary"},
        ],
        total=total,
        page=page,
        per_page=per_page,
        filters=filters,
    )

# Create your views here.
