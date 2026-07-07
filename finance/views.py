from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import connection, transaction
from django.shortcuts import redirect, render

from accounts.permissions import permission_required
from fees.views import payments, record_payment, structure
from school_system_django.native import (
    audit_action,
    delete_record,
    dict_rows,
    insert_record,
    legacy_user_id,
    now_text,
    one_row,
    render_detail_page,
    render_record_form_page,
    render_table_page,
    simple_pdf,
    table_exists,
    today_text,
    update_record,
    school_settings,
)
from school_system_django.official_docs import published_date_time, qr_data_uri, qr_flowable


def receipt_absolute_url(request, path):
    return request.build_absolute_uri(path) if request else path


EXPENSE_FIELDS = ["expense_date", "amount", "category", "description", "payment_method", "reference_no", "notes"]
INVENTORY_FIELDS = ["item_name", "category", "quantity", "unit", "location", "reorder_level", "sku", "sale_price", "is_sellable", "notes"]
POS_FIELDS = ["receipt_no", "sale_date", "customer_name", "pupil_id", "payment_method", "reference_no", "total_amount", "notes"]


def fees_structure(request):
    return structure(request)


def money(value):
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def cashbook_source_rows(exclude_expense_id=None, candidate_expense=None):
    rows = []
    rows.extend(
        dict_rows(
            """
            SELECT payment_id AS source_id, payment_date AS entry_date, 'payments' AS source_table,
                   amount_paid AS debit, 0 AS credit
            FROM payments
            """
        )
    )
    if table_exists("pos_sales"):
        rows.extend(
            dict_rows(
                """
                SELECT sale_id AS source_id, sale_date AS entry_date, 'pos_sales' AS source_table,
                       total_amount AS debit, 0 AS credit
                FROM pos_sales
                """
            )
        )
    expense_params = []
    expense_where = ""
    if exclude_expense_id:
        expense_where = "WHERE expense_id != %s"
        expense_params.append(exclude_expense_id)
    rows.extend(
        dict_rows(
            f"""
            SELECT expense_id AS source_id, expense_date AS entry_date, 'expenses' AS source_table,
                   0 AS debit, amount AS credit
            FROM expenses
            {expense_where}
            """,
            expense_params,
        )
    )
    if candidate_expense:
        rows.append(
            {
                "source_id": candidate_expense.get("source_id") or 0,
                "entry_date": candidate_expense.get("expense_date"),
                "source_table": "expenses",
                "debit": Decimal("0.00"),
                "credit": money(candidate_expense.get("amount")),
            }
        )
    return rows


def cashbook_sort_key(row):
    source_order = {"payments": 1, "pos_sales": 2, "expenses": 3}
    return (
        str(row.get("entry_date") or ""),
        source_order.get(str(row.get("source_table") or ""), 99),
        int(row.get("source_id") or 0),
    )


def projected_cashbook_balance(candidate_expense=None, exclude_expense_id=None):
    settings = school_settings()
    running_balance = money(settings.get("cashbook_opening_balance", 0))
    minimum_balance = running_balance
    for row in sorted(cashbook_source_rows(exclude_expense_id=exclude_expense_id, candidate_expense=candidate_expense), key=cashbook_sort_key):
        running_balance += money(row.get("debit")) - money(row.get("credit"))
        minimum_balance = min(minimum_balance, running_balance)
    return running_balance, minimum_balance


def validate_expense_affordability(amount, expense_date=None, exclude_expense_id=None):
    amount_value = money(amount)
    if amount_value <= 0:
        raise ValueError("Expense amount must be greater than zero.")
    _closing_balance, minimum_balance = projected_cashbook_balance(
        candidate_expense={"amount": amount_value, "expense_date": expense_date or today_text(), "source_id": exclude_expense_id or 0},
        exclude_expense_id=exclude_expense_id,
    )
    if minimum_balance < 0:
        raise ValueError(
            f"Expense denied. It would make the school account negative by USD {abs(minimum_balance):,.2f}. "
            "Record income first or reduce the expense amount."
        )


