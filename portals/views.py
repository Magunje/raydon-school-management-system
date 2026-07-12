import time
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.portal_access import clear_portal_session_state, safe_next_url
from accounts.permissions import permission_required
from fees.services import receipt_context, statement_payment_rows, student_financial_summary
from reports.views import statement_excel, statement_number, statement_pdf_response
from school_system_django.native import audit_action, insert_record, now_text, render_table_page, school_settings, today_text
from portals.services import (
    LOGIN_MAX_ATTEMPTS,
    attendance_history,
    attendance_summary,
    clear_student_session,
    current_student,
    dashboard_context,
    decimal_json,
    e_learning_context,
    json_dumps,
    pending_payment_requests,
    portal_assignment_for_student,
    portal_payments,
    profile_sections,
    published_results,
    row_if_tables,
    rows_if_tables,
    set_student_session,
    student_lookup_for_login,
    student_status_is_active,
    tenant_submission_path,
    textbook_rows,
    timetable_context,
    overdue_textbook_count,
)


LOGIN_LOCK_SECONDS = 15 * 60


def _login_lock_remaining(request):
    locked_until = int(request.session.get("student_login_locked_until") or 0)
    remaining = locked_until - int(time.time())
    if remaining <= 0:
        request.session.pop("student_login_locked_until", None)
        if locked_until:
            request.session["student_login_attempts"] = 0
        return 0
    return remaining


def _record_login_failure(request):
    attempts = int(request.session.get("student_login_attempts") or 0) + 1
    request.session["student_login_attempts"] = attempts
    if attempts >= LOGIN_MAX_ATTEMPTS:
        request.session["student_login_locked_until"] = int(time.time()) + LOGIN_LOCK_SECONDS


def _record_login_success(request):
    request.session.pop("student_login_attempts", None)
    request.session.pop("student_login_locked_until", None)


def student_portal_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        pupil = current_student(request)
        if pupil is None:
            return redirect("student_portal:login")
        return view_func(request, pupil, *args, **kwargs)

    return wrapped


def student_portal_api_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        pupil = current_student(request)
        if pupil is None:
            return JsonResponse({"ok": False, "error": "authentication_required"}, status=401)
        return view_func(request, pupil, *args, **kwargs)

    return wrapped


@permission_required("dashboard.view")
def staff(request):
    return render_table_page(
        request,
        "Staff Portal",
        "teacher_profiles",
        ["profile_id", "user_id", "phone_number", "email", "qualifications", "assigned_subjects"],
        "Assigned classes, subjects, attendance, marks, timetable, and payslips.",
        order_by="profile_id DESC",
    )


def student_login(request):
    if current_student(request):
        return redirect("student_portal:dashboard")

    if request.user.is_authenticated:
        clear_portal_session_state(request)

    if request.method == "POST":
        remaining = _login_lock_remaining(request)
        if remaining:
            messages.error(request, f"Too many failed attempts. Try again in {max(1, remaining // 60)} minute(s).")
            return render(request, "student_portal/login.html", {"settings": school_settings()})

        identifier = (request.POST.get("admission_no") or "").strip()
        date_of_birth = (request.POST.get("date_of_birth") or "").strip()
        pupil = student_lookup_for_login(identifier)
        if pupil and student_status_is_active(pupil) and str(pupil.get("date_of_birth") or "") == date_of_birth:
            set_student_session(request, pupil)
            _record_login_success(request)
            request.session["active_portal"] = "student_portal"
            audit_action(request, "Student portal login", f"{pupil['admission_no']} signed in")
            messages.success(request, "Student portal login successful.")
            next_url = safe_next_url(request, request.GET.get("next"), "/student-portal/", reverse("student_portal:dashboard"))
            return redirect(next_url)

        _record_login_failure(request)
        if pupil and not student_status_is_active(pupil):
            messages.error(request, "This student portal account is not active. Contact the school office.")
        else:
            messages.error(request, "Invalid admission number or date of birth.")
        audit_action(request, "Failed student portal login", f"Identifier {identifier} failed at {request.path}")

    response = render(request, "student_portal/login.html", {"settings": school_settings()})
    response["Cache-Control"] = "no-store"
    return response


