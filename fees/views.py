from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render

from accounts.permissions import permission_required
from .services import (
    can_delete_receipts,
    can_edit_receipts,
    can_receive_payment,
    can_record_payments,
    create_allocations,
    dashboard_metrics,
    delete_payment_with_audit,
    ensure_current_term_bills_for_active_students,
    ensure_term_bill,
    ensure_finance_indexes,
    next_receipt_no as service_next_receipt_no,
    pupil_by_admission,
    pupil_by_identifier,

    receipt_context,
    save_payment,
    student_financial_summary,
    update_payment_with_audit,
)
from school_system_django.native import (
    audit_action,
    academic_grade_option,
    compact_class_label,
    delete_record,
    dict_rows,
    hydrate_class_labels,
    insert_record,
    legacy_user_id,
    now_text,
    one_row,
    render_detail_page,
    render_record_form_page,
    render_rows_page,
    render_table_page,
    school_settings,
    simple_pdf,
    today_text,
    update_record_fields,
)
from school_system_django.official_docs import (
    BORDER,
    GOLD,
    INK,
    LIGHT_BLUE,
    NAVY,
    amount_in_words,
    money_decimal,
    money_text,
    official_logo_path,
    published_date_time,
    qr_data_uri,
    qr_flowable,
    receipt_status,
    receipt_verify_url,
    school_contact_line,
    create_reportlab_stamp,
)


FEE_STRUCTURE_FIELDS = ["grade", "term", "year", "amount_required", "grade_id", "payment_deadline", "notes"]
PAYMENT_FIELDS = ["amount_paid", "payment_date", "payment_method", "term", "year", "reference_no"]


def find_receipt_context(receipt_no=None, payment_id=None, admission_no=None):
    context = receipt_context(receipt_no=receipt_no, payment_id=payment_id, admission_no=admission_no)
    if context is None and receipt_no and str(receipt_no).isdigit():
        context = receipt_context(payment_id=receipt_no)
    return context


def decorate_receipt_context(request, context):
    payment = context["payment"]
    summary = context["summary"] or {}
    settings = dict(context["settings"] or {})
    settings["school_motto"] = settings.get("school_motto") or "Knowledge - Discipline - Excellence"
    current_balance = money_decimal(summary.get("overall_balance"))
    amount_paid = money_decimal(payment.get("amount_paid"))
    previous_balance = current_balance + amount_paid
    receipt_no = payment.get("receipt_no") or ""
    issued_date, issued_time = published_date_time(payment.get("issued_date") or payment.get("payment_date") or now_text())
    cashier = "-"
    if payment.get("recorded_by"):
        user_row = one_row("SELECT full_name, username FROM users WHERE user_id = %s", [payment["recorded_by"]])
        if user_row:
            cashier = user_row.get("full_name") or user_row.get("username") or "-"
    if cashier == "-" and request and getattr(request, "user", None) and request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        cashier = getattr(profile, "full_name", None) or request.user.get_username()
    verify_url = receipt_verify_url(request, receipt_no)
    context.update(
        {
            "amount_words": amount_in_words(amount_paid),
            "cashier_name": cashier,
            "current_balance": current_balance,
            "previous_balance": previous_balance,
            "receipt_date": issued_date,
            "receipt_time": issued_time,
            "receipt_status": receipt_status(current_balance),
            "receipt_verify_url": verify_url,
            "receipt_qr_data_uri": qr_data_uri(verify_url),
            "school_contact_line": school_contact_line(settings),
            "settings": settings,
        }
    )
    return context


@permission_required("fees.manage")
def structure(request):
    try:
        ensure_current_term_bills_for_active_students()
    except Exception:
        pass
    return render_table_page(
        request,
        "Fees Structure",
        "fees_structure",
        ["fee_id", "grade", "term", "year", "amount_required", "payment_deadline", "notes"],
        "Term fees by Form.",
        order_by="year DESC, term DESC, grade",
        search_columns=["grade", "term", "notes"],
        pk_column="fee_id",
        create_href="/fees-structure/new",
        create_label="New Fee Structure",
        actions=[{"label": "Generate Term Bills", "href": "/fees-structure/generate-bills", "icon": "bi-receipt-cutoff"}],
        row_actions=[
            {"label": "View", "href": "/fees-structure/{fee_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/fees-structure/{fee_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/fees-structure/{fee_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this fee structure?"},
        ],
    )