def expense_form_fields(values=None):
    values = values or {}
    return [
        {"name": "expense_date", "label": "Expense Date", "type": "date", "value": values.get("expense_date") or today_text(), "required": True},
        {"name": "amount", "label": "Amount", "type": "number", "value": values.get("amount") or "", "required": True},
        {"name": "category", "label": "Category", "value": values.get("category") or "", "required": True},
        {"name": "description", "label": "Description", "widget": "textarea", "value": values.get("description") or "", "required": True},
        {"name": "payment_method", "label": "Payment Method", "value": values.get("payment_method") or "Cash", "required": True},
        {"name": "reference_no", "label": "Reference No", "value": values.get("reference_no") or ""},
        {"name": "notes", "label": "Notes", "widget": "textarea", "value": values.get("notes") or ""},
    ]


def posted_expense_data(request):
    return {field: (request.POST.get(field) or "").strip() for field in EXPENSE_FIELDS}


def next_master_receipt_no(receipt_type="Fees"):
    year = today_text()[:4]
    prefix = f"MR{year}{'POS' if receipt_type == 'POS' else 'FEE'}"
    rows = dict_rows(
        "SELECT master_receipt_no FROM master_receipts WHERE master_receipt_no LIKE %s ORDER BY master_receipt_no DESC LIMIT 100",
        [f"{prefix}%"],
    )
    highest = 0
    for row in rows:
        suffix = str(row.get("master_receipt_no") or "").replace(prefix, "")
        highest = max(highest, int(suffix or 0) if suffix.isdigit() else 0)
    return f"{prefix}{highest + 1:04d}"


def next_pos_receipt_no():
    year = today_text()[:4]
    prefix = f"POS{year}"
    rows = dict_rows("SELECT receipt_no FROM pos_sales WHERE receipt_no LIKE %s ORDER BY receipt_no DESC LIMIT 100", [f"{prefix}%"])
    highest = 0
    for row in rows:
        suffix = str(row.get("receipt_no") or "").replace(prefix, "")
        highest = max(highest, int(suffix or 0) if suffix.isdigit() else 0)
    return f"{prefix}{highest + 1:05d}"