def student_logout(request):
    clear_student_session(request)
    clear_portal_session_state(request)
    messages.success(request, "Signed out of the student portal.")
    return redirect("student_portal:login")


@student_portal_required
def student(request, pupil):
    context = dashboard_context(pupil)
    return render(request, "portals/student_dashboard.html", context)


@student_portal_required
def student_profile(request, pupil):
    return render(
        request,
        "portals/student_profile.html",
        {
            "pupil": pupil,
            "sections": profile_sections(pupil),
            "settings": school_settings(),
        },
    )


@student_portal_required
def student_attendance(request, pupil):
    rows = attendance_history(pupil["pupil_id"])
    summary = attendance_summary(pupil["pupil_id"])
    return render(
        request,
        "portals/student_attendance.html",
        {
            "title": "Attendance",
            "pupil": pupil,
            "rows": rows,
            "summary": summary,
            "history_json": json_dumps(rows[:45]),
            "settings": school_settings(),
        },
    )


def _results_restriction(pupil):
    summary = student_financial_summary(pupil=pupil)
    overdue = overdue_textbook_count(pupil["pupil_id"])
    amount_due = float((summary or {}).get("amount_due") or 0)
    if amount_due > 0:
        return "Fees balance", summary
    if overdue:
        return "Overdue textbooks", summary
    return "", summary


@student_portal_required
def student_results(request, pupil):
    restriction, summary = _results_restriction(pupil)
    if restriction:
        messages.error(request, f"Results are restricted: {restriction}.")
        return render(
            request,
            "portals/student_results.html",
            {
                "pupil": pupil,
                "rows": [],
                "restricted_reason": restriction,
                "summary": summary,
                "trend_json": "[]",
                "latest_entries_json": "[]",
                "settings": school_settings(),
            },
        )

    if request.GET.get("result_id"):
        from exams.views import result_slip_pdf_response

        result_id = request.GET.get("result_id")
        result = row_if_tables(
            ["result_sheets"],
            "SELECT * FROM result_sheets WHERE result_id = %s AND pupil_id = %s AND status = 'Published'",
            [result_id, pupil["pupil_id"]],
        )
        if result:
            entries = rows_if_tables(
                ["result_entries"],
                """
                SELECT s.subject_name, s.subject_code, s.display_order, e.mark, e.grade, e.subject_id, e.subject_comment
                FROM result_entries e
                LEFT JOIN subjects s ON s.subject_id = e.subject_id
                WHERE e.result_id = %s
                ORDER BY s.display_order, s.subject_name
                """,
                [result_id],
            )
            return result_slip_pdf_response(result, pupil, entries, request)
        messages.error(request, "Result slip not found or not published.")
        return redirect("student_portal:results")

    rows = published_results(pupil["pupil_id"])
    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        return _student_results_summary_pdf(pupil, rows)

    latest_entries = []
    if rows:
        latest_entries = rows_if_tables(
            ["result_entries"],
            """
            SELECT s.subject_name, e.mark, e.grade, e.subject_comment
            FROM result_entries e
            LEFT JOIN subjects s ON s.subject_id = e.subject_id
            WHERE e.result_id = %s
            ORDER BY s.display_order, s.subject_name
            """,
            [rows[0]["result_id"]],
        )
    trend_data = list(rows)
    trend_data.reverse()
    return render(
        request,
        "portals/student_results.html",
        {
            "pupil": pupil,
            "rows": rows,
            "trend": trend_data,
            "latest_entries": latest_entries,
            "trend_json": json_dumps(trend_data),
            "latest_entries_json": json_dumps(latest_entries),
            "settings": school_settings(),
        },
    )