@permission_required("fees.manage")
def generate_term_bills(request):
    settings = school_settings()
    if request.method != "POST":
        return render(
            request,
            "school/form_page.html",
            {
                "title": "Generate Term Bills",
                "subtitle": "Create term bills for active students using the matching fee structure.",
                "fields": [
                    {"name": "term", "label": "Term", "value": settings.get("current_term") or "Term 1"},
                    {"name": "year", "label": "Year", "type": "number", "value": settings.get("current_year") or today_text()[:4]},
                ],
            },
        )
    term = request.POST.get("term") or settings.get("current_term") or "Term 1"
    year = int(request.POST.get("year") or settings.get("current_year") or today_text()[:4])
    pupils = dict_rows("SELECT * FROM pupils WHERE COALESCE(status, 'Active') = 'Active'")
    created = 0
    missing_fee_structure = 0
    for pupil in pupils:
        before = one_row("SELECT bill_id FROM term_bills WHERE pupil_id = %s AND term = %s AND year = %s", [pupil["pupil_id"], term, year])
        bill = ensure_term_bill(pupil, term, year)
        if bill and not before:
            created += 1
        elif not bill and not before:
            missing_fee_structure += 1
    audit_action(request, "Generate term bills", f"{created} term bills generated for {term} {year}.")
    messages.success(request, f"{created} term bill(s) generated for {term} {year}.")
    if missing_fee_structure:
        messages.info(request, f"{missing_fee_structure} active student(s) were skipped because no matching fee structure exists.")
    return redirect("/fees-structure")


@permission_required("fees.view")
def payments(request):
    ensure_finance_indexes()
    q = (request.GET.get("q") or "").strip()
    grade = (request.GET.get("grade") or "").strip()
    term = (request.GET.get("term") or "").strip()
    year = (request.GET.get("year") or "").strip()
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
        clauses.append("(p.receipt_no LIKE %s OR pu.admission_no LIKE %s OR pu.first_name LIKE %s OR pu.surname LIKE %s OR pu.guardian_name LIKE %s)")
        params.extend([f"%{q}%"] * 5)
    if grade:
        clauses.append("pu.grade = %s")
        params.append(grade)
    if term:
        clauses.append("p.term = %s")
        params.append(term)
    if year:
        clauses.append("CAST(p.year AS TEXT) = %s")
        params.append(year)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    base_sql = f"""
        FROM payments p
        JOIN pupils pu ON pu.pupil_id = p.pupil_id
        {where}
    """
    count = one_row(f"SELECT COUNT(*) AS total {base_sql}", params)
    total = int(count["total"] or 0) if count else 0
    rows = dict_rows(
        f"""
        SELECT p.receipt_no,
               pu.admission_no,
               pu.first_name || ' ' || pu.surname AS student_name,
               pu.grade,
               pu.class_stream,
               p.amount_paid,
               p.payment_date,
               p.payment_method,
               p.term,
               p.year,
               p.reference_no
        {base_sql}
        ORDER BY p.payment_date DESC, p.payment_id DESC
        LIMIT %s OFFSET %s
        """,
        params + [per_page, (page - 1) * per_page],
    )
    row_actions = [
        {"label": "Receipt", "href": "/receipt/{receipt_no}", "icon": "bi-receipt", "class": "btn-outline-primary"},
        {"label": "PDF", "href": "/receipt/{receipt_no}/pdf", "icon": "bi-file-earmark-pdf", "class": "btn-outline-info"},
    ]
    if can_edit_receipts(request.user):
        row_actions.append({"label": "Edit", "href": "/payments/{receipt_no}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"})
    if can_delete_receipts(request.user):
        row_actions.append({"label": "Delete", "href": "/payments/{receipt_no}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this receipt? This is audited."})
    filters = [
        {"name": "grade", "label": "Class", "value": grade, "options": [academic_grade_option(row["grade"]) for row in dict_rows("SELECT DISTINCT grade FROM pupils WHERE grade IS NOT NULL AND TRIM(grade) != '' ORDER BY grade")]},
        {"name": "term", "label": "Term", "value": term, "options": [row["term"] for row in dict_rows("SELECT DISTINCT term FROM payments ORDER BY term")]},
        {"name": "year", "label": "Year", "value": year, "options": [row["year"] for row in dict_rows("SELECT DISTINCT year FROM payments ORDER BY year DESC")]},
    ]
    return render_rows_page(
        request,
        "Fee Payments",
        rows,
        ["receipt_no", "admission_no", "student_name", "class_label", "amount_paid", "payment_date", "payment_method", "term", "year", "reference_no"],
        "Receipts, payment history, and allocations.",
        actions=[{"label": "Record Payment", "href": "/payments/new", "icon": "bi-plus-circle"}],
        row_actions=row_actions,
        total=total,
        page=page,
        per_page=per_page,
        filters=filters,
    )