@permission_required("master_receipts.manage")
def master_receipts(request):
    return render_table_page(
        request,
        "Master Receipts",
        "master_receipts",
        ["master_receipt_id", "master_receipt_no", "batch_date", "total_amount", "receipt_count", "receipt_type"],
        "Cash handover and grouped receipts.",
        order_by="batch_date DESC, master_receipt_id DESC",
        search_columns=["master_receipt_no", "receipt_type"],
        pk_column="master_receipt_id",
        create_href="/master-receipts/new",
        create_label="Generate Master Receipt",
        row_actions=[
            {"label": "View", "href": "/master-receipts/{master_receipt_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "PDF", "href": "/master-receipts/{master_receipt_id}/pdf", "icon": "bi-file-earmark-pdf", "class": "btn-outline-info"},
        ],
    )


@permission_required("master_receipts.manage")
def master_receipt_new(request):
    if request.method == "POST":
        batch_date = request.POST.get("batch_date") or today_text()
        receipt_type = request.POST.get("receipt_type") or "Fees"
        notes = request.POST.get("notes") or ""
        source_table = "pos_sales" if receipt_type == "POS" else "payments"
        amount_column = "total_amount" if receipt_type == "POS" else "amount_paid"
        rows = dict_rows(
            f"""
            SELECT {amount_column} AS amount
            FROM {source_table}
            WHERE sale_date = %s AND master_receipt_id IS NULL
            """ if receipt_type == "POS" else f"""
            SELECT {amount_column} AS amount
            FROM {source_table}
            WHERE payment_date = %s AND master_receipt_id IS NULL
            """,
            [batch_date],
        )
        if not rows:
            messages.error(request, "No unbatched receipts were found for that date and type.")
        else:
            total = sum((money(row.get("amount")) for row in rows), Decimal("0.00"))
            with transaction.atomic():
                master_no = next_master_receipt_no(receipt_type)
                master_id = insert_record(
                    request,
                    "master_receipts",
                    {
                        "master_receipt_no": master_no,
                        "batch_date": batch_date,
                        "generated_at": now_text(),
                        "total_amount": total,
                        "receipt_count": len(rows),
                        "notes": notes,
                        "generated_by": legacy_user_id(request),
                        "receipt_type": receipt_type,
                    },
                )
                with connection.cursor() as cursor:
                    if receipt_type == "POS":
                        cursor.execute("UPDATE pos_sales SET master_receipt_id = %s WHERE sale_date = %s AND master_receipt_id IS NULL", [master_id, batch_date])
                    else:
                        cursor.execute("UPDATE payments SET master_receipt_id = %s WHERE payment_date = %s AND master_receipt_id IS NULL", [master_id, batch_date])
                audit_action(request, "Generate master receipt", f"Master receipt {master_no} generated for {receipt_type} {batch_date}.")
            messages.success(request, f"Master receipt {master_no} generated.")
            return redirect(f"/master-receipts/{master_id}")
    return render(
        request,
        "finance/master_receipt_form.html",
        {"today": today_text(), "receipt_types": ["Fees", "POS"]},
    )


@permission_required("expenses.manage")
def expenses(request):
    return render_table_page(
        request,
        "Expense Ledger",
        "expenses",
        ["expense_id", "expense_date", "amount", "category", "description", "payment_method", "reference_no"],
        "School expenditure and reconciliation records.",
        order_by="expense_date DESC, expense_id DESC",
        search_columns=["category", "description", "payment_method", "reference_no"],
        pk_column="expense_id",
        create_href="/expenses/new",
        create_label="Record Expense",
        row_actions=[
            {"label": "View", "href": "/expenses/{expense_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/expenses/{expense_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/expenses/{expense_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this expense?"},
        ],
    )


@permission_required("expenses.manage")
def record_expense(request):
    values = {"expense_date": today_text(), "payment_method": "Cash"}
    if request.method == "POST":
        values = posted_expense_data(request)
        try:
            validate_expense_affordability(values.get("amount"), values.get("expense_date"))
            insert_record(request, "expenses", {**values, "created_at": now_text()})
            audit_action(request, "Record Expense", f"Expense {values.get('category')} amount {values.get('amount')} recorded.")
            messages.success(request, "Expense saved.")
            return redirect("/expenses")
        except Exception as exc:
            messages.error(request, f"Could not save expense: {exc}")
    return render(
        request,
        "school/form_page.html",
        {
            "title": "Record Expense",
            "subtitle": "Record school expenditure. Expenses cannot exceed the available school account balance.",
            "fields": expense_form_fields(values),
            "settings": school_settings(),
        },
    )


@permission_required("pos.manage")
def pos(request):
    return render_table_page(
        request,
        "Uniform POS",
        "pos_sales",
        ["sale_id", "receipt_no", "sale_date", "customer_name", "payment_method", "total_amount"],
        "Point-of-sale receipt history.",
        order_by="sale_date DESC, sale_id DESC",
        search_columns=["receipt_no", "customer_name", "payment_method"],
        pk_column="sale_id",
        create_href="/uniform-pos/new",
        create_label="New Sale",
        row_actions=[
            {"label": "Receipt", "href": "/uniform-pos/receipt/{sale_id}", "icon": "bi-receipt", "class": "btn-outline-primary"},
            {"label": "PDF", "href": "/uniform-pos/receipt/{sale_id}/pdf", "icon": "bi-file-earmark-pdf", "class": "btn-outline-info"},
            {"label": "Edit", "href": "/uniform-pos/{sale_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
        ],
    )


def master_receipt_pdf_response(master, transactions, classification, request=None):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.http import HttpResponse
    from school_system_django.native import school_settings, one_row

    settings = school_settings()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=12 * mm, leftMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'SchoolNameMR',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#102a43'),
        alignment=1,
        spaceAfter=2
    )

    meta_style = ParagraphStyle(
        'SchoolMetaMR',
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#486581'),
        alignment=1,
        spaceAfter=15
    )

    label_style = ParagraphStyle(
        'LabelMR',
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#486581')
    )

    val_style = ParagraphStyle(
        'ValueMR',
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#102a43')
    )

    header_cell_style = ParagraphStyle(
        'HeaderCellMR',
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.white,
        alignment=1
    )

    story = []

    # Header
    from school_system_django.native import get_pdf_header
    story.append(get_pdf_header(settings, 186 * mm))
    story.append(Paragraph("<b>MASTER RECEIPT BATCH REPORT</b>", styles["Heading2"]))
    story.append(Spacer(1, 10))

    # Metadata Grid
    # Resolve generated by username
    gen_by = "-"
    if master.get("generated_by"):
        usr = one_row("SELECT username, role, full_name FROM users WHERE user_id = %s", [master["generated_by"]])
        if usr:
            gen_by = usr.get("full_name") or usr.get("username") or "-"

    meta = [
        [Paragraph("Master Receipt No", label_style), Paragraph(master.get("master_receipt_no") or "-", val_style),
         Paragraph("Batch Date", label_style), Paragraph(master.get("batch_date") or "-", val_style)],
        [Paragraph("Receipt Type", label_style), Paragraph(master.get("receipt_type") or "-", val_style),
         Paragraph("Total Amount", label_style), Paragraph(f"USD {float(master.get('total_amount') or 0):,.2f}", val_style)],
        [Paragraph("Receipt Count", label_style), Paragraph(str(master.get('receipt_count') or 0), val_style),
         Paragraph("Generated By", label_style), Paragraph(gen_by, val_style)]
    ]
    meta_table = Table(meta, colWidths=[35 * mm, 50 * mm, 35 * mm, 50 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 15)])

    if master.get("notes"):
        story.append(Paragraph("<b>Notes / Remarks:</b>", label_style))
        story.append(Paragraph(master["notes"], val_style))
        story.append(Spacer(1, 10))

    # Payment Classification Summary
    story.append(Paragraph("<b>Payment Method Classification</b>", styles["Heading3"]))
    story.append(Spacer(1, 5))
    class_headers = [Paragraph("Payment Method", label_style), Paragraph("Total Amount Grouped", label_style)]
    class_data = [class_headers]
    for row in classification:
        class_data.append([
            Paragraph(row["method"], val_style),
            Paragraph(f"USD {float(row['amount']):,.2f}", val_style)
        ])
    class_table = Table(class_data, colWidths=[80 * mm, 90 * mm])
    c_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ])
    class_table.setStyle(c_style)
    story.extend([class_table, Spacer(1, 15)])

    # Grouped Receipts Details
    story.append(Paragraph("<b>Grouped Transactions List</b>", styles["Heading3"]))
    story.append(Spacer(1, 5))
    
    tx_headers = [
        Paragraph("Receipt No", header_cell_style),
        Paragraph("Customer / Pupil Name", header_cell_style),
        Paragraph("Method", header_cell_style),
        Paragraph("Reference No", header_cell_style),
        Paragraph("Amount", header_cell_style)
    ]
    tx_data = [tx_headers]
    for tx in transactions:
        tx_data.append([
            Paragraph(tx.get("receipt_no") or "-", val_style),
            Paragraph(tx.get("customer_name") or "-", val_style),
            Paragraph(tx.get("payment_method") or "-", val_style),
            Paragraph(tx.get("reference_no") or "-", val_style),
            Paragraph(f"USD {float(tx.get('total_amount') or 0):,.2f}", val_style)
        ])
    
    tx_table = Table(tx_data, colWidths=[30 * mm, 55 * mm, 30 * mm, 30 * mm, 25 * mm])
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#102a43')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d9e2ec')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#102a43')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ])
    for i in range(1, len(tx_data)):
        if i % 2 == 0:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f0f4f8'))
        else:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.white)
    tx_table.setStyle(t_style)
    story.extend([tx_table, Spacer(1, 15)])

    verify_url = receipt_absolute_url(request, f"/master-receipts/{master.get('master_receipt_id')}")
    generated_date, generated_time = published_date_time(master.get("generated_at") or master.get("batch_date") or now_text())
    qr = qr_flowable(verify_url, size_mm=24)
    verify_cells = [
        Paragraph("<b>SCAN TO VERIFY AUTHENTICITY</b>", label_style),
        Paragraph(f"Verification ID: {master.get('master_receipt_no') or '-'}", val_style),
        Paragraph(f"Generated: {generated_date} {generated_time}", val_style),
        Paragraph(verify_url, val_style),
    ]
    if qr:
        verify_cells.insert(0, qr)
    verify_table = Table(
        [verify_cells],
        colWidths=[30 * mm, 35 * mm, 40 * mm, 40 * mm, 25 * mm] if qr else [40 * mm, 45 * mm, 45 * mm, 40 * mm],
    )
    verify_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([verify_table, Spacer(1, 15)])

    # Signatures
    story.append(Paragraph("Prepared By: ____________________    Authorized By: ____________________    Stamp: ____________________", val_style))

    document.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="master-receipt-{master.get("master_receipt_no")}.pdf"'
    return response