def _student_results_summary_pdf(pupil, rows):
    from io import BytesIO

    from django.http import HttpResponse
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    from portals.services import class_label
    from school_system_django.native import get_pdf_header

    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle("Label", fontName="Helvetica-Bold", fontSize=9, textColor=colors.HexColor("#486581"))
    val_style = ParagraphStyle("Value", fontName="Helvetica", fontSize=9, textColor=colors.HexColor("#102a43"))
    title_style = ParagraphStyle("PortalResultsTitle", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=18, textColor=colors.HexColor("#102a43"), alignment=1, spaceAfter=15)

    story = [get_pdf_header(school_settings(), 180 * mm), Paragraph(f"Academic Record - {pupil['first_name']} {pupil['surname']}", title_style)]
    meta = [[
        Paragraph("Admission No", label_style),
        Paragraph(pupil["admission_no"], val_style),
        Paragraph("Class / Stream", label_style),
        Paragraph(class_label(pupil) or "-", val_style),
    ]]
    meta_table = Table(meta, colWidths=[35 * mm, 50 * mm, 35 * mm, 50 * mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f4f8")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.extend([meta_table, Spacer(1, 15)])

    table_data = [[
        Paragraph("Term", label_style),
        Paragraph("Year", label_style),
        Paragraph("Average Mark", label_style),
        Paragraph("Total Marks", label_style),
        Paragraph("Class Position", label_style),
        Paragraph("Grade Position", label_style),
    ]]
    for row in rows:
        table_data.append([
            Paragraph(str(row.get("term") or "-"), val_style),
            Paragraph(str(row.get("year") or "-"), val_style),
            Paragraph(f"{float(row.get('average_mark') or 0):.2f}%", val_style),
            Paragraph(f"{float(row.get('total_marks') or 0):g}", val_style),
            Paragraph(str(row.get("class_position") or "-"), val_style),
            Paragraph(str(row.get("grade_position") or "-"), val_style),
        ])
    results_table = Table(table_data, colWidths=[30 * mm, 25 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm])
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#102a43")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#102a43")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ])
    for index in range(1, len(table_data)):
        style.add("BACKGROUND", (0, index), (-1, index), colors.HexColor("#f0f4f8") if index % 2 == 0 else colors.white)
    results_table.setStyle(style)
    story.append(results_table)
    document.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="student-results-{pupil["admission_no"]}.pdf"'
    return response


@student_portal_required
def student_e_learning(request, pupil):
    context = e_learning_context(pupil)
    return render(
        request,
        "portals/student_e_learning.html",
        {
            "title": "E-Learning",
            "pupil": pupil,
            "assignments": context["assignments"],
            "notes": context["notes"],
            "due_open": context["due_open"],
            "settings": school_settings(),
        },
    )


def save_uploaded_submission_file(uploaded_file):
    relative, target_path = tenant_submission_path(uploaded_file.name)
    os_dir = __import__("os")
    os_dir.makedirs(os_dir.path.dirname(target_path), exist_ok=True)
    with open(target_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
    return relative, uploaded_file.name


@student_portal_required
def student_submit_assignment(request, pupil, assignment_id):
    from django.db import connection

    assignment = portal_assignment_for_student(pupil, assignment_id)
    if not assignment:
        messages.error(request, "Assignment not found for your class and subjects.")
        return redirect("student_portal:e_learning")

    submission = row_if_tables(
        ["e_learning_submissions"],
        "SELECT * FROM e_learning_submissions WHERE assignment_id = %s AND pupil_id = %s",
        [assignment_id, pupil["pupil_id"]],
    )
    if request.method == "POST":
        if assignment["status"] != "Open":
            messages.error(request, "This assignment is closed and cannot receive submissions.")
            return redirect("student_portal:submit_assignment", assignment_id=assignment_id)
        if submission and submission["status"] == "Marked":
            messages.error(request, "This assignment has already been marked and cannot be updated.")
            return redirect("student_portal:submit_assignment", assignment_id=assignment_id)

        answer_text = request.POST.get("answer_text") or ""
        file_path = submission["file_path"] if submission else None
        original_filename = submission["original_filename"] if submission else None
        if request.FILES.get("file"):
            try:
                file_path, original_filename = save_uploaded_submission_file(request.FILES["file"])
            except Exception as exc:
                messages.error(request, f"Failed to upload submission file: {exc}")

        with connection.cursor() as cursor:
            if submission:
                cursor.execute(
                    """
                    UPDATE e_learning_submissions
                    SET answer_text = %s, file_path = %s, original_filename = %s, status = 'Submitted', updated_at = %s
                    WHERE submission_id = %s AND pupil_id = %s
                    """,
                    [answer_text, file_path, original_filename, now_text(), submission["submission_id"], pupil["pupil_id"]],
                )
                messages.success(request, "Assignment submission updated successfully.")
            else:
                cursor.execute(
                    """
                    INSERT INTO e_learning_submissions (assignment_id, pupil_id, answer_text, file_path, original_filename, status, submitted_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, 'Submitted', %s, %s)
                    """,
                    [assignment_id, pupil["pupil_id"], answer_text, file_path, original_filename, now_text(), now_text()],
                )
                messages.success(request, "Assignment submitted successfully.")
        audit_action(request, "Student assignment submission", f"{pupil['admission_no']} submitted assignment {assignment_id}")
        return redirect("student_portal:submit_assignment", assignment_id=assignment_id)

    return render(
        request,
        "portals/student_e_learning_submit.html",
        {"title": "Submit Assignment", "pupil": pupil, "assignment": assignment, "submission": submission, "settings": school_settings()},
    )


@student_portal_required
def student_timetable(request, pupil):
    context = timetable_context(pupil)
    return render(
        request,
        "portals/student_timetable.html",
        {
            "title": "Timetable",
            "pupil": pupil,
            "periods": context["periods"],
            "timetable_rows": context["timetable_rows"],
            "settings": school_settings(),
        },
    )


@student_portal_required
def student_statement(request, pupil):
    summary = student_financial_summary(pupil=pupil)
    rows = statement_payment_rows(pupil["pupil_id"], limit=500)
    settings = school_settings()
    statement_no = statement_number(pupil)
    export_type = (request.GET.get("export") or "").lower()
    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        return statement_pdf_response(pupil, summary, rows, settings, statement_no)
    if export_type in {"xlsx", "excel"}:
        return statement_excel(pupil, summary, rows, settings, statement_no)
    return render(
        request,
        "reports/student_statement.html",
        {"pupil": pupil, "summary": summary, "payments": rows, "today": today_text(), "settings": settings, "portal_statement": True, "statement_no": statement_no},
    )


@student_portal_required
def student_pay(request, pupil, reference_no=None):
    if not reference_no:
        reference_no = getattr(request.resolver_match, "kwargs", {}).get("reference_no")
    if reference_no:
        request_row = row_if_tables(
            ["online_payment_requests"],
            "SELECT * FROM online_payment_requests WHERE reference_no = %s AND pupil_id = %s",
            [reference_no, pupil["pupil_id"]],
        )
        return render(request, "portals/student_pay.html", {"pupil": pupil, "request_row": request_row, "summary": student_financial_summary(pupil=pupil), "settings": school_settings()})

    if request.method == "POST":
        amount_raw = request.POST.get("amount")
        method = (request.POST.get("method") or "").strip() or "Bank Transfer"
        reference = (request.POST.get("reference") or f"PORTAL-{pupil['pupil_id']}-{today_text().replace('-', '')}-{now_text()[-2:]}").strip()
        try:
            amount = Decimal(str(amount_raw or "0"))
            if amount <= 0:
                raise InvalidOperation()
        except (InvalidOperation, ValueError):
            amount = None
            messages.error(request, "Enter a valid payment amount greater than zero.")
        if amount is not None and row_if_tables(["online_payment_requests"], "SELECT request_id FROM online_payment_requests WHERE reference_no = %s OR bank_reference_no = %s", [reference, reference]):
            messages.error(request, "That bank reference has already been submitted.")
        elif amount is not None and row_if_tables(["payments"], "SELECT payment_id FROM payments WHERE reference_no = %s", [reference]):
            messages.error(request, "That bank reference has already been receipted.")
        elif amount is not None:
            settings = school_settings()
            insert_record(
                request,
                "online_payment_requests",
                {
                    "pupil_id": pupil["pupil_id"],
                    "reference_no": reference,
                    "amount": str(amount),
                    "method": method,
                    "phone_number": pupil.get("guardian_phone"),
                    "term": settings.get("current_term") or "Term 1",
                    "year": settings.get("current_year") or today_text()[:4],
                    "status": "Pending",
                    "created_at": now_text(),
                    "updated_at": now_text(),
                    "bank_reference_no": reference,
                },
            )
            audit_action(request, "Student portal payment request", f"{pupil['admission_no']} submitted {reference}")
            messages.success(request, "Payment reference submitted for approval.")
            return redirect("student_portal:payment_status", reference_no=reference)
    return render(
        request,
        "portals/student_pay.html",
        {
            "pupil": pupil,
            "summary": student_financial_summary(pupil=pupil),
            "pending_payments": pending_payment_requests(pupil["pupil_id"], limit=10),
            "settings": school_settings(),
        },
    )


@student_portal_required
def student_textbooks(request, pupil):
    rows = textbook_rows(pupil["pupil_id"])
    return render(request, "portals/student_textbooks.html", {"title": "Textbooks", "pupil": pupil, "rows": rows, "overdue_textbooks": overdue_textbook_count(pupil["pupil_id"]), "settings": school_settings()})


@student_portal_required
def student_receipt(request, pupil, payment_id=None, receipt_no=None):
    context = receipt_context(receipt_no=receipt_no, payment_id=payment_id)
    if context is None and receipt_no and str(receipt_no).isdigit():
        context = receipt_context(payment_id=receipt_no)
    if not context or context["pupil"]["pupil_id"] != pupil["pupil_id"]:
        messages.error(request, "Receipt not found.")
        return redirect("student_portal:statement")
    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        from fees.views import receipt_pdf_response

        return receipt_pdf_response(context, request=request)
    from fees.views import decorate_receipt_context

    context = decorate_receipt_context(request, context)
    context["can_edit_receipt"] = False
    context["can_delete_receipt"] = False
    context["portal_receipt"] = True
    return render(request, "fees/receipt.html", context)


@student_portal_api_required
def student_updates(request, pupil):
    context = dashboard_context(pupil)
    data = {
        "ok": True,
        "student": {
            "pupil_id": pupil["pupil_id"],
            "admission_no": pupil.get("admission_no"),
            "name": f"{pupil.get('first_name') or ''} {pupil.get('surname') or ''}".strip(),
            "class_label": context["class_label"],
        },
        "finance": context["summary"],
        "attendance": context["attendance"],
        "published_results": len(context["results"]),
        "assignments_due": len(context["assignments_due"]),
        "overdue_textbooks": context["overdue_textbooks"],
        "pending_payments": context["pending_payments"],
        "generated_at": now_text(),
    }
    return JsonResponse(decimal_json(data))


@student_portal_api_required
def student_api(request, pupil, module):
    module = (module or "dashboard").lower()
    if module == "dashboard":
        payload = dashboard_context(pupil)
    elif module == "attendance":
        payload = {"summary": attendance_summary(pupil["pupil_id"]), "history": attendance_history(pupil["pupil_id"])}
    elif module == "results":
        rows = published_results(pupil["pupil_id"])
        payload = {"results": rows, "latest_entries": rows_if_tables(["result_entries"], "SELECT * FROM result_entries WHERE result_id = %s", [rows[0]["result_id"]]) if rows else []}
    elif module == "fees":
        payload = {"summary": student_financial_summary(pupil=pupil), "payments": portal_payments(pupil["pupil_id"], limit=50), "pending_payments": pending_payment_requests(pupil["pupil_id"], limit=20)}
    elif module == "timetable":
        payload = timetable_context(pupil)
    elif module == "elearning":
        payload = e_learning_context(pupil)
    elif module == "textbooks":
        payload = {"rows": textbook_rows(pupil["pupil_id"]), "overdue_textbooks": overdue_textbook_count(pupil["pupil_id"])}
    else:
        return JsonResponse({"ok": False, "error": "unknown_module"}, status=404)
    return JsonResponse(decimal_json({"ok": True, "module": module, "data": payload, "generated_at": now_text()}))