def posted_admission_number(request):
    admission_no = (request.POST.get("admission_no") or "").strip()
    if admission_no:
        return admission_no
    query = (request.POST.get("pupil_query") or "").strip()
    if query and any(character.isdigit() for character in query):
        return query
    return ""


@permission_required("payments.record")
def record_payment(request):
    if not can_record_payments(request.user):
        messages.error(request, "Your account is not allowed to record fees payments.")
        return redirect("/dashboard")
    settings = school_settings()
    if request.method == "POST":
        # Student selection robustness.
        # Goal: require a correct selection.
        admission_no = (request.POST.get("admission_no") or "").strip().upper()
        pupil_query = (request.POST.get("pupil_query") or "").strip()

        pupil = pupil_by_admission(admission_no) if admission_no else None
        identifier = admission_no if pupil else None
        if not pupil and pupil_query:
            # Picker posts the selected *name* into `pupil_query`.
            # Sometimes users paste text like "Brian Banda"; in that case
            # we should *still* try to resolve by admission/name.
            query = pupil_query.strip()

            # If the pasted text looks like an admission number, prefer admission.
            looks_like_admission = (
                any(ch.isdigit() for ch in query)
                or query.upper().startswith("ADM")
                or query.upper().startswith("A")
            )

            identifier = query if looks_like_admission else query

            pupil = pupil_by_identifier(identifier) if identifier else None


        # Hard fail: this workflow requires a valid selection.
        if not pupil:
            typed = identifier or ""
            messages.error(
                request,
                f"Student was not found for '{typed}'. Enter a valid admission number (e.g. A26001) or ensure the selected student is correct.",
            )
            return redirect("/payments/new")
        if not can_receive_payment(pupil):
            messages.error(request, f"Cannot record payment for archived student {pupil.get('admission_no')} because status is {pupil.get('status') or 'Active'}.")
            return redirect(f"/pupils/{pupil['admission_no']}")

        term = request.POST.get("term") or settings.get("current_term") or "Term 1"
        year = request.POST.get("year") or settings.get("current_year") or today_text()[:4]
        try:
            payment_method = (request.POST.get("payment_method") or "").strip()
            reference_no = (request.POST.get("reference_no") or "").strip() or None

            # If paying via Bank Transfer / Mobile Money / Cheque, require reference number.
            # Also prevent reusing the same reference number.
            requires_reference = payment_method in {"Bank Transfer", "Mobile Money", "Cheque"}
            if requires_reference and not reference_no:
                messages.error(request, f"Reference number is required for {payment_method} payments.")
                return redirect("/payments/new")

            if reference_no:
                from django.db import connection

                exists = one_row(
                    "SELECT payment_id FROM payments WHERE reference_no = %s",
                    [reference_no],
                )
                if exists:
                    messages.error(request, f"Reference {reference_no} has already been used. Please enter a new reference.")
                    return redirect("/payments/new")

            payment_id, receipt_no, _allocations, credit = save_payment(
                request,
                pupil,
                request.POST.get("amount_paid") or "0",
                request.POST.get("payment_date") or today_text(),
                payment_method or "Cash",
                term,
                int(year),
                reference_no,
            )

            # Connect to GL ERP to post balanced G/L journal entries automatically!
            try:
                from student_registry.models import Student
                from fees_management.models import StudentFeeAccount
                from fees_management.services import record_payment as erp_record_payment
                from decimal import Decimal
                import datetime

                from academic_structure.models import AcademicClass, AcademicTerm
                
                aclass_obj = None
                if pupil.get("class_id"):
                    aclass_obj = AcademicClass.objects.filter(pk=pupil["class_id"]).first()

                # Fetch or create student registry record
                student_obj, _ = Student.objects.get_or_create(
                    admission_no=pupil["admission_no"],
                    defaults={
                        "first_name": pupil.get("first_name", "Student"),
                        "surname": pupil.get("surname", "Record"),
                        "gender": pupil.get("gender", "Male"),
                        "date_of_birth": datetime.date(2010, 1, 1),
                        "admission_date": datetime.date(2026, 1, 1),
                        "academic_class": aclass_obj,
                        "status": "Active Student"
                    }
                )

                # Resolve active term and year for defaults
                year_obj = aclass_obj.academic_year if aclass_obj else None
                term_obj = None
                if year_obj:
                    term_obj = AcademicTerm.objects.filter(academic_year=year_obj, is_active=True).first() or AcademicTerm.objects.filter(academic_year=year_obj).first()

                fee_acct, _ = StudentFeeAccount.objects.get_or_create(
                    student=student_obj,
                    defaults={
                        "academic_year": year_obj,
                        "academic_term": term_obj,
                        "total_charges": Decimal("0.00"),
                        "amount_paid": Decimal("0.00"),
                        "arrears": Decimal("0.00")
                    }
                )
                
                # Check for ZiG payments
                pmt_currency = "USD"
                if "ZIG" in (payment_method or "").upper():
                    pmt_currency = "ZiG"

                erp_record_payment(
                    student_account=fee_acct,
                    amount=Decimal(request.POST.get("amount_paid") or "0"),
                    currency=pmt_currency,
                    payment_method=payment_method or "CASH",
                    cashier=request.user
                )
            except Exception as erp_err:
                print(f"GL ERP Posting warning: {erp_err}")

            if credit > 0:
                messages.success(request, f"Payment saved. Receipt {receipt_no} generated. Credit balance USD {credit}.")
            else:
                messages.success(request, f"Payment saved. Receipt {receipt_no} generated.")
            return redirect(f"/receipt/{receipt_no}")
        except Exception as exc:
            messages.error(request, f"Could not save payment: {exc}")
    return render(
        request,
        "fees/payment_form.html",
        {
            "title": "Record Payment",
            "settings": settings,
            "payment_methods": ["Cash", "Bank Transfer", "Mobile Money", "Card", "Cheque"],
            "today": today_text(),
            "current_year": settings.get("current_year") or today_text()[:4],
            "initial_admission_no": (request.GET.get("admission_no") or "").strip().upper(),
        },
    )