@permission_required("master_receipts.manage")
def master_receipt_detail(request, master_receipt_id):
    from school_system_django.native import one_row, dict_rows, school_settings
    from collections import defaultdict
    from django.contrib import messages
    from django.shortcuts import redirect

    master_receipt = one_row("SELECT * FROM master_receipts WHERE master_receipt_id = %s", [master_receipt_id])
    if not master_receipt:
        messages.error(request, "Master receipt not found.")
        return redirect("/master-receipts")

    receipt_type = master_receipt.get("receipt_type") or "Fees"
    
    if receipt_type == "POS":
        transactions = dict_rows(
            """
            SELECT receipt_no, customer_name, total_amount, payment_method, sale_date, reference_no
            FROM pos_sales
            WHERE master_receipt_id = %s
            ORDER BY receipt_no
            """,
            [master_receipt_id]
        )
    else:
        transactions = dict_rows(
            """
            SELECT p.receipt_no, pu.first_name || ' ' || pu.surname AS customer_name, pu.admission_no,
                   p.amount_paid AS total_amount, p.payment_method, p.payment_date AS sale_date, p.reference_no
            FROM payments p
            JOIN pupils pu ON pu.pupil_id = p.pupil_id
            WHERE p.master_receipt_id = %s
            ORDER BY p.receipt_no
            """,
            [master_receipt_id]
        )

    # Classify transactions by payment method
    breakdown = defaultdict(Decimal)
    for tx in transactions:
        method = tx.get("payment_method") or "Other"
        breakdown[method] += Decimal(str(tx.get("total_amount") or 0))
    
    classification = [{"method": method, "amount": amount} for method, amount in breakdown.items()]
    classification.sort(key=lambda x: x["amount"], reverse=True)

    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        return master_receipt_pdf_response(master_receipt, transactions, classification, request=request)

    verify_url = receipt_absolute_url(request, f"/master-receipts/{master_receipt_id}")
    receipt_date, receipt_time = published_date_time(master_receipt.get("generated_at") or master_receipt.get("batch_date") or now_text())

    return render(
        request,
        "finance/master_receipt_detail.html",
        {
            "master_receipt": master_receipt,
            "transactions": transactions,
            "classification": classification,
            "settings": school_settings(),
            "receipt_verify_url": verify_url,
            "receipt_qr_data_uri": qr_data_uri(verify_url),
            "receipt_date": receipt_date,
            "receipt_time": receipt_time,
        }
    )