@permission_required("fees.manage")
def portal_requests(request):
    from accounts.permissions import normalized_role, ROLE_BURSAR
    role = normalized_role(request.user)
    row_actions = []
    if role == ROLE_BURSAR:
        row_actions = [
            {"label": "Approve", "href": "/portal-payment-requests/{request_id}/approve", "icon": "bi-check-circle", "class": "btn-outline-success", "method": "post", "confirm": "Approve this portal payment?"},
            {"label": "Reject", "href": "/portal-payment-requests/{request_id}/reject", "icon": "bi-x-circle", "class": "btn-outline-danger", "method": "post", "confirm": "Reject this portal payment?"},
        ]
    return render_table_page(
        request,
        "Portal Payment Requests",
        "online_payment_requests",
        ["request_id", "pupil_id", "reference_no", "amount", "method", "term", "year", "status"],
        "Student portal payment requests and bank reference approvals.",
        order_by="created_at DESC",
        search_columns=["reference_no", "method", "status"],
        pk_column="request_id",
        row_actions=row_actions,
    )


def next_receipt_no():
    return service_next_receipt_no()


@permission_required("fees.view")
def structure_detail(request, fee_id):
    return render_detail_page(request, "Fee Structure", "fees_structure", "fee_id", fee_id)


@permission_required("fees.manage")
def structure_new(request):
    return render_record_form_page(request, "New Fee Structure", "fees_structure", FEE_STRUCTURE_FIELDS, redirect_to="/fees-structure")


@permission_required("fees.manage")
def structure_edit(request, fee_id):
    return render_record_form_page(request, "Edit Fee Structure", "fees_structure", FEE_STRUCTURE_FIELDS, pk_column="fee_id", pk_value=fee_id, redirect_to=f"/fees-structure/{fee_id}")


@permission_required("fees.manage")
def structure_delete(request, fee_id):
    return delete_record(request, "Fee Structure", "fees_structure", "fee_id", fee_id, "/fees-structure")


@permission_required("fees.view")
def payment_detail(request, payment_id):
    context = find_receipt_context(payment_id=payment_id)
    if not context:
        messages.error(request, "Payment was not found.")
        return redirect("/payments")
    return redirect(f"/receipt/{context['payment']['receipt_no']}")


@permission_required("receipts.edit")
def payment_edit(request, payment_id=None, receipt_no=None):
    if not can_edit_receipts(request.user):
        messages.error(request, "Only Admin or Super Admin can edit receipts.")
        return redirect("/payments")
    context = find_receipt_context(receipt_no=receipt_no, payment_id=payment_id)
    if not context:
        messages.error(request, "Receipt was not found.")
        return redirect("/payments")
    payment = context["payment"]
    if request.method == "POST":
        reason = (request.POST.get("edit_reason") or "").strip()
        data = {
            "amount_paid": request.POST.get("amount_paid"),
            "payment_date": request.POST.get("payment_date"),
            "payment_method": request.POST.get("payment_method"),
            "term": request.POST.get("term"),
            "year": request.POST.get("year"),
            "reference_no": request.POST.get("reference_no") or None,
        }
        try:
            update_payment_with_audit(request, payment["payment_id"], data, reason)
            messages.success(request, "Receipt updated and audit log saved.")
            return redirect(f"/receipt/{payment['receipt_no']}")
        except Exception as exc:
            messages.error(request, f"Could not edit receipt: {exc}")
    return render(request, "fees/payment_edit.html", context)


@permission_required("receipts.delete")
def payment_delete(request, payment_id=None, receipt_no=None):
    if not can_delete_receipts(request.user):
        messages.error(request, "Only Super Admin can delete receipts.")
        return redirect("/payments")
    context = find_receipt_context(receipt_no=receipt_no, payment_id=payment_id)
    if not context:
        messages.error(request, "Receipt was not found.")
        return redirect("/payments")
    payment = context["payment"]
    if request.method == "POST":
        try:
            delete_payment_with_audit(request, payment["payment_id"], request.POST.get("delete_reason") or "Super Admin deletion")
            messages.success(request, "Receipt deleted and audit log saved.")
            return redirect("/payments")
        except Exception as exc:
            messages.error(request, f"Could not delete receipt: {exc}")
            return redirect("/payments")
    row = {
        "receipt_no": payment.get("receipt_no"),
        "admission_no": payment.get("admission_no"),
        "student_name": f"{payment.get('first_name')} {payment.get('surname')}",
        "amount_paid": payment.get("amount_paid"),
        "payment_date": payment.get("payment_date"),
    }
    return render(
        request,
        "school/detail_page.html",
        {
            "title": "Delete Receipt",
            "row": row,
            "delete_confirm": True,
            "actions": [{"label": "Cancel", "href": f"/receipt/{payment['receipt_no']}", "icon": "bi-x-circle"}],
        },
    )