@permission_required("expenses.manage")
def expense_detail(request, expense_id):
    return render_detail_page(request, "Expense", "expenses", "expense_id", expense_id)


@permission_required("expenses.manage")
def expense_edit(request, expense_id):
    expense = one_row("SELECT * FROM expenses WHERE expense_id = %s", [expense_id])
    if not expense:
        messages.error(request, "Expense was not found.")
        return redirect("/expenses")
    values = expense
    if request.method == "POST":
        values = posted_expense_data(request)
        try:
            validate_expense_affordability(values.get("amount"), values.get("expense_date"), exclude_expense_id=expense_id)
            update_record(request, "expenses", "expense_id", expense_id, values)
            audit_action(request, "Edit Expense", f"Expense {expense_id} updated. Amount {values.get('amount')}.")
            messages.success(request, "Expense updated.")
            return redirect(f"/expenses/{expense_id}")
        except Exception as exc:
            messages.error(request, f"Could not update expense: {exc}")
    return render(
        request,
        "school/form_page.html",
        {
            "title": "Edit Expense",
            "subtitle": "Update school expenditure. Expenses cannot exceed the available school account balance.",
            "fields": expense_form_fields(values),
            "settings": school_settings(),
        },
    )


@permission_required("expenses.manage")
def expense_delete(request, expense_id):
    return delete_record(request, "Expense", "expenses", "expense_id", expense_id, "/expenses")


@permission_required("inventory.manage")
def inventory(request):
    return render_table_page(
        request,
        "Inventory",
        "inventory_items",
        ["item_id", "item_name", "category", "quantity", "unit", "location", "reorder_level", "sku", "sale_price", "is_sellable"],
        "Stock, uniforms, assets, and reorder tracking.",
        order_by="item_name",
        search_columns=["item_name", "category", "sku", "location"],
        pk_column="item_id",
        create_href="/inventory/new",
        create_label="New Inventory Item",
        row_actions=[
            {"label": "View", "href": "/inventory/{item_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/inventory/{item_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Add Stock", "href": "/inventory/{item_id}/add-stock", "icon": "bi-plus-square", "class": "btn-outline-success"},
            {"label": "Delete", "href": "/inventory/{item_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this inventory item?"},
        ],
    )