def receipt_pdf_response(context, request=None):
    from io import BytesIO
    from xml.sax.saxutils import escape

    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    context = decorate_receipt_context(request, context)
    payment = context["payment"]
    pupil = context["pupil"]
    settings = context["settings"]
    allocations = context["allocations"]
    previous_balance = context["previous_balance"]
    current_balance = context["current_balance"]
    status_color = "#b91c1c" if current_balance > 0 else "#16803a"

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=6 * mm,
        leftMargin=6 * mm,
        topMargin=6 * mm,
        bottomMargin=6 * mm,
    )
    styles = getSampleStyleSheet()
    navy = colors.HexColor(NAVY)
    gold = colors.HexColor(GOLD)
    border = colors.HexColor(BORDER)
    light = colors.HexColor(LIGHT_BLUE)
    ink = colors.HexColor(INK)

    title_style = ParagraphStyle("DocTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=navy)
    motto_style = ParagraphStyle("Motto", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=gold, alignment=1)
    small_style = ParagraphStyle("Small", parent=styles["Normal"], fontSize=7, leading=8.5, textColor=ink)
    label_style = ParagraphStyle("Label", parent=small_style, fontName="Helvetica-Bold", textColor=ink)
    value_style = ParagraphStyle("Value", parent=small_style, fontName="Helvetica", textColor=ink)
    white_style = ParagraphStyle("WhiteHeader", parent=small_style, fontName="Helvetica-Bold", textColor=colors.white)
    center_style = ParagraphStyle("Center", parent=value_style, alignment=1)
    right_style = ParagraphStyle("Right", parent=value_style, alignment=2)

    def p(value, style=value_style):
        return Paragraph(escape(str(value if value is not None else "-")), style)

    def html(value, style=value_style):
        return Paragraph(value, style)

    logo_path = official_logo_path(settings)
    logo = Image(logo_path, width=24 * mm, height=24 * mm) if logo_path else p("")
    school_name = (settings.get("school_name") or "RAYDON HIGH SCHOOL").upper()
    school_block = [
        p(school_name, title_style),
        Paragraph(escape(settings.get("school_motto") or "Knowledge • Discipline • Excellence"), motto_style),
        Spacer(1, 2),
        p(settings.get("school_address") or "School Address", small_style),
        p(school_contact_line(settings), small_style),
    ]

    receipt_meta = [
        [html("<b>OFFICIAL RECEIPT</b>", white_style), ""],
        [p("Receipt No:", label_style), html(f"<font color=\"#b91c1c\"><b>{escape(str(payment.get('receipt_no') or '-'))}</b></font>", value_style)],
        [p("Date:", label_style), p(context["receipt_date"])],
        [p("Time:", label_style), p(context["receipt_time"])],
        [p("Academic Year:", label_style), p(payment.get("year") or "-")],
        [p("Term:", label_style), p(payment.get("term") or "-")],
        [p("Payment Method:", label_style), p(payment.get("payment_method") or "-")],
        [p("Cashier:", label_style), p(context["cashier_name"])],
    ]
    receipt_box = Table(receipt_meta, colWidths=[23 * mm, 31 * mm])
    receipt_box.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.8, navy),
        ("INNERGRID", (0, 1), (-1, -1), 0.2, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]))

    header = Table([[logo, school_block, receipt_box]], colWidths=[30 * mm, 110 * mm, 58 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    section_style = TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, navy),
        ("INNERGRID", (0, 1), (-1, -1), 0.25, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])

    class_label = compact_class_label(grade=pupil.get("grade"), stream=pupil.get("class_stream"), grade_id=pupil.get("grade_id")) or "-"
    student_data = [
        [html("<b>STUDENT INFORMATION</b>", white_style), "", "", ""],
        [p("Admission No:", label_style), p(pupil.get("admission_no") or "-"), p("Stream:", label_style), p(pupil.get("stream") or "Ordinary Level")],
        [p("Student Name:", label_style), p(f"{pupil.get('first_name') or ''} {pupil.get('surname') or ''}".strip()), p("Parent / Guardian:", label_style), p(pupil.get("guardian_name") or "-")],
        [p("Class:", label_style), p(class_label), p("Contact:", label_style), p(pupil.get("guardian_phone") or "-")],
    ]
    student_table = Table(student_data, colWidths=[28 * mm, 68 * mm, 33 * mm, 69 * mm])
    student_table.setStyle(section_style)

    payment_rows = [
        [html("<b>PAYMENT DETAILS</b>", white_style), ""],
        [html("<b>DESCRIPTION</b>", white_style), html("<b>AMOUNT (USD)</b>", white_style)],
    ]
    if allocations:
        for allocation in allocations:
            payment_rows.append([
                p(f"Fees Allocation - {allocation.get('term')} {allocation.get('year')}"),
                p(money_text(allocation.get("amount_allocated")), right_style),
            ])
    else:
        payment_rows.append([p(f"Fees Payment - {payment.get('term')} {payment.get('year')}"), p(money_text(payment.get("amount_paid")), right_style)])
    payment_rows.extend([
        [html("<b>SUBTOTAL</b>", label_style), html(f"<b>{money_text(payment.get('amount_paid'))}</b>", right_style)],
        [p("Discount", value_style), p("USD 0.00", right_style)],
        [html("<b>TOTAL AMOUNT DUE</b>", label_style), html(f"<b>{money_text(payment.get('amount_paid'))}</b>", right_style)],
        [html("<b>AMOUNT PAID</b>", label_style), html(f"<b>{money_text(payment.get('amount_paid'))}</b>", right_style)],
        [html("<b>BALANCE REMAINING</b>", label_style), html(f"<b>{money_text(current_balance)}</b>", right_style)],
    ])
    payment_table = Table(payment_rows, colWidths=[92 * mm, 36 * mm])
    payment_style = TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 1), navy),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.6, navy),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, -5), (-1, -3), colors.HexColor("#fff5df")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eaf8ef") if current_balance <= 0 else colors.HexColor("#ffecec")),
    ])
    payment_table.setStyle(payment_style)

    summary_data = [
        [html("<b>ACCOUNT SUMMARY</b>", label_style), ""],
        [p("Previous Balance:", label_style), p(money_text(previous_balance), right_style)],
        [p("Amount Paid:", label_style), p(money_text(payment.get("amount_paid")), right_style)],
        [p("Current Balance:", label_style), html(f"<b>{money_text(current_balance)}</b>", right_style)],
        [html("<b>AMOUNT IN WORDS</b>", label_style), ""],
        [p(context["amount_words"], value_style), ""],
        [html("<b>PAYMENT STATUS</b>", label_style), ""],
        [html(f"<font size=\"14\" color=\"{status_color}\"><b>{escape(context['receipt_status'])}</b></font>", center_style), ""],
    ]
    summary_table = Table(summary_data, colWidths=[38 * mm, 31 * mm])
    summary_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("SPAN", (0, 4), (-1, 4)),
        ("SPAN", (0, 5), (-1, 5)),
        ("SPAN", (0, 6), (-1, 6)),
        ("SPAN", (0, 7), (-1, 7)),
        ("BACKGROUND", (0, 0), (-1, 0), light),
        ("BACKGROUND", (0, 4), (-1, 4), light),
        ("BACKGROUND", (0, 6), (-1, 6), light),
        ("BOX", (0, 0), (-1, -1), 0.6, border),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    payment_summary = Table([[payment_table, summary_table]], colWidths=[129 * mm, 69 * mm])
    payment_summary.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    qr = qr_flowable(context["receipt_verify_url"], size_mm=22)
    stamp_drawing = create_reportlab_stamp(
        school_name=school_name,
        date_str=context["receipt_date"],
        time_str=context["receipt_time"],
        term_str=payment.get("term") or "TERM",
        year_str=str(payment.get("year") or ""),
        status_str="PAYMENT VERIFIED",
        stamp_color=NAVY
    )
    stamp_cell = [
        html("<b>ELECTRONIC SCHOOL STAMP</b>", center_style),
        Spacer(1, 2),
        stamp_drawing,
    ]
    verify_cell = [html("<b>VERIFY RECEIPT</b>", center_style), Spacer(1, 2)]
    if qr:
        verify_cell.append(qr)
    verify_cell.extend([
        p("Scan to verify authenticity", center_style),
        html(f"<b>Verification ID:</b><br/>{escape(str(payment.get('receipt_no') or '-'))}", center_style),
    ])
    instruction_cell = [
        html("<b>VERIFICATION INSTRUCTIONS</b>", label_style),
        Spacer(1, 4),
        p("Scan the QR code or open the verification link to verify this receipt."),
        Spacer(1, 3),
        p("This receipt is computer generated and does not require a manual signature."),
    ]
    verify_table = Table([[stamp_cell, verify_cell, instruction_cell]], colWidths=[56 * mm, 56 * mm, 86 * mm])
    verify_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, border),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (1, 0), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    approvals = Table([
        [html("<b>RECEIVED BY</b>", label_style), html("<b>APPROVED BY</b>", label_style)],
        [p(f"Name: {context['cashier_name']}"), p("Name: Accounts Officer")],
        [p("Signature: __________________________"), p("Signature: __________________________")],
        [p(f"Date: {context['receipt_date']}"), p(f"Date: {context['receipt_date']}")],
    ], colWidths=[99 * mm, 99 * mm])
    approvals.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, border),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))

    footer = Table([[html("<b>THIS IS A COMPUTER GENERATED RECEIPT. ANY ALTERATION OR TAMPERING IS ILLEGAL.</b><br/><font color=\"#f7c948\"><b>Thank you for your payment.</b></font>", center_style)]], colWidths=[198 * mm])
    footer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), navy),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, navy),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story = [header, Spacer(1, 4), student_table, Spacer(1, 5), payment_summary, Spacer(1, 5), verify_table, Spacer(1, 5), approvals, Spacer(1, 5), footer]
    document.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="receipt-{payment.get("receipt_no")}.pdf"'
    return response


@permission_required("fees.view")
def receipt(request, payment_id=None, receipt_no=None, admission_no=None):
    context = find_receipt_context(receipt_no=receipt_no, payment_id=payment_id, admission_no=admission_no)
    if not context:
        messages.error(request, "Receipt or student was not found.")
        return redirect("/payments")
    context = decorate_receipt_context(request, context)
    payment = context["payment"]

    # PDF/print handling
    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        return receipt_pdf_response(context, request=request)

    if request.GET.get("print") == "1":
        return render(request, "fees/receipt_print.html", context)

    context["can_edit_receipt"] = can_edit_receipts(request.user)
    context["can_delete_receipt"] = can_delete_receipts(request.user)
    return render(request, "fees/receipt.html", context)


@permission_required("fees.manage")
def portal_request_action(request, request_id, action):
    from accounts.permissions import normalized_role, ROLE_BURSAR
    if normalized_role(request.user) != ROLE_BURSAR:
        messages.error(request, "Only the Bursar has the right to approve or reject portal payments.")
        return redirect("/portal-payment-requests")
    if request.method != "POST":
        messages.error(request, "Portal payment requests must be approved or rejected from the action button.")
        return redirect("/portal-payment-requests")
    if action not in {"approve", "reject"}:
        messages.error(request, "Unknown portal payment action.")
        return redirect("/portal-payment-requests")
    request_row = one_row("SELECT * FROM online_payment_requests WHERE request_id = %s", [request_id])
    if not request_row:
        messages.error(request, "Portal payment request was not found.")
        return redirect("/portal-payment-requests")
    if action == "reject":
        return update_record_fields(
            request,
            "online_payment_requests",
            "request_id",
            request_id,
            {"status": "Rejected", "updated_at": now_text()},
            "Portal payment request rejected.",
            "/portal-payment-requests",
        )
    if request_row.get("status") == "Approved" and request_row.get("payment_id"):
        messages.info(request, "This portal payment request is already approved.")
        return redirect("/portal-payment-requests")
    reference_no = request_row.get("reference_no") or request_row.get("bank_reference_no")
    if reference_no:
        duplicate = one_row(
            "SELECT payment_id, receipt_no FROM payments WHERE reference_no = %s",
            [reference_no],
        )
        if duplicate:
            messages.error(request, f"Reference {reference_no} is already linked to receipt {duplicate['receipt_no']}.")
            return redirect("/portal-payment-requests")
    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [request_row.get("pupil_id")])
    if not pupil:
        messages.error(request, "The student linked to this request was not found.")
        return redirect("/portal-payment-requests")
    if not can_receive_payment(pupil):
        messages.error(request, f"Cannot approve payment for archived student {pupil.get('admission_no')} because status is {pupil.get('status') or 'Active'}.")
        return redirect("/portal-payment-requests")
    try:
        payment_id, receipt_no, _allocations, _credit = save_payment(
            request,
            pupil,
            request_row.get("amount"),
            today_text(),
            request_row.get("method") or "Bank Transfer",
            request_row.get("term") or (school_settings().get("current_term") or "Term 1"),
            int(request_row.get("year") or school_settings().get("current_year") or today_text()[:4]),
            reference_no,
        )
        update_record_fields(
            request,
            "online_payment_requests",
            "request_id",
            request_id,
            {"status": "Approved", "payment_id": payment_id, "updated_at": now_text()},
            f"Portal payment approved and receipt {receipt_no} generated.",
            "/portal-payment-requests",
        )
        audit_action(request, "Approve portal payment", f"Request {request_id} approved as receipt {receipt_no}.")
    except Exception as exc:
        messages.error(request, f"Could not approve portal payment: {exc}")
    return redirect("/portal-payment-requests")