@permission_required("inventory.manage")
def inventory_detail(request, item_id):
    return render_detail_page(request, "Inventory Item", "inventory_items", "item_id", item_id)


@permission_required("inventory.manage")
def inventory_new(request):
    return render_record_form_page(request, "New Inventory Item", "inventory_items", INVENTORY_FIELDS, redirect_to="/inventory")


@permission_required("inventory.manage")
def inventory_edit(request, item_id):
    return render_record_form_page(request, "Edit Inventory Item", "inventory_items", INVENTORY_FIELDS, pk_column="item_id", pk_value=item_id, redirect_to=f"/inventory/{item_id}")


@permission_required("inventory.manage")
def inventory_delete(request, item_id):
    return delete_record(request, "Inventory Item", "inventory_items", "item_id", item_id, "/inventory")


@permission_required("pos.manage")
def pos_new(request):
    items = dict_rows(
        """
        SELECT item_id, item_name, quantity, unit, sale_price, sku
        FROM inventory_items
        WHERE CAST(COALESCE(is_sellable, 0) AS TEXT) IN ('1', 'true', 'True', 'Yes')
        ORDER BY item_name
        """
    )
    if request.method == "POST":
        item_ids = request.POST.getlist("item_ids")
        quantities = request.POST.getlist("quantities")
        unit_prices = request.POST.getlist("unit_prices")
        
        if not item_ids:
            messages.error(request, "Please add at least one item to checkout.")
        else:
            valid = True
            lines_to_save = []
            total_amount = Decimal("0.00")
            
            for i in range(len(item_ids)):
                try:
                    qty = money(quantities[i])
                    price = money(unit_prices[i])
                    item_id = int(item_ids[i])
                except (IndexError, ValueError, TypeError):
                    messages.error(request, f"Invalid data for item line {i + 1}.")
                    valid = False
                    break
                
                if qty <= 0:
                    messages.error(request, "Quantity must be greater than zero for all items.")
                    valid = False
                    break
                
                item = one_row("SELECT * FROM inventory_items WHERE item_id = %s", [item_id])
                if not item:
                    messages.error(request, "Selected item was not found in inventory.")
                    valid = False
                    break
                
                if money(item.get("quantity")) < qty:
                    messages.error(request, f"Insufficient stock for '{item['item_name']}'. Available: {item['quantity']}.")
                    valid = False
                    break
                
                line_total = qty * price
                total_amount += line_total
                lines_to_save.append({
                    "item": item,
                    "quantity": qty,
                    "unit_price": price,
                    "line_total": line_total
                })
            
            if valid and lines_to_save:
                with transaction.atomic():
                    receipt_no = next_pos_receipt_no()
                    sale_id = insert_record(
                        request,
                        "pos_sales",
                        {
                            "receipt_no": receipt_no,
                            "sale_date": request.POST.get("sale_date") or today_text(),
                            "customer_name": request.POST.get("customer_name") or "Walk-in Customer",
                            "pupil_id": request.POST.get("pupil_id") or None,
                            "payment_method": request.POST.get("payment_method") or "Cash",
                            "reference_no": request.POST.get("reference_no") or None,
                            "total_amount": total_amount,
                            "notes": request.POST.get("notes") or "",
                            "recorded_by": legacy_user_id(request),
                            "created_at": now_text(),
                        },
                    )
                    
                    for line in lines_to_save:
                        item = line["item"]
                        qty = line["quantity"]
                        price = line["unit_price"]
                        line_total = line["line_total"]
                        
                        insert_record(
                            request,
                            "pos_sale_items",
                            {
                                "sale_id": sale_id,
                                "item_id": item["item_id"],
                                "item_name": item["item_name"],
                                "quantity": qty,
                                "unit_price": price,
                                "line_total": line_total,
                            },
                        )
                        
                        # Reduce stock
                        with connection.cursor() as cursor:
                            cursor.execute(
                                "UPDATE inventory_items SET quantity = quantity - %s, updated_at = %s WHERE item_id = %s",
                                [qty, now_text(), item["item_id"]]
                            )
                        
                        # Inventory movement
                        insert_record(
                            request,
                            "inventory_movements",
                            {
                                "item_id": item["item_id"],
                                "movement_type": "Stock Out",
                                "quantity": qty,
                                "movement_date": today_text(),
                                "reference_no": receipt_no,
                                "notes": f"POS sale {receipt_no}",
                                "recorded_by": legacy_user_id(request),
                                "created_at": now_text(),
                                "sale_id": sale_id,
                            },
                        )
                    
                    audit_action(request, "Create POS receipt", f"POS receipt {receipt_no} total {total_amount}.")
                messages.success(request, f"POS receipt {receipt_no} generated and stock reduced.")
                return redirect(f"/uniform-pos/receipt/{sale_id}")
    return render(request, "finance/pos_form.html", {"items": items, "today": today_text(), "receipt_no": next_pos_receipt_no()})