@permission_required("payments.record")
def pupil_search(request):
    q = (request.GET.get("q") or request.GET.get("term") or "").strip()
    if len(q) < 1:
        return JsonResponse({"items": [], "results": []})
    pupils = dict_rows(
        """
        SELECT admission_no, first_name, surname, grade, class_stream, grade_id, class_id, guardian_name, guardian_phone, status
        FROM pupils
        WHERE COALESCE(status, 'Active') = 'Active'
          AND (
               admission_no LIKE %s
            OR first_name LIKE %s
            OR surname LIKE %s
            OR grade LIKE %s
            OR class_stream LIKE %s
            OR guardian_name LIKE %s
          )
        ORDER BY surname, first_name
        LIMIT 20
        """,
        [f"%{q}%"] * 6,
    )
    pupils = hydrate_class_labels(pupils)
    items = [
        {
            **row,
            "name": f"{row.get('first_name', '')} {row.get('surname', '')}".strip(),
            "label": f"{row.get('admission_no')} - {row.get('first_name', '')} {row.get('surname', '')}",
        }
        for row in pupils
    ]
    return JsonResponse({"items": items, "results": items})


@permission_required("fees.view")
def pupil_balance(request):
    admission_no = request.GET.get("admission_no")
    term = request.GET.get("term") or None
    year = request.GET.get("year") or None
    summary = student_financial_summary(admission_no=admission_no, term=term, year=year, ensure_bill=True)
    if not summary:
        return JsonResponse({"error": "Student not found"}, status=404)
    return JsonResponse(summary)


@permission_required("fees.view")
def portal_request_detail(request, request_id):
    return render_detail_page(request, "Portal Payment Request", "online_payment_requests", "request_id", request_id)


@permission_required("fees.manage")
def portal_request_edit(request, request_id):
    fields = ["pupil_id", "reference_no", "amount", "method", "term", "year", "status", "phone_number", "bank_reference_no"]
    return render_record_form_page(
        request,
        "Edit Portal Payment Request",
        "online_payment_requests",
        fields,
        pk_column="request_id",
        pk_value=request_id,
        redirect_to="/portal-payment-requests"
    )


@permission_required("fees.manage")
def portal_request_delete(request, request_id):
    return delete_record(request, "Portal Payment Request", "online_payment_requests", "request_id", request_id, "/portal-payment-requests")


# Create your views here.