@permission_required("pos.manage")
def pos_edit(request, sale_id):
    return render_record_form_page(request, "Edit POS Sale", "pos_sales", POS_FIELDS, pk_column="sale_id", pk_value=sale_id, redirect_to=f"/uniform-pos/receipt/{sale_id}")


def pos_receipt_pdf_response(row, items, request=None):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.http import HttpResponse
    from school_system_django.native import school_settings

    settings = school_settings()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'SchoolName',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#102a43'),
        alignment=1,
        spaceAfter=2
    )

    meta_style = ParagraphStyle(
        'SchoolMeta',
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#486581'),
        alignment=1,
        spaceAfter=15
    )

    label_style = ParagraphStyle(
        'Label',
        fontName='Helvetica-Bold',
        fontSize=9,
        textColor=colors.HexColor('#486581')
    )

    val_style = ParagraphStyle(
        'Value',
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#102a43')
    )

    story = []

    # Header
    from school_system_django.native import get_pdf_header
    story.append(get_pdf_header(settings, 180 * mm))
    story.append(Paragraph("<b>POINT OF SALE RECEIPT</b>", styles["Heading2"]))
    story.append(Spacer(1, 10))

    # Metadata Grid
    meta = [
        [Paragraph("Receipt No", label_style), Paragraph(row.get("receipt_no") or "-", val_style),
         Paragraph("Sale Date", label_style), Paragraph(row.get("sale_date") or "-", val_style)],
        [Paragraph("Customer Name", label_style), Paragraph(row.get("customer_name") or "-", val_style),
         Paragraph("Payment Method", label_style), Paragraph(row.get("payment_method") or "-", val_style)],
        [Paragraph("Reference No", label_style), Paragraph(row.get("reference_no") or "-", val_style),
         Paragraph("Recorded By", label_style), Paragraph(str(row.get("recorded_by") or "-"), val_style)]
    ]
    meta_table = Table(meta, colWidths=[35 * mm, 50 * mm, 35 * mm, 50 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 15)])

    # Items Table
    headers = [Paragraph("Item Name", label_style), Paragraph("Quantity", label_style), Paragraph("Unit Price", label_style), Paragraph("Total", label_style)]
    table_data = [headers]

    for item in items:
        table_data.append([
            Paragraph(item.get("item_name") or "-", val_style),
            Paragraph(f"{float(item.get('quantity', 0)):g}", val_style),
            Paragraph(f"USD {float(item.get('unit_price', 0)):,.2f}", val_style),
            Paragraph(f"USD {float(item.get('line_total', 0)):,.2f}", val_style)
        ])

    items_table = Table(table_data, colWidths=[80 * mm, 30 * mm, 30 * mm, 30 * mm])
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#102a43')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d9e2ec')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#102a43')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f0f4f8'))
        else:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.white)
    items_table.setStyle(t_style)
    story.extend([items_table, Spacer(1, 15)])

    # Total Amount
    summary = [
        [Paragraph("<b>Grand Total</b>", label_style), Paragraph(f"<b>USD {float(row.get('total_amount', 0)):,.2f}</b>", val_style)],
    ]
    summary_table = Table(summary, colWidths=[120 * mm, 50 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 15)])

    verify_url = receipt_absolute_url(request, f"/uniform-pos/receipt/{row.get('sale_id')}")
    receipt_date, receipt_time = published_date_time(row.get("created_at") or row.get("sale_date") or now_text())
    qr = qr_flowable(verify_url, size_mm=24)
    verify_cells = [
        Paragraph("<b>SCAN TO VERIFY AUTHENTICITY</b>", label_style),
        Paragraph(f"Verification ID: {row.get('receipt_no') or '-'}", val_style),
        Paragraph(f"Issued: {receipt_date} {receipt_time}", val_style),
        Paragraph(verify_url, val_style),
    ]
    if qr:
        verify_cells.insert(0, qr)
    verify_table = Table(
        [verify_cells],
        colWidths=[30 * mm, 35 * mm, 35 * mm, 35 * mm, 35 * mm] if qr else [42 * mm, 42 * mm, 42 * mm, 44 * mm],
    )
    verify_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([verify_table, Spacer(1, 20)])

    if row.get("notes"):
        story.append(Paragraph("<b>Notes:</b>", label_style))
        story.append(Paragraph(row.get("notes"), val_style))
        story.append(Spacer(1, 25))

    # Signatures
    story.append(Paragraph("Bursar Signature: ____________________    Customer Signature: ____________________", val_style))

    document.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="pos-receipt-{row.get("receipt_no")}.pdf"'
    return response


@permission_required("pos.manage")
def pos_receipt(request, sale_id):
    row = one_row("SELECT * FROM pos_sales WHERE sale_id = %s", [sale_id])
    items = dict_rows("SELECT * FROM pos_sale_items WHERE sale_id = %s", [sale_id])
    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        return pos_receipt_pdf_response(row, items, request=request)
    verify_url = receipt_absolute_url(request, f"/uniform-pos/receipt/{sale_id}")
    receipt_date, receipt_time = published_date_time(row.get("created_at") or row.get("sale_date") or now_text())
    return render(
        request,
        "finance/pos_receipt.html",
        {
            "sale": row,
            "items": items,
            "receipt_verify_url": verify_url,
            "receipt_qr_data_uri": qr_data_uri(verify_url),
            "receipt_date": receipt_date,
            "receipt_time": receipt_time,
        },
    )


@permission_required("inventory.manage")
def inventory_add_stock(request, item_id):
    item = one_row("SELECT * FROM inventory_items WHERE item_id = %s", [item_id])
    if not item:
        messages.error(request, "Inventory item not found.")
        return redirect("/inventory")

    if request.method == "POST":
        try:
            qty_added = money(request.POST.get("quantity"))
            notes = (request.POST.get("notes") or "").strip()
            ref_no = (request.POST.get("reference_no") or "").strip() or None
            movement_date = (request.POST.get("movement_date") or today_text()).strip()

            if qty_added <= 0:
                messages.error(request, "Quantity to add must be greater than zero.")
            else:
                with transaction.atomic():
                    # Update quantity
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "UPDATE inventory_items SET quantity = quantity + %s, updated_at = %s WHERE item_id = %s",
                            [qty_added, now_text(), item_id]
                        )
                    # Insert movement
                    insert_record(
                        request,
                        "inventory_movements",
                        {
                            "item_id": item_id,
                            "movement_type": "Stock In",
                            "quantity": qty_added,
                            "movement_date": movement_date,
                            "reference_no": ref_no,
                            "notes": notes or f"Received {qty_added} units",
                            "recorded_by": legacy_user_id(request),
                            "created_at": now_text(),
                        }
                    )
                    audit_action(request, "Add Stock", f"Added {qty_added} units to inventory item {item['item_name']} (ID: {item_id})")
                messages.success(request, f"Added {qty_added} units to {item['item_name']}.")
                return redirect("/inventory")
        except Exception as exc:
            messages.error(request, f"Could not add stock: {exc}")

    fields = [
        {"name": "quantity", "label": "Quantity to Add", "type": "number", "required": True},
        {"name": "reference_no", "label": "Reference / Invoice No", "type": "text", "required": False},
        {"name": "movement_date", "label": "Received Date", "type": "date", "value": today_text(), "required": True},
        {"name": "notes", "label": "Notes / Source", "widget": "textarea", "required": False},
    ]

    return render(
        request,
        "school/form_page.html",
        {
            "title": f"Add Stock - {item['item_name']}",
            "subtitle": f"Current Quantity: {item['quantity']} {item.get('unit', 'units')}.",
            "fields": fields,
            "settings": school_settings(),
        }
    )

# Create your views here.
