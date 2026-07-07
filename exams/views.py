from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from accounts.permissions import permission_required, user_has_permission
from school_system_django.native import delete_record, dict_rows, hydrate_class_labels, legacy_user_id, now_text, render_detail_page, render_record_form_page, render_table_page, simple_pdf, today_text, update_record_fields


EXAM_FIELDS = ["exam_name", "term", "year", "grade", "start_date", "end_date", "status", "notes"]
RESULT_FIELDS = ["pupil_id", "term", "year", "status", "total_marks", "average_mark", "teacher_comment", "grade_snapshot", "class_stream_snapshot", "class_position", "grade_position"]


def extra_context_tabs(active):
    return [
        {"label": "Result Sheets", "href": "/results?tab=sheets", "active": active == "sheets"},
        {"label": "Class Marks Entry", "href": "/results?tab=entry", "active": active == "entry"},
        {"label": "Bulk Publish", "href": "/results?tab=publish", "active": active == "publish"},
        {"label": "Mark Schedule", "href": "/results?tab=schedule", "active": active == "schedule"},
        {"label": "Analytics", "href": "/results?tab=analytics", "active": active == "analytics"},
        {"label": "Predictions", "href": "/results?tab=predictions", "active": active == "predictions"},
        {"label": "Exam Setup", "href": "/results?tab=setup", "active": active == "setup"},
    ]


def active_pupils_for_class(selected_class, grade_name="", select_fields=None):
    from school_system_django.native import active_pupils_for_class as load_active_pupils_for_class

    return load_active_pupils_for_class(selected_class, grade_name, select_fields)


def result_sheets_for_pupils(students, term, year):
    from school_system_django.native import dict_rows

    pupil_ids = [s.get("pupil_id") for s in students if s.get("pupil_id")]
    if not pupil_ids:
        return []
    placeholders = ", ".join(["%s"] * len(pupil_ids))
    return dict_rows(
        f"SELECT * FROM result_sheets WHERE term = %s AND year = %s AND pupil_id IN ({placeholders})",
        [term, int(year)] + pupil_ids,
    )


@permission_required("results.manage")
def setup(request, tabbed=False):
    from django.shortcuts import redirect
    if not tabbed:
        return redirect("/results?tab=setup")
    tabs = extra_context_tabs("setup")
    return render_table_page(
        request,
        "Examination Setup",
        "exam_sessions",
        ["exam_id", "exam_name", "term", "year", "grade", "start_date", "end_date", "status"],
        "Exam windows and publishing status.",
        order_by="year DESC, term DESC",
        search_columns=["exam_name", "grade", "status"],
        pk_column="exam_id",
        create_href="/exams/new",
        create_label="New Exam",
        row_actions=[
            {"label": "View", "href": "/exams/{exam_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/exams/{exam_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/exams/{exam_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this exam session?"},
        ],
        extra_context={"tabs": tabs, "active_tab": "setup"}
    )


@permission_required("results.manage")
def results(request):
    from django.shortcuts import redirect, render
    from school_system_django.native import class_membership_where, dict_rows, current_user_role, school_settings, one_row
    from accounts.permissions import assigned_classes_for_teacher, user_has_permission
    from django.core.paginator import Paginator

    tab = request.GET.get("tab") or "sheets"
    if tab == "entry":
        return result_class_entry(request, tabbed=True)
    if tab == "publish":
        return result_bulk_publish(request, tabbed=True)
    if tab == "setup":
        return setup(request, tabbed=True)
    if tab == "predictions":
        return predictions(request, tabbed=True)
    if tab == "schedule":
        return result_mark_schedule(request, tabbed=True)
    if tab == "analytics":
        return result_analytics(request, tabbed=True)

    tabs = extra_context_tabs("sheets")
    role = current_user_role(request.user)

    # Base query for results sheets list
    query = """
        SELECT r.*, p.admission_no, p.first_name, p.surname, p.gender, p.class_id
        FROM result_sheets r
        JOIN pupils p ON p.pupil_id = r.pupil_id
    """
    params = []
    where_clauses = []

    # Enforce strict teacher visibility with admin bypass
    is_admin = request.user.is_superuser or user_has_permission(request.user, "results.publish")
    allowed_class_ids = assigned_classes_for_teacher(request.user)
    if role == "Teacher" and not is_admin:
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            where_clauses.append(f"p.class_id IN ({placeholders})")
            params.extend(allowed_class_ids)
        else:
            where_clauses.append("1 = 0")
    
    # Filter by search q
    search_q = (request.GET.get("q") or "").strip()
    if search_q:
        where_clauses.append("(p.admission_no LIKE %s OR p.first_name LIKE %s OR p.surname LIKE %s)")
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])

    # Filter by class
    selected_class_id = request.GET.get("class_id")
    if selected_class_id:
        if role == "Teacher" and not is_admin and int(selected_class_id) not in allowed_class_ids:
            pass
        else:
            selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [selected_class_id])
            if selected_class:
                grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class["grade_id"]])
                membership_where, membership_params = class_membership_where(
                    selected_class,
                    (grade_rec or {}).get("grade_name") or "",
                    table_alias="p",
                )
                where_clauses.append(membership_where)
                params.extend(membership_params)
            else:
                where_clauses.append("1 = 0")

    # Filter by term / year
    selected_term = request.GET.get("term")
    if selected_term:
        where_clauses.append("r.term = %s")
        params.append(selected_term)

    selected_year = request.GET.get("year")
    if selected_year:
        where_clauses.append("r.year = %s")
        params.append(int(selected_year))

    order_by = request.GET.get("order_by") or ""

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    if order_by == "class_position":
        query += " ORDER BY r.year DESC, r.term DESC, CASE WHEN r.class_position IS NULL OR r.class_position = 0 THEN 999999 ELSE r.class_position END ASC, p.surname, p.first_name"
    elif order_by == "grade_position":
        query += " ORDER BY r.year DESC, r.term DESC, CASE WHEN r.grade_position IS NULL OR r.grade_position = 0 THEN 999999 ELSE r.grade_position END ASC, p.surname, p.first_name"
    else:
        query += " ORDER BY r.year DESC, r.term DESC, p.surname, p.first_name"

    all_results = dict_rows(query, params)
    
    # Hydrate student admission numbers
    from school_system_django.native import hydrate_admission_numbers
    all_results = hydrate_admission_numbers(all_results)

    # Paginate results
    page_num = request.GET.get("page", 1)
    paginator = Paginator(all_results, 25)
    page_obj = paginator.get_page(page_num)

    # Get classes for filters dropdown
    if role == "Teacher" and not is_admin:
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            classes = dict_rows(
                f"SELECT class_id, class_name, academic_year, grade_id FROM classes WHERE class_id IN ({placeholders}) ORDER BY academic_year DESC, class_name",
                allowed_class_ids
            )
        else:
            classes = []
    else:
        classes = dict_rows("SELECT class_id, class_name, academic_year, grade_id FROM classes ORDER BY academic_year DESC, class_name")
    
    for c in classes:
        g = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [c["grade_id"]])
        c["grade_name"] = g["grade_name"] if g else ""

    settings = school_settings()
    try:
        current_year_number = int(settings.get("current_year") or 2026)
    except (TypeError, ValueError):
        current_year_number = 2026
    years = list(range(current_year_number, current_year_number - 4, -1))

    can_publish = user_has_permission(request.user, "results.publish")

    context = {
        "tabs": tabs,
        "active_tab": "sheets",
        "page_obj": page_obj,
        "classes": classes,
        "years": years,
        "selected_class_id": selected_class_id,
        "selected_term": selected_term,
        "selected_year": selected_year,
        "q": search_q,
        "can_publish": can_publish,
        "current_role": role,
        "order_by": order_by,
    }
    return render(request, "exams/results_list.html", context)


def results_export_pdf(request):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.http import HttpResponse
    from school_system_django.native import class_membership_where, school_settings, dict_rows, current_user_role, one_row, get_pdf_header, hydrate_admission_numbers
    from accounts.permissions import assigned_classes_for_teacher, user_has_permission

    role = current_user_role(request.user)
    is_admin = request.user.is_superuser or user_has_permission(request.user, "results.publish")
    allowed_class_ids = assigned_classes_for_teacher(request.user)

    # Base query for results sheets list
    query = """
        SELECT r.*, p.admission_no, p.first_name, p.surname, p.gender, p.class_id
        FROM result_sheets r
        JOIN pupils p ON p.pupil_id = r.pupil_id
    """
    params = []
    where_clauses = []

    # Enforce strict teacher visibility with admin bypass
    if role == "Teacher" and not is_admin:
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            where_clauses.append(f"p.class_id IN ({placeholders})")
            params.extend(allowed_class_ids)
        else:
            where_clauses.append("1 = 0")
    
    # Filter by search q
    search_q = (request.GET.get("q") or "").strip()
    if search_q:
        where_clauses.append("(p.admission_no LIKE %s OR p.first_name LIKE %s OR p.surname LIKE %s)")
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])

    # Filter by class
    selected_class_id = request.GET.get("class_id")
    if selected_class_id:
        if role == "Teacher" and not is_admin and int(selected_class_id) not in allowed_class_ids:
            pass
        else:
            selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [selected_class_id])
            if selected_class:
                grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class["grade_id"]])
                membership_where, membership_params = class_membership_where(
                    selected_class,
                    (grade_rec or {}).get("grade_name") or "",
                    table_alias="p",
                )
                where_clauses.append(membership_where)
                params.extend(membership_params)
            else:
                where_clauses.append("1 = 0")

    # Filter by term / year
    selected_term = request.GET.get("term")
    if selected_term:
        where_clauses.append("r.term = %s")
        params.append(selected_term)

    selected_year = request.GET.get("year")
    if selected_year:
        where_clauses.append("r.year = %s")
        params.append(int(selected_year))

    order_by = request.GET.get("order_by") or ""

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    if order_by == "class_position":
        query += " ORDER BY r.year DESC, r.term DESC, CASE WHEN r.class_position IS NULL OR r.class_position = 0 THEN 999999 ELSE r.class_position END ASC, p.surname, p.first_name"
    elif order_by == "grade_position":
        query += " ORDER BY r.year DESC, r.term DESC, CASE WHEN r.grade_position IS NULL OR r.grade_position = 0 THEN 999999 ELSE r.grade_position END ASC, p.surname, p.first_name"
    else:
        query += " ORDER BY r.year DESC, r.term DESC, p.surname, p.first_name"

    all_results = dict_rows(query, params)
    all_results = hydrate_admission_numbers(all_results)

    # Generate ReportLab PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#0f766e'),
        alignment=1,
        spaceAfter=5
    )

    meta_style = ParagraphStyle(
        'MetaText',
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor('#334155'),
        alignment=1,
        spaceAfter=15
    )

    hdr_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.white,
        alignment=0
    )
    hdr_style_center = ParagraphStyle(
        'TableHeaderCenter',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.white,
        alignment=1
    )

    cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#0f172a'),
        alignment=0
    )
    cell_style_center = ParagraphStyle(
        'TableCellCenter',
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#0f172a'),
        alignment=1
    )

    story = []

    # Get school settings & header
    settings = school_settings()
    story.append(get_pdf_header(settings, 190 * mm))
    story.append(Spacer(1, 5 * mm))

    # Title
    story.append(Paragraph("Results Centre Report", title_style))

    # Metadata sub-title
    meta_parts = []
    if selected_class_id:
        class_rec = one_row("SELECT class_name, grade_id FROM classes WHERE class_id = %s", [selected_class_id])
        if class_rec:
            grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [class_rec["grade_id"]])
            class_label = f"{grade_rec['grade_name']} {class_rec['class_name']}" if grade_rec else class_rec["class_name"]
            meta_parts.append(f"Class: {class_label}")
    else:
        meta_parts.append("Class: All Classes")

    if selected_term:
        meta_parts.append(f"Term: {selected_term}")
    if selected_year:
        meta_parts.append(f"Year: {selected_year}")
    
    sort_label = "Alphabetical"
    if order_by == "class_position":
        sort_label = "Class Position"
    elif order_by == "grade_position":
        sort_label = "Grade Position"
    meta_parts.append(f"Sorted By: {sort_label}")

    story.append(Paragraph(" | ".join(meta_parts), meta_style))

    # Table columns
    headers = [
        Paragraph("#", hdr_style_center),
        Paragraph("Admission No", hdr_style),
        Paragraph("Student Name", hdr_style),
        Paragraph("Gender", hdr_style_center),
        Paragraph("Grade/Stream", hdr_style),
        Paragraph("Term/Year", hdr_style_center),
        Paragraph("Total Marks", hdr_style_center),
        Paragraph("Average", hdr_style_center),
        Paragraph("Class Pos", hdr_style_center),
        Paragraph("Grade Pos", hdr_style_center)
    ]

    table_data = [headers]

    for idx, r in enumerate(all_results):
        class_lbl = ""
        # Calculate class label
        if r.get("class_id"):
            class_rec = one_row("SELECT class_name, grade_id FROM classes WHERE class_id = %s", [r["class_id"]])
            if class_rec:
                grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [class_rec["grade_id"]])
                grade_name = grade_rec["grade_name"] if grade_rec else ""
                class_lbl = f"{grade_name} {class_rec['class_name']}" if grade_name else class_rec["class_name"]
        
        avg_text = f"{r.get('average_mark', 0.0):.1f}%" if r.get('average_mark') is not None else "-"
        total_text = f"{r.get('total_marks', 0.0):.0f}" if r.get('total_marks') is not None else "-"
        
        row = [
            Paragraph(str(idx + 1), cell_style_center),
            Paragraph(str(r.get("admission_no") or "-"), cell_style),
            Paragraph(f"{r.get('first_name', '')} {r.get('surname', '')}", cell_style),
            Paragraph(str(r.get("gender") or "-"), cell_style_center),
            Paragraph(class_lbl, cell_style),
            Paragraph(f"{r.get('term', '')} {r.get('year', '')}", cell_style_center),
            Paragraph(total_text, cell_style_center),
            Paragraph(avg_text, cell_style_center),
            Paragraph(str(r.get("class_position") or "-"), cell_style_center),
            Paragraph(str(r.get("grade_position") or "-"), cell_style_center)
        ]
        table_data.append(row)

    # Column widths (A4 width = 210mm, margins = 20mm, content width = 190mm)
    col_widths = [10*mm, 22*mm, 42*mm, 15*mm, 25*mm, 23*mm, 18*mm, 15*mm, 10*mm, 10*mm]
    
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
    ]))

    story.append(t)
    doc.build(story)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="results-centre-report.pdf"'
    return response


@permission_required("results.manage")
def result_mark_schedule(request, tabbed=False):
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from school_system_django.native import school_settings, one_row, dict_rows, current_user_role
    from accounts.permissions import assigned_classes_for_teacher

    if not tabbed:
        params = request.GET.urlencode()
        url = "/results?tab=schedule"
        if params:
            url += f"&{params}"
        return redirect(url)

    role = current_user_role(request.user)
    is_admin = request.user.is_superuser or user_has_permission(request.user, "results.publish")
    allowed_class_ids = assigned_classes_for_teacher(request.user)

    # Get class list for dropdown
    if role == "Teacher" and not is_admin:
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            classes = dict_rows(
                f"SELECT class_id, class_name, academic_year, grade_id FROM classes WHERE class_id IN ({placeholders}) ORDER BY academic_year DESC, class_name",
                allowed_class_ids
            )
        else:
            classes = []
    else:
        classes = dict_rows("SELECT class_id, class_name, academic_year, grade_id FROM classes ORDER BY academic_year DESC, class_name")

    for c in classes:
        g = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [c["grade_id"]])
        c["grade_name"] = g["grade_name"] if g else ""

    settings = school_settings()
    curr_term = settings.get("current_term") or "Term 1"
    curr_year = str(settings.get("current_year", 2026))

    selected_class_id = request.GET.get("class_id")
    selected_term = request.GET.get("term") or curr_term
    selected_year = request.GET.get("year") or curr_year

    years = [2026, 2027, 2025]

    selected_class = None
    subjects = []
    students_data = []

    if selected_class_id:
        if role == "Teacher" and not is_admin and int(selected_class_id) not in allowed_class_ids:
            messages.error(request, "You are not assigned to view the mark schedule for this class.")
            return redirect("/results?tab=schedule")

        selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [selected_class_id])
        if selected_class:
            grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class["grade_id"]])
            grade_name = grade_rec["grade_name"] if grade_rec else ""
            
            # Fetch subjects for this grade
            subjects = dict_rows(
                "SELECT subject_id, subject_code, subject_name FROM subjects WHERE status = 'Active' AND (grade = 'All Forms' OR grade = %s) ORDER BY display_order, subject_name",
                [grade_name]
            )

            # Fetch active students linked by current class_id or legacy grade/stream data.
            students = active_pupils_for_class(selected_class, grade_name)

            # Fetch results sheets
            sheets = result_sheets_for_pupils(students, selected_term, selected_year)
            sheet_map = {s["pupil_id"]: s for s in sheets}

            # Fetch results entries
            if sheets:
                sheet_ids = [s["result_id"] for s in sheets]
                placeholders = ", ".join(["%s"] * len(sheet_ids))
                entries = dict_rows(
                    f"SELECT result_id, subject_id, mark, grade FROM result_entries WHERE result_id IN ({placeholders})",
                    sheet_ids
                )
                entry_map = {(e["result_id"], e["subject_id"]): e for e in entries}
            else:
                entry_map = {}

            # Populate grid data
            for s in students:
                pupil_id = s["pupil_id"]
                sheet = sheet_map.get(pupil_id)
                
                row_data = {
                    "student": s,
                    "sheet": sheet,
                    "marks": {},
                    "passed_all": False
                }

                if sheet:
                    result_id = sheet["result_id"]
                    has_marks = False
                    failed_any = False
                    
                    for sub in subjects:
                        entry = entry_map.get((result_id, sub["subject_id"]))
                        if entry:
                            row_data["marks"][sub["subject_id"]] = entry["mark"]
                            has_marks = True
                            if float(entry["mark"]) < 40.0:
                                failed_any = True
                        else:
                            row_data["marks"][sub["subject_id"]] = None
                            failed_any = True

                    row_data["passed_all"] = has_marks and not failed_any
                else:
                    for sub in subjects:
                        row_data["marks"][sub["subject_id"]] = None
                    row_data["passed_all"] = False

                students_data.append(row_data)

    tabs = extra_context_tabs("schedule")
    context = {
        "tabs": tabs,
        "active_tab": "schedule",
        "classes": classes,
        "years": years,
        "selected_class_id": selected_class_id,
        "selected_term": selected_term,
        "selected_year": selected_year,
        "selected_class": selected_class,
        "subjects": subjects,
        "students_data": students_data,
        "settings": school_settings(),
    }
    return render(request, "exams/mark_schedule.html", context)


@permission_required("results.manage")
def result_mark_schedule_pdf(request):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.http import HttpResponse
    from django.contrib import messages
    from django.shortcuts import redirect
    from school_system_django.native import compact_class_label, school_settings, one_row, dict_rows, current_user_role, today_text
    from accounts.permissions import assigned_classes_for_teacher

    role = current_user_role(request.user)
    is_admin = request.user.is_superuser or user_has_permission(request.user, "results.publish")
    allowed_class_ids = assigned_classes_for_teacher(request.user)

    class_id = request.GET.get("class_id")
    term = request.GET.get("term")
    year = request.GET.get("year")

    if not class_id or not term or not year:
        return HttpResponse("Missing query parameters (class_id, term, year)", status=400)

    if role == "Teacher" and not is_admin and int(class_id) not in allowed_class_ids:
        return HttpResponse("Unauthorized access", status=403)

    selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [class_id])
    if not selected_class:
        return HttpResponse("Class not found", status=404)

    grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class["grade_id"]])
    grade_name = grade_rec["grade_name"] if grade_rec else ""
    class_label = compact_class_label(grade_id=selected_class.get("grade_id"), grade_name=grade_name, class_name=selected_class.get("class_name"))

    # Fetch subjects
    subjects = dict_rows(
        "SELECT subject_id, subject_code, subject_name FROM subjects WHERE status = 'Active' AND (grade = 'All Forms' OR grade = %s) ORDER BY display_order, subject_name",
        [grade_name]
    )

    # Fetch active students linked by current class_id or legacy grade/stream data.
    students = active_pupils_for_class(selected_class, grade_name)

    # Fetch results sheets
    sheets = result_sheets_for_pupils(students, term, year)
    sheet_map = {s["pupil_id"]: s for s in sheets}

    # Fetch results entries
    if sheets:
        sheet_ids = [s["result_id"] for s in sheets]
        placeholders = ", ".join(["%s"] * len(sheet_ids))
        entries = dict_rows(
            f"SELECT result_id, subject_id, mark, grade FROM result_entries WHERE result_id IN ({placeholders})",
            sheet_ids
        )
        entry_map = {(e["result_id"], e["subject_id"]): e for e in entries}
    else:
        entry_map = {}

    settings = school_settings()
    buffer = BytesIO()
    
    document = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(A4), 
        rightMargin=10 * mm, 
        leftMargin=10 * mm, 
        topMargin=10 * mm, 
        bottomMargin=10 * mm
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'SchoolName',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=18,
        textColor=colors.HexColor('#0f766e'),
        alignment=1,
        spaceAfter=2
    )

    meta_style = ParagraphStyle(
        'MetaText',
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.HexColor('#334155'),
        alignment=1,
        spaceAfter=10
    )

    hdr_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.white,
        alignment=1
    )

    cell_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        textColor=colors.HexColor('#0f172a'),
        alignment=1
    )

    cell_style_left = ParagraphStyle(
        'TableCellLeft',
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=colors.HexColor('#0f172a'),
        alignment=0
    )

    story = []

    # Header
    from school_system_django.native import get_pdf_header
    story.append(get_pdf_header(settings, 277 * mm))
    story.append(Paragraph(f"CLASS MARK SCHEDULE &middot; {class_label} &middot; {term} {year} &middot; Printed: {today_text()}", meta_style))
    story.append(Spacer(1, 5))

    # Broad Sheet Table headers: Name, Sub1, Sub2, ..., SubN, Total, Avg, class pos, grade pos, status
    headers = [Paragraph("<b>Student Name</b>", cell_style_left)]
    for sub in subjects:
        headers.append(Paragraph(sub["subject_code"], hdr_style))
    headers.extend([
        Paragraph("<b>Total</b>", hdr_style),
        Paragraph("<b>Avg %</b>", hdr_style),
        Paragraph("<b>Class Pos</b>", hdr_style),
        Paragraph("<b>Grade Pos</b>", hdr_style),
        Paragraph("<b>Status</b>", hdr_style)
    ])

    table_data = [headers]

    for s in students:
        pupil_id = s["pupil_id"]
        sheet = sheet_map.get(pupil_id)
        
        row = [Paragraph(f"{s['first_name']} {s['surname']} ({s['admission_no']})", cell_style_left)]
        
        if sheet:
            result_id = sheet["result_id"]
            failed_any = False
            has_marks = False
            for sub in subjects:
                entry = entry_map.get((result_id, sub["subject_id"]))
                if entry:
                    row.append(Paragraph(f"{float(entry['mark']):g}", cell_style))
                    has_marks = True
                    if float(entry["mark"]) < 40.0:
                        failed_any = True
                else:
                    row.append(Paragraph("-", cell_style))
                    failed_any = True

            passed_all = has_marks and not failed_any
            
            row.extend([
                Paragraph(f"{float(sheet['total_marks']):g}", cell_style),
                Paragraph(f"{float(sheet['average_mark']):.1f}%", cell_style),
                Paragraph(str(sheet["class_position"] or "-"), cell_style),
                Paragraph(str(sheet["grade_position"] or "-"), cell_style),
                Paragraph("<b>PASS</b>" if passed_all else "FAIL", ParagraphStyle('Pill', parent=cell_style, textColor=colors.HexColor("#166534") if passed_all else colors.HexColor("#b91c1c")))
            ])
        else:
            for sub in subjects:
                row.append(Paragraph("-", cell_style))
            row.extend([
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("-", cell_style),
                Paragraph("N/A", cell_style)
            ])
        table_data.append(row)

    num_subs = len(subjects)
    rem_width = 277 - 70 - 81
    sub_col_width = (rem_width / num_subs) if num_subs > 0 else 20
    
    col_widths = [70 * mm] + [sub_col_width * mm] * num_subs + [15 * mm, 15 * mm, 18 * mm, 18 * mm, 15 * mm]

    table = Table(table_data, colWidths=col_widths, repeatRows=1)
    
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0f766e')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ])

    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f8fafc'))
        else:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.white)

    table.setStyle(t_style)
    story.append(table)

    document.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="broadsheet-{class_label}-{term}-{year}.pdf"'
    return response


@permission_required("results.manage")
def result_analytics(request, tabbed=False):
    from django.shortcuts import render, redirect
    from school_system_django.native import school_settings, one_row, dict_rows, current_user_role
    from accounts.permissions import assigned_classes_for_teacher
    from django.utils import timezone

    if not tabbed:
        params = request.GET.urlencode()
        url = "/results?tab=analytics"
        if params:
            url += f"&{params}"
        return redirect(url)

    settings = school_settings()
    curr_term = settings.get("current_term") or "Term 1"
    actual_year = timezone.localdate().year
    try:
        curr_year = min(int(settings.get("current_year") or actual_year), actual_year)
    except (TypeError, ValueError):
        curr_year = actual_year

    selected_term = request.GET.get("term") or curr_term
    selected_year = int(request.GET.get("year") or curr_year)
    years = list(range(curr_year, curr_year - 4, -1))

    role = current_user_role(request.user)
    is_admin = request.user.is_superuser or user_has_permission(request.user, "results.publish")
    allowed_class_ids = assigned_classes_for_teacher(request.user)
    if role == "Teacher" and not is_admin:
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            classes = dict_rows(
                f"""
                SELECT c.class_id, c.class_name, c.grade_id, g.grade_name
                FROM classes c
                LEFT JOIN grades g ON g.grade_id = c.grade_id
                WHERE c.class_id IN ({placeholders})
                ORDER BY c.grade_id, c.class_name
                """,
                allowed_class_ids,
            )
        else:
            classes = []
    else:
        classes = dict_rows(
            """
            SELECT c.class_id, c.class_name, c.grade_id, g.grade_name
            FROM classes c
            LEFT JOIN grades g ON g.grade_id = c.grade_id
            ORDER BY c.grade_id, c.class_name
            """
        )

    scope_pairs = [(row.get("grade_name") or "", row.get("class_name") or "") for row in classes]

    def scoped_where(alias="r", extra=""):
        clauses = [f"{alias}.term = %s", f"{alias}.year = %s"]
        params = [selected_term, selected_year]
        if scope_pairs:
            pair_clauses = []
            for grade_name, class_name in scope_pairs:
                pair_clauses.append(f"({alias}.grade_snapshot = %s AND {alias}.class_stream_snapshot = %s)")
                params.extend([grade_name, class_name])
            clauses.append("(" + " OR ".join(pair_clauses) + ")")
        elif role == "Teacher" and not is_admin:
            clauses.append("1=0")
        if extra:
            clauses.append(extra)
        return " AND ".join(clauses), params

    where_sql, params = scoped_where("r")
    total_sheets = one_row(f"SELECT COUNT(*) as cnt FROM result_sheets r WHERE {where_sql}", params)["cnt"]

    passed_sheets = 0
    school_pass_rate = 0.0
    school_avg = 0.0

    if total_sheets > 0:
        where_sql, params = scoped_where(
            "r",
            """
            NOT EXISTS (
                SELECT 1 FROM result_entries e
                WHERE e.result_id = r.result_id AND e.mark < 40.0
            )
            AND EXISTS (
                SELECT 1 FROM result_entries e
                WHERE e.result_id = r.result_id
            )
            """,
        )
        passed_sheets = one_row(
            f"""
            SELECT COUNT(*) as cnt FROM result_sheets r
            WHERE {where_sql}
            """,
            params,
        )["cnt"]
        school_pass_rate = (passed_sheets / total_sheets) * 100.0

        where_sql, params = scoped_where("r")
        school_avg_res = one_row(f"SELECT AVG(average_mark) as avg_val FROM result_sheets r WHERE {where_sql}", params)
        school_avg = school_avg_res["avg_val"] if school_avg_res["avg_val"] is not None else 0.0

    # Class Pass Rates
    class_stats = []
    for c in classes:
        c_grade_name = c.get("grade_name") or ""
        
        c_total = one_row(
            "SELECT COUNT(*) as cnt FROM result_sheets WHERE term = %s AND year = %s AND class_stream_snapshot = %s AND grade_snapshot = %s",
            [selected_term, selected_year, c["class_name"], c_grade_name]
        )["cnt"]

        c_passed = 0
        c_pass_rate = 0.0
        c_avg = 0.0

        if c_total > 0:
            c_passed = one_row(
                """
                SELECT COUNT(*) as cnt FROM result_sheets r
                WHERE r.term = %s AND r.year = %s AND r.class_stream_snapshot = %s AND r.grade_snapshot = %s
                  AND NOT EXISTS (
                      SELECT 1 FROM result_entries e 
                      WHERE e.result_id = r.result_id AND e.mark < 40.0
                  )
                  AND EXISTS (
                      SELECT 1 FROM result_entries e 
                      WHERE e.result_id = r.result_id
                  )
                """,
                [selected_term, selected_year, c["class_name"], c_grade_name]
            )["cnt"]
            c_pass_rate = (c_passed / c_total) * 100.0
            c_avg_res = one_row(
                "SELECT AVG(average_mark) as avg_val FROM result_sheets WHERE term = %s AND year = %s AND class_stream_snapshot = %s AND grade_snapshot = %s",
                [selected_term, selected_year, c["class_name"], c_grade_name]
            )
            c_avg = c_avg_res["avg_val"] if c_avg_res["avg_val"] is not None else 0.0

        class_stats.append({
            "class_id": c["class_id"],
            "grade_name": c_grade_name,
            "class_name": c["class_name"],
            "total_students": c_total,
            "passed_students": c_passed,
            "pass_rate": c_pass_rate,
            "average_mark": c_avg,
        })

    # Grade Pass Rates
    grade_stats = []
    grade_names = sorted({row.get("grade_name") for row in classes if row.get("grade_name")})
    for grade_name in grade_names:
        grade_class_pairs = [(g, c) for g, c in scope_pairs if g == grade_name]
        pair_sql = " OR ".join(["(grade_snapshot = %s AND class_stream_snapshot = %s)"] * len(grade_class_pairs))
        pair_params = [value for pair in grade_class_pairs for value in pair]
        g_total = one_row(
            f"SELECT COUNT(*) as cnt FROM result_sheets WHERE term = %s AND year = %s AND ({pair_sql})",
            [selected_term, selected_year] + pair_params,
        )["cnt"] if pair_sql else 0

        g_passed = 0
        g_pass_rate = 0.0
        g_avg = 0.0

        if g_total > 0:
            g_passed = one_row(
                f"""
                SELECT COUNT(*) as cnt FROM result_sheets r
                WHERE r.term = %s AND r.year = %s AND ({pair_sql.replace('grade_snapshot', 'r.grade_snapshot').replace('class_stream_snapshot', 'r.class_stream_snapshot')})
                  AND NOT EXISTS (
                      SELECT 1 FROM result_entries e 
                      WHERE e.result_id = r.result_id AND e.mark < 40.0
                  )
                  AND EXISTS (
                      SELECT 1 FROM result_entries e 
                      WHERE e.result_id = r.result_id
                  )
                """,
                [selected_term, selected_year] + pair_params
            )["cnt"]
            g_pass_rate = (g_passed / g_total) * 100.0
            g_avg_res = one_row(
                f"SELECT AVG(average_mark) as avg_val FROM result_sheets WHERE term = %s AND year = %s AND ({pair_sql})",
                [selected_term, selected_year] + pair_params,
            )
            g_avg = g_avg_res["avg_val"] if g_avg_res["avg_val"] is not None else 0.0

        grade_stats.append({
            "grade_name": grade_name,
            "total_students": g_total,
            "passed_students": g_passed,
            "pass_rate": g_pass_rate,
            "average_mark": g_avg,
        })

    # Subject Pass Rates
    # For a subject, pass rate is count of entries with mark >= 40 / total entries
    subject_stats = []
    subjects = dict_rows("SELECT subject_id, subject_code, subject_name FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")
    for sub in subjects:
        where_sql, params = scoped_where("r", "e.subject_id = %s")
        params.append(sub["subject_id"])
        sub_total = one_row(
            f"""
            SELECT COUNT(e.entry_id) as cnt
            FROM result_entries e
            JOIN result_sheets r ON r.result_id = e.result_id
            WHERE {where_sql}
            """,
            params,
        )["cnt"]

        sub_passed = 0
        sub_pass_rate = 0.0
        sub_avg = 0.0

        if sub_total > 0:
            sub_passed = one_row(
                f"""
                SELECT COUNT(e.entry_id) as cnt
                FROM result_entries e
                JOIN result_sheets r ON r.result_id = e.result_id
                WHERE {where_sql} AND e.mark >= 40.0
                """,
                params,
            )["cnt"]
            sub_pass_rate = (sub_passed / sub_total) * 100.0
            sub_avg_res = one_row(
                f"""
                SELECT AVG(e.mark) as avg_val
                FROM result_entries e
                JOIN result_sheets r ON r.result_id = e.result_id
                WHERE {where_sql}
                """,
                params,
            )
            sub_avg = sub_avg_res["avg_val"] if sub_avg_res["avg_val"] is not None else 0.0

        subject_stats.append({
            "subject_code": sub["subject_code"],
            "subject_name": sub["subject_name"],
            "total_entries": sub_total,
            "passed_entries": sub_passed,
            "pass_rate": sub_pass_rate,
            "average_mark": sub_avg,
        })

    tabs = extra_context_tabs("analytics")
    context = {
        "tabs": tabs,
        "active_tab": "analytics",
        "years": years,
        "selected_term": selected_term,
        "selected_year": selected_year,
        "school_total": total_sheets,
        "school_passed": passed_sheets,
        "school_pass_rate": school_pass_rate,
        "school_average_mark": school_avg,
        "class_stats": class_stats,
        "grade_stats": grade_stats,
        "subject_stats": subject_stats,
        "settings": settings,
    }
    return render(request, "exams/analytics.html", context)


@permission_required("results.manage")
def predictions(request, tabbed=False):
    from django.shortcuts import redirect
    if not tabbed:
        return redirect("/results?tab=predictions")
    tabs = extra_context_tabs("predictions")
    return render_table_page(
        request,
        "Performance Predictions",
        "student_performance_predictions",
        ["prediction_id", "pupil_id", "term", "year", "risk_score", "risk_level", "predicted_average", "trend_label"],
        "Academic risk and prediction reports.",
        order_by="created_at DESC",
        search_columns=["risk_level", "trend_label"],
        pk_column="prediction_id",
        extra_context={"tabs": tabs, "active_tab": "predictions"}
    )


@permission_required("results.manage")
def exam_detail(request, exam_id):
    return render_detail_page(request, "Exam Session", "exam_sessions", "exam_id", exam_id)


@permission_required("results.manage")
def exam_new(request):
    return render_record_form_page(request, "New Exam Session", "exam_sessions", EXAM_FIELDS, redirect_to="/exams")


@permission_required("results.manage")
def exam_edit(request, exam_id):
    return render_record_form_page(request, "Edit Exam Session", "exam_sessions", EXAM_FIELDS, pk_column="exam_id", pk_value=exam_id, redirect_to=f"/exams/{exam_id}")


@permission_required("results.manage")
def exam_delete(request, exam_id):
    return delete_record(request, "Exam Session", "exam_sessions", "exam_id", exam_id, "/exams")


@permission_required("results.manage")
def result_detail(request, result_id):
    from django.db import connection
    from django.contrib import messages
    from django.shortcuts import redirect, render
    from school_system_django.native import dict_rows, one_row, school_settings, now_text, current_user_role
    from school_system_django.official_docs import published_date_time, qr_data_uri, result_verify_url
    from accounts.permissions import user_has_permission, assigned_classes_for_teacher

    result = one_row("SELECT * FROM result_sheets WHERE result_id = %s", [result_id])
    if not result:
        messages.error(request, "Result sheet not found.")
        return redirect("/results")

    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [result["pupil_id"]]) if result else {}
    
    # Security Check: Teachers can only view/download results of their assigned classes
    role = current_user_role(request.user)
    if role == "Teacher":
        allowed_class_ids = assigned_classes_for_teacher(request.user)
        if not allowed_class_ids or pupil.get("class_id") not in allowed_class_ids:
            messages.error(request, "You do not have permission to view or download results for this student.")
            return redirect("/results")

    entries = dict_rows(
        "SELECT s.subject_name, s.subject_code, s.display_order, e.mark, e.grade, e.subject_id, e.subject_comment FROM result_entries e LEFT JOIN subjects s ON s.subject_id = e.subject_id WHERE e.result_id = %s ORDER BY s.display_order, s.subject_name",
        [result_id],
    )

    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        return result_slip_pdf_response(result, pupil, entries, request)

    if request.method == "POST":
        if user_has_permission(request.user, "results.publish"):
            headmaster_comment = request.POST.get("headmaster_comment") or ""
            next_term_fees = request.POST.get("next_term_fees")
            try:
                nt_fees = float(next_term_fees) if next_term_fees else 0.0
            except ValueError:
                nt_fees = 0.0
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE result_sheets SET headmaster_comment = %s, next_term_fees = %s, updated_at = %s WHERE result_id = %s",
                    [headmaster_comment, nt_fees, now_text(), result_id]
                )
            from school_system_django.native import audit_action
            audit_action(request, "Save Admin Result comments", f"Saved admin comments and next term fees for result sheet {result_id}")
            messages.success(request, "Admin comments and next term fees updated successfully.")
            return redirect(f"/results/{result_id}")
        else:
            messages.error(request, "You do not have permission to publish or edit admin comments.")
            return redirect(f"/results/{result_id}")

    # Determine default next term fees for display
    term = result.get('term')
    year = int(result.get('year') or 2026)
    if term == 'Term 1':
        next_term = 'Term 2'
        next_year = year
    elif term == 'Term 2':
        next_term = 'Term 3'
        next_year = year
    else:
        next_term = 'Term 1'
        next_year = year + 1

    next_fees_rec = one_row(
        "SELECT amount_required FROM fees_structure WHERE (grade_id = %s OR grade = %s) AND term = %s AND year = %s",
        [pupil.get('grade_id'), result.get('grade_snapshot'), next_term, next_year]
    )
    default_fees = next_fees_rec['amount_required'] if next_fees_rec else 0.0
    published_date, published_time = published_date_time(result.get("published_at") or result.get("updated_at") or now_text())
    verify_url = result_verify_url(request, result_id)

    return render(
        request,
        "exams/result_detail.html",
        {
            "result": result,
            "pupil": pupil,
            "entries": entries,
            "settings": school_settings(),
            "can_publish": user_has_permission(request.user, "results.publish"),
            "current_role": role,
            "default_next_fees": default_fees,
            "published_date": published_date,
            "published_time": published_time,
            "result_verify_url": verify_url,
            "result_qr_data_uri": qr_data_uri(verify_url),
            "verification_id": f"RES-{result.get('year')}-{int(result_id):06d}",
        }
    )


def calculate_grade(mark):
    try:
        val = float(mark)
        if val >= 80:
            return "A"
        elif val >= 70:
            return "B"
        elif val >= 60:
            return "C"
        elif val >= 50:
            return "D"
        elif val >= 40:
            return "E"
        else:
            return "U"
    except (ValueError, TypeError):
        return "U"


def recalculate_positions(term, year, grade):
    from django.db import connection

    # 1. Recalculate GRADE positions
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT result_id, total_marks, average_mark
            FROM result_sheets
            WHERE term = %s AND year = %s AND grade_snapshot = %s
            ORDER BY average_mark DESC, total_marks DESC
            """,
            [term, year, grade]
        )
        rows = cursor.fetchall()

    rank = 1
    prev_avg = None
    prev_total = None
    for idx, (result_id, total, avg) in enumerate(rows):
        if prev_avg is not None and (avg != prev_avg or total != prev_total):
            rank = idx + 1
        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE result_sheets SET grade_position = %s WHERE result_id = %s",
                [rank, result_id]
            )
        prev_avg = avg
        prev_total = total

    # 2. Recalculate CLASS positions (by stream)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT DISTINCT class_stream_snapshot
            FROM result_sheets
            WHERE term = %s AND year = %s AND grade_snapshot = %s
            """,
            [term, year, grade]
        )
        streams = [r[0] for r in cursor.fetchall() if r[0]]

    for stream in streams:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT result_id, total_marks, average_mark
                FROM result_sheets
                WHERE term = %s AND year = %s AND grade_snapshot = %s AND class_stream_snapshot = %s
                ORDER BY average_mark DESC, total_marks DESC
                """,
                [term, year, grade, stream]
            )
            rows = cursor.fetchall()

        rank = 1
        prev_avg = None
        prev_total = None
        for idx, (result_id, total, avg) in enumerate(rows):
            if prev_avg is not None and (avg != prev_avg or total != prev_total):
                rank = idx + 1
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE result_sheets SET class_position = %s WHERE result_id = %s",
                    [rank, result_id]
                )
            prev_avg = avg
            prev_total = total


def result_slip_pdf_response(result, pupil, entries, request=None):
    from io import BytesIO
    import os
    from xml.sax.saxutils import escape

    from django.conf import settings as django_settings
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image
    from django.http import HttpResponse
    from school_system_django.native import compact_class_label, dict_rows, now_text, one_row, school_settings
    from students.services import ensure_student_photo, student_age_text
    from school_system_django.official_docs import (
        BORDER,
        GOLD,
        INK,
        LIGHT_BLUE,
        NAVY,
        official_logo_path,
        published_date_time,
        qr_flowable,
        result_verify_url,
        school_contact_line,
        school_website,
        create_reportlab_stamp,
    )

    settings = school_settings()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=8 * mm, leftMargin=8 * mm, topMargin=7 * mm, bottomMargin=7 * mm)
    styles = getSampleStyleSheet()
    navy = colors.HexColor(NAVY)
    gold = colors.HexColor(GOLD)
    border = colors.HexColor(BORDER)
    light = colors.HexColor(LIGHT_BLUE)
    ink = colors.HexColor(INK)

    title_style = ParagraphStyle("SlipSchool", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=22, leading=25, textColor=navy)
    motto_style = ParagraphStyle("SlipMotto", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=gold)
    small_style = ParagraphStyle("SlipSmall", parent=styles["Normal"], fontSize=8, leading=10, textColor=ink)
    label_style = ParagraphStyle("SlipLabel", parent=small_style, fontName="Helvetica-Bold", textColor=ink)
    value_style = ParagraphStyle("SlipValue", parent=small_style, fontName="Helvetica", textColor=ink)
    white_style = ParagraphStyle("SlipWhite", parent=small_style, fontName="Helvetica-Bold", textColor=colors.white)
    center_style = ParagraphStyle("SlipCenter", parent=value_style, alignment=1)
    right_style = ParagraphStyle("SlipRight", parent=value_style, alignment=2)

    def p(value, style=value_style):
        return Paragraph(escape(str(value if value is not None else "-")), style)

    def html(value, style=value_style):
        return Paragraph(value, style)

    attendance_pct = "100.0%"
    if pupil.get("pupil_id"):
        attendance_records = dict_rows(
            "SELECT status FROM attendance_records WHERE pupil_id = %s AND attendance_date LIKE %s",
            [pupil["pupil_id"], f"{result.get('year') or 2026}-%"],
        )
        if attendance_records:
            present_days = sum(1 for r in attendance_records if r["status"] in ("Present", "Late"))
            attendance_pct = f"{(present_days / len(attendance_records)) * 100:.1f}%"

    total_in_class = 0
    total_in_grade = 0
    if result.get("year") and result.get("term") and result.get("grade_snapshot"):
        total_in_grade_rec = one_row(
            "SELECT COUNT(*) AS cnt FROM result_sheets WHERE term = %s AND year = %s AND grade_snapshot = %s",
            [result["term"], result["year"], result["grade_snapshot"]]
        )
        total_in_grade = total_in_grade_rec["cnt"] if total_in_grade_rec else 0
        
        if result.get("class_stream_snapshot"):
            total_in_class_rec = one_row(
                "SELECT COUNT(*) AS cnt FROM result_sheets WHERE term = %s AND year = %s AND grade_snapshot = %s AND class_stream_snapshot = %s",
                [result["term"], result["year"], result["grade_snapshot"], result["class_stream_snapshot"]]
            )
            total_in_class = total_in_class_rec["cnt"] if total_in_class_rec else 0

    class_pos_str = f"{result.get('class_position') or '-'} of {total_in_class}" if result.get("class_position") and total_in_class > 0 else str(result.get("class_position") or "-")
    grade_pos_str = f"{result.get('grade_position') or '-'} of {total_in_grade}" if result.get("grade_position") and total_in_grade > 0 else str(result.get("grade_position") or "-")
    published_date, published_time = published_date_time(result.get("published_at") or result.get("updated_at") or now_text())
    verification_id = f"RES-{result.get('year')}-{int(result.get('result_id') or 0):06d}"
    verify_url = result_verify_url(request, result.get("result_id"))

    logo_path = official_logo_path(settings)
    logo = Image(logo_path, width=29 * mm, height=29 * mm) if logo_path else p("")
    school_name = (settings.get("school_name") or "RAYDON HIGH SCHOOL").upper()
    header_text = [
        p(school_name, title_style),
        p(settings.get("school_motto") or "Knowledge • Discipline • Excellence", motto_style),
        Spacer(1, 2),
        p(settings.get("school_address") or "School Address", small_style),
        p(school_contact_line(settings), small_style),
    ]

    slip_box = Table([
        [html("<b>RESULT SLIP</b>", white_style), ""],
        [p("Academic Year:", label_style), p(result.get("year") or "-")],
        [p("Term:", label_style), html(f"<b>{escape(str(result.get('term') or '-')).upper()}</b>", value_style)],
        [p("Date Published:", label_style), p(f"{published_date}, {published_time}")],
        [p("Admission No:", label_style), p(pupil.get("admission_no") or "-")],
    ], colWidths=[28 * mm, 37 * mm])
    slip_box.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BOX", (0, 0), (-1, -1), 0.8, navy),
        ("INNERGRID", (0, 1), (-1, -1), 0.25, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    header = Table([[logo, header_text, slip_box]], colWidths=[32 * mm, 92 * mm, 66 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    class_label = compact_class_label(
        grade_name=result.get("grade_snapshot"),
        class_name=result.get("class_stream_snapshot"),
        grade=pupil.get("grade"),
        stream=pupil.get("class_stream"),
        grade_id=pupil.get("grade_id"),
    ) or f"{result.get('grade_snapshot') or ''} {result.get('class_stream_snapshot') or ''}".strip() or "-"
    student_photo = p("")
    photo_path = ensure_student_photo(pupil)
    if photo_path:
        photo_file = os.path.join(django_settings.MEDIA_ROOT, photo_path)
        if os.path.exists(photo_file):
            student_photo = Image(photo_file, width=24 * mm, height=31 * mm)
    age_text = student_age_text(pupil.get("date_of_birth")) or "-"
    student_info = [
        [p("Student Name:", label_style), p(f"{pupil.get('first_name') or ''} {pupil.get('surname') or ''}".strip()), p("Stream:", label_style), p(pupil.get("stream") or "Ordinary Level"), p("Position In Class:", label_style), p(class_pos_str)],
        [p("Gender:", label_style), p(pupil.get("gender") or "-"), p("House:", label_style), p(pupil.get("house") or "-"), p("Position In Grade:", label_style), p(grade_pos_str)],
        [p("Class:", label_style), p(class_label), p("Age:", label_style), p(age_text), p("Attendance:", label_style), p(attendance_pct)],
    ]
    student_table = Table(student_info, colWidths=[26 * mm, 47 * mm, 24 * mm, 43 * mm, 32 * mm, 18 * mm])
    student_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, navy),
        ("INNERGRID", (0, 0), (-1, -1), 0.2, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    student_table = Table([[student_photo, student_table]], colWidths=[28 * mm, 162 * mm])
    student_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    table_data = [[
        html("<b>SUBJECT</b>", white_style),
        html("<b>TEACHER</b>", white_style),
        html("<b>MARK (%)</b>", white_style),
        html("<b>GRADE</b>", white_style),
        html("<b>COMMENT</b>", white_style),
    ]]

    best_subject = "-"
    best_mark = -1.0
    weakest_subject = "-"
    weakest_mark = 101.0

    class_id = pupil.get("class_id")

    for entry in entries:
        subj_name = entry.get("subject_name") or str(entry.get("subject_id"))
        try:
            mark = float(entry.get("mark", 0))
        except (TypeError, ValueError):
            mark = 0.0
        if mark > best_mark:
            best_mark = mark
            best_subject = f"{subj_name} ({mark:g}%)"
        if mark < weakest_mark:
            weakest_mark = mark
            weakest_subject = f"{subj_name} ({mark:g}%)"

        teacher_name = "-"
        if class_id and entry.get("subject_id"):
            teacher_rec = one_row(
                """
                SELECT teacher_name
                FROM class_timetable_entries
                WHERE class_id = %s AND subject_id = %s AND academic_year = %s
                  AND COALESCE(teacher_name, '') != ''
                ORDER BY day_order, period_no
                LIMIT 1
                """,
                [class_id, entry["subject_id"], result.get("year") or 2026],
            )
            if teacher_rec:
                teacher_name = teacher_rec["teacher_name"]

        table_data.append([
            p(subj_name),
            p(teacher_name, center_style),
            p(f"{mark:g}", center_style),
            p(entry.get("grade") or "-", center_style),
            p(entry.get("subject_comment") or "-"),
        ])

    if best_mark == -1.0: best_subject = "-"
    if weakest_mark == 101.0: weakest_subject = "-"

    marks_table = Table(table_data, colWidths=[30 * mm, 26 * mm, 16 * mm, 14 * mm, 26 * mm], repeatRows=1)
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, border),
        ('BOX', (0, 0), (-1, -1), 0.8, navy),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4.5),
    ])
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f7fbff'))
        else:
            t_style.add('BACKGROUND', (0, i), (-1, i), colors.white)
    marks_table.setStyle(t_style)

    avg = float(result.get('average_mark', 0))
    if avg >= 80:
        auto_remarks = "Outstanding Performance"
    elif avg >= 70:
        auto_remarks = "Very Good Performance"
    elif avg >= 60:
        auto_remarks = "Good Performance"
    elif avg >= 50:
        auto_remarks = "Fair Performance"
    else:
        auto_remarks = "Needs Improvement"
    total_marks = float(result.get("total_marks") or 0)
    max_marks = len(entries) * 100
    summary = [
        [html("<b>PERFORMANCE SUMMARY</b>", white_style), ""],
        [p("Total Marks:", label_style), p(f"{total_marks:g} / {max_marks or '-'}")],
        [p("Average (%):", label_style), p(f"{avg:.2f}")],
        [p("Grade Average:", label_style), p(calculate_grade(avg))],
        [p("Best Subject:", label_style), p(best_subject)],
        [p("Worst Subject:", label_style), p(weakest_subject)],
        [p("Remark:", label_style), p(auto_remarks)],
    ]
    summary_table = Table(summary, colWidths=[30 * mm, 46 * mm])
    summary_table.setStyle(TableStyle([
        ("SPAN", (0, 0), (-1, 0)),
        ("BACKGROUND", (0, 0), (-1, 0), navy),
        ("BOX", (0, 0), (-1, -1), 0.7, navy),
        ("INNERGRID", (0, 1), (-1, -1), 0.25, border),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    marks_summary = Table([[marks_table, summary_table]], colWidths=[112 * mm, 78 * mm])
    marks_summary.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    class_teacher_name = "-"
    if class_id:
        class_rec = one_row("SELECT * FROM classes WHERE class_id = %s", [class_id])
        if class_rec:
            class_teacher_name = class_rec.get("class_teacher") or "-"
    qr = qr_flowable(verify_url, size_mm=27)
    teacher_block = [
        html("<b>CLASS TEACHER</b>", label_style),
        p(class_teacher_name),
        Spacer(1, 8),
        p("Signature: ____________________", value_style),
        p(f"Date: {published_date}", value_style),
    ]
    headmaster_block = [
        html("<b>PRINCIPAL / HEADMASTER</b>", label_style),
        p(settings.get("headmaster_name") or "Headmaster"),
        Spacer(1, 8),
        p("Signature: ____________________", value_style),
        p(f"Date: {published_date}", value_style),
    ]
    date_block = [
        html("<b>PUBLISHED DATE</b>", label_style),
        p(published_date),
        p(published_time),
        Spacer(1, 5),
        p("Result published and approved on the date and time shown above."),
    ]
    stamp_drawing = create_reportlab_stamp(
        school_name=school_name,
        date_str=published_date,
        time_str=published_time,
        term_str=result.get('term') or 'TERM',
        year_str=str(result.get('year') or ''),
        status_str="VERIFIED RESULT",
        stamp_color=NAVY
    )
    stamp_block = [
        html("<b>ELECTRONIC DATE STAMP</b>", center_style),
        Spacer(1, 5),
        stamp_drawing,
    ]
    qr_block = [html("<b>VERIFY RESULT</b>", center_style), Spacer(1, 4)]
    if qr:
        qr_block.append(qr)
    qr_block.extend([p("Scan to verify authenticity", center_style), html(f"<b>VERIFICATION ID:</b><br/>{verification_id}", center_style)])
    sig_data = [
        [teacher_block, headmaster_block, date_block, stamp_block, qr_block]
    ]
    sig_table = Table(sig_data, colWidths=[38 * mm, 38 * mm, 35 * mm, 40 * mm, 39 * mm])
    sig_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, border),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, border),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )

    footer = Table([[html(f"This result slip is a computer generated document. Any alteration or tampering is illegal. Verify at https://{escape(school_website(settings))}/results/verify/{result.get('result_id')}", center_style)]], colWidths=[190 * mm])
    footer.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5fbff")),
        ("BOX", (0, 0), (-1, -1), 0.4, border),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story = [header, Spacer(1, 6), student_table, Spacer(1, 7), marks_summary, Spacer(1, 8), sig_table, Spacer(1, 8), footer]

    document.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="result-slip-{result.get("result_id")}.pdf"'
    return response


@permission_required("results.manage")
def result_new(request):
    from django.shortcuts import render, redirect
    from school_system_django.native import school_settings, insert_record, now_text, today_text, one_row, current_user_role
    from django.contrib import messages
    from accounts.permissions import assigned_classes_for_teacher, ROLE_TEACHER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT

    role = current_user_role(request.user)
    if role not in {ROLE_TEACHER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT}:
        messages.error(request, "Only academic staff can enter or modify results.")
        return redirect("/results")

    allowed_class_ids = assigned_classes_for_teacher(request.user)
    if not allowed_class_ids:
        messages.error(request, "You are not assigned as a class teacher to any class.")
        return redirect("/results")

    settings = school_settings()
    curr_term = settings.get("current_term") or "Term 1"
    curr_year = int(settings.get("current_year") or today_text()[:4])

    if request.method == "POST":
        pupil_id = request.POST.get("pupil_id")
        term = request.POST.get("term")
        year = request.POST.get("year")
        teacher_comment = request.POST.get("teacher_comment") or ""

        # Validate term and year
        if term != curr_term or int(year) != curr_year:
            messages.error(request, f"You can only enter results for the current term ({curr_term} {curr_year}).")
            return redirect("/results")

        # Check if student exists
        pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil_id])
        if not pupil:
            messages.error(request, "Student not found.")
            return redirect("/results")

        # Check class
        if pupil.get("class_id") not in allowed_class_ids:
            messages.error(request, "You can only enter results for students in your assigned class.")
            return redirect("/results")

        # Check if result sheet already exists for pupil, term, year
        exists = one_row("SELECT result_id FROM result_sheets WHERE pupil_id = %s AND term = %s AND year = %s", [pupil_id, term, year])
        if exists:
            messages.warning(request, f"Result sheet already exists for this student for {term} {year}. Editing instead.")
            return redirect(f"/results/{exists['result_id']}/edit")

        # Insert result sheet with snapshotted class and stream
        data = {
            "pupil_id": int(pupil_id),
            "term": term,
            "year": int(year),
            "status": "Draft",
            "total_marks": 0.0,
            "average_mark": 0.0,
            "teacher_comment": teacher_comment,
            "grade_snapshot": pupil.get("grade"),
            "class_stream_snapshot": pupil.get("class_stream"),
            "created_at": now_text(),
            "updated_at": now_text(),
        }

        try:
            result_id = insert_record(request, "result_sheets", data)
            if not result_id:
                created = one_row("SELECT result_id FROM result_sheets WHERE pupil_id = %s AND term = %s AND year = %s", [pupil_id, term, year])
                result_id = created["result_id"] if created else None
            from school_system_django.native import audit_action
            audit_action(request, "Create Results Sheet", f"Created results sheet {result_id} for student ID {pupil_id} (Term: {term}, Year: {year})")
            messages.success(request, "Result sheet created. Please enter subject marks below.")
            return redirect(f"/results/{result_id}/edit")
        except Exception as exc:
            messages.error(request, f"Could not create result sheet: {exc}")

    return render(
        request,
        "exams/result_form.html",
        {
            "title": "New Result Sheet",
            "subtitle": "Select a student to start entering marks.",
            "is_new": True,
            "current_term": curr_term,
            "current_year": curr_year,
        }
    )


@permission_required("results.manage")
def result_edit(request, result_id):
    from django.shortcuts import render, redirect
    from school_system_django.native import one_row, dict_rows, now_text, current_user_role, school_settings, today_text
    from django.db import connection
    from django.contrib import messages
    from accounts.permissions import assigned_classes_for_teacher, ROLE_TEACHER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT

    role = current_user_role(request.user)
    if role not in {ROLE_TEACHER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT}:
        messages.error(request, "Only academic staff can enter or modify results.")
        return redirect("/results")

    allowed_class_ids = assigned_classes_for_teacher(request.user)
    if not allowed_class_ids:
        messages.error(request, "You are not assigned as a class teacher to any class.")
        return redirect("/results")

    result = one_row("SELECT * FROM result_sheets WHERE result_id = %s", [result_id])
    if not result:
        messages.error(request, "Result sheet not found.")
        return redirect("/results")
    
    if result["status"] == "Published":
        messages.error(request, "This result sheet has been finalized and published. It cannot be modified.")
        return redirect(f"/results/{result_id}")

    settings = school_settings()
    curr_term = settings.get("current_term") or "Term 1"
    curr_year = int(settings.get("current_year") or today_text()[:4])

    # Validate term and year
    if result["term"] != curr_term or int(result["year"]) != curr_year:
        messages.error(request, f"You can only modify results for the current term ({curr_term} {curr_year}).")
        return redirect("/results")

    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [result["pupil_id"]])
    if not pupil or pupil.get("class_id") not in allowed_class_ids:
        messages.error(request, "You can only enter results for students in your assigned class.")
        return redirect("/results")

    # Get only subjects student is registered for matching their grade snapshot
    subjects = dict_rows(
        """
        SELECT s.subject_id, s.subject_code, s.subject_name, e.mark, e.grade, e.subject_comment
        FROM subjects s
        JOIN student_subjects ss ON ss.subject_id = s.subject_id AND ss.pupil_id = %s AND ss.academic_year = %s
        LEFT JOIN result_entries e ON e.subject_id = s.subject_id AND e.result_id = %s
        WHERE s.status = 'Active' AND (s.grade = 'All Forms' OR s.grade = %s)
        ORDER BY s.display_order, s.subject_name
        """,
        [pupil["pupil_id"], curr_year, result_id, result["grade_snapshot"]]
    )

    if request.method == "POST":
        teacher_comment = request.POST.get("teacher_comment") or ""
        marks_updated = 0
        total_marks = 0.0
        subject_count = 0

        # Perform server-side validations first
        for sub in subjects:
            input_name = f"subject_{sub['subject_id']}"
            mark_val = request.POST.get(input_name)
            if mark_val != "" and mark_val is not None:
                # Check student subject registration
                is_reg = one_row(
                    "SELECT 1 FROM student_subjects WHERE pupil_id = %s AND subject_id = %s AND academic_year = %s LIMIT 1",
                    [pupil["pupil_id"], sub["subject_id"], curr_year]
                )
                if not is_reg:
                    messages.error(request, f"Student is not registered for subject {sub['subject_name']}.")
                    return redirect(request.path)
                    
                # Check teacher assignment (if teacher role)
                if role == ROLE_TEACHER:
                    from accounts.permissions import check_teacher_assignment_access
                    if not check_teacher_assignment_access(request.user, result["grade_snapshot"], result["class_stream_snapshot"], sub["subject_id"]):
                        messages.error(request, f"You are not assigned to teach {sub['subject_name']} to this class.")
                        return redirect(request.path)

        # We start a transaction to save marks and update result sheet
        with connection.cursor() as cursor:
            # First, clean existing entries for this result sheet to avoid duplicates
            cursor.execute("DELETE FROM result_entries WHERE result_id = %s", [result_id])

            for sub in subjects:
                input_name = f"subject_{sub['subject_id']}"
                comment_name = f"comment_{sub['subject_id']}"
                mark_val = request.POST.get(input_name)
                subject_comment = request.POST.get(comment_name) or ""
                if mark_val != "" and mark_val is not None:
                    try:
                        mark = float(mark_val)
                        grade = calculate_grade(mark)
                        cursor.execute(
                            """
                            INSERT INTO result_entries (result_id, subject_id, mark, grade, subject_comment, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            [result_id, sub["subject_id"], mark, grade, subject_comment, now_text(), now_text()]
                        )
                        # Log change to audit trail if modified
                        if sub["mark"] is not None and float(sub["mark"]) != float(mark):
                            from school_system_django.native import audit_action
                            audit_action(
                                request,
                                "Edit Exam Mark",
                                f"Modified exam mark for student {pupil['admission_no']} in subject {sub['subject_name']} (ID: {sub['subject_id']}) on sheet {result_id}. Old: {sub['mark']}, New: {mark}."
                            )
                        total_marks += mark
                        subject_count += 1
                        marks_updated += 1
                    except ValueError:
                        pass

            average_mark = (total_marks / subject_count) if subject_count > 0 else 0.0

            # Update the ResultSheet record
            cursor.execute(
                """
                UPDATE result_sheets
                SET total_marks = %s, average_mark = %s, teacher_comment = %s, updated_at = %s
                WHERE result_id = %s
                """,
                [total_marks, average_mark, teacher_comment, now_text(), result_id]
            )

        # Recalculate Class/Grade positions
        recalculate_positions(result["term"], result["year"], result["grade_snapshot"])

        from school_system_django.native import audit_action
        audit_action(request, "Record subject marks", f"Recorded {marks_updated} subject marks for result sheet {result_id}")

        messages.success(request, f"Saved {marks_updated} subject marks. Positions recalculated.")
        return redirect(f"/results/{result_id}")

    return render(
        request,
        "exams/result_form.html",
        {
            "title": "Enter Subject Marks",
            "subtitle": f"Record exam marks for {pupil['first_name']} {pupil['surname']}.",
            "is_new": False,
            "pupil": pupil,
            "result": result,
            "subjects": subjects,
        }
    )


@login_required
def result_delete(request, result_id):
    from django.contrib import messages
    from django.shortcuts import redirect
    from school_system_django.native import one_row
    result = one_row("SELECT * FROM result_sheets WHERE result_id = %s", [result_id])
    if result and result["status"] == "Published":
        messages.error(request, "Published result sheets cannot be deleted.")
        return redirect(f"/results/{result_id}")
    if not user_has_permission(request.user, "results.publish"):
        messages.error(request, "Your role is not allowed to delete result sheets.")
        return redirect("accounts:dashboard")
    return delete_record(request, "Result Sheet", "result_sheets", "result_id", result_id, "/results")


@permission_required("results.publish")
def result_publish(request, result_id):
    return update_record_fields(
        request,
        "result_sheets",
        "result_id",
        result_id,
        {"status": "Published", "published_at": now_text(), "published_by": legacy_user_id(request)},
        "Result published.",
        "/results",
    )


@permission_required("results.manage")
def result_pupil_search(request):
    from school_system_django.native import current_user_role
    from accounts.permissions import assigned_classes_for_teacher

    q = (request.GET.get("q") or "").strip()
    rows = []
    if q:
        role = current_user_role(request.user)
        if role == "Teacher":
            allowed_class_ids = assigned_classes_for_teacher(request.user)
            if allowed_class_ids:
                placeholders = ", ".join(["%s"] * len(allowed_class_ids))
                rows = dict_rows(
                    f"""
                    SELECT pupil_id, admission_no, first_name, surname, grade, class_stream, grade_id, class_id, status
                    FROM pupils
                    WHERE (admission_no LIKE %s OR first_name LIKE %s OR surname LIKE %s)
                      AND class_id IN ({placeholders})
                    ORDER BY surname, first_name
                    LIMIT 20
                    """,
                    [f"%{q}%", f"%{q}%", f"%{q}%"] + allowed_class_ids,
                )
            else:
                rows = []
        else:
            rows = dict_rows(
                """
                SELECT pupil_id, admission_no, first_name, surname, grade, class_stream, grade_id, class_id, status
                FROM pupils
                WHERE admission_no LIKE %s OR first_name LIKE %s OR surname LIKE %s
                ORDER BY surname, first_name
                LIMIT 20
                """,
                [f"%{q}%", f"%{q}%", f"%{q}%"],
            )
    rows = hydrate_class_labels(rows)
    return JsonResponse({"results": rows})


@permission_required("results.manage")
def result_class_entry(request, tabbed=False):
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from school_system_django.native import school_settings, one_row, dict_rows, now_text, today_text, insert_record, current_user_role
    from django.db import connection
    from accounts.permissions import assigned_classes_for_teacher, ROLE_TEACHER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT

    role = current_user_role(request.user)
    if role not in {ROLE_TEACHER, ROLE_ADMIN, ROLE_SUPER_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT}:
        messages.error(request, "Only academic staff can enter or modify results.")
        return redirect("/results")

    if not tabbed:
        if request.method == "POST":
            return result_class_entry(request, tabbed=True)
        params = request.GET.urlencode()
        url = "/results?tab=entry"
        if params:
            url += f"&{params}"
        return redirect(url)

    allowed_class_ids = assigned_classes_for_teacher(request.user)
    
    if allowed_class_ids:
        placeholders = ", ".join(["%s"] * len(allowed_class_ids))
        classes = dict_rows(
            f"SELECT class_id, class_name, academic_year, grade_id FROM classes WHERE class_id IN ({placeholders}) ORDER BY academic_year DESC, class_name",
            allowed_class_ids
        )
        for c in classes:
            g = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [c["grade_id"]])
            c["grade_name"] = g["grade_name"] if g else ""
    else:
        classes = []

    settings = school_settings()
    curr_term = settings.get("current_term") or "Term 1"
    curr_year = str(settings.get("current_year", 2026))

    years = [int(curr_year)]

    selected_class_id = request.GET.get("class_id") or request.POST.get("class_id")
    selected_subject_id = request.GET.get("subject_id") or request.POST.get("subject_id")
    selected_term = curr_term
    selected_year = curr_year

    selected_class = None
    selected_subject = None
    students_with_marks = []
    grade_name = ""

    # Filter subjects by selected class grade name
    subjects = []
    if selected_class_id:
        selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [selected_class_id])
        if selected_class:
            grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class["grade_id"]])
            grade_name = grade_rec["grade_name"] if grade_rec else ""
            if grade_name:
                subjects = dict_rows(
                    "SELECT subject_id, subject_code, subject_name, grade FROM subjects WHERE status = 'Active' AND (grade = 'All Forms' OR grade = %s) ORDER BY display_order, subject_name",
                    [grade_name]
                )
    if not subjects:
        subjects = dict_rows("SELECT subject_id, subject_code, subject_name, grade FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")

    if selected_class_id and selected_subject_id:
        if allowed_class_ids and int(selected_class_id) not in allowed_class_ids:
            messages.error(request, "You are not assigned to manage results for this class.")
            return redirect("/results?tab=entry")

        selected_subject = one_row("SELECT * FROM subjects WHERE subject_id = %s", [selected_subject_id])

        if selected_class and selected_subject:
            class_students = active_pupils_for_class(
                selected_class,
                grade_name,
                select_fields="pupil_id, admission_no, first_name, surname, gender",
            )
            pupil_ids = [student["pupil_id"] for student in class_students]
            if pupil_ids:
                placeholders = ", ".join(["%s"] * len(pupil_ids))
                students = dict_rows(
                    f"""
                    SELECT DISTINCT p.pupil_id, p.admission_no, p.first_name, p.surname, p.gender
                    FROM pupils p
                    JOIN student_subjects ss ON ss.pupil_id = p.pupil_id
                    WHERE p.pupil_id IN ({placeholders})
                      AND ss.subject_id = %s
                      AND ss.academic_year = %s
                    ORDER BY p.surname, p.first_name
                    """,
                    pupil_ids + [selected_subject_id, int(selected_year)]
                )
            else:
                students = []

            for s in students:
                sheet = one_row(
                    "SELECT result_id FROM result_sheets WHERE pupil_id = %s AND term = %s AND year = %s",
                    [s["pupil_id"], selected_term, selected_year]
                )
                current_mark = None
                current_comment = ""
                if sheet:
                    entry = one_row(
                        "SELECT mark, subject_comment FROM result_entries WHERE result_id = %s AND subject_id = %s",
                        [sheet["result_id"], selected_subject_id]
                    )
                    if entry:
                        current_mark = entry["mark"]
                        current_comment = entry.get("subject_comment") or ""
                
                students_with_marks.append({
                    "pupil_id": s["pupil_id"],
                    "admission_no": s["admission_no"],
                    "first_name": s["first_name"],
                    "surname": s["surname"],
                    "gender": s["gender"],
                    "current_mark": current_mark,
                    "current_comment": current_comment,
                })

    if request.method == "POST" and selected_class_id and selected_subject_id:
        # Check teacher assignment allocation first
        if role == ROLE_TEACHER:
            from accounts.permissions import check_teacher_assignment_access
            if not check_teacher_assignment_access(request.user, grade_name, selected_class["class_name"], selected_subject_id):
                messages.error(request, "You are not assigned to enter marks for this subject and class.")
                return redirect(f"/results?tab=entry&class_id={selected_class_id}&subject_id={selected_subject_id}&term={selected_term}&year={selected_year}")
                
        saved_count = 0
        invalid_marks = []
        with connection.cursor() as cursor:
            for item in students_with_marks:
                input_name = f"mark_{item['pupil_id']}"
                comment_name = f"comment_{item['pupil_id']}"
                mark_val = request.POST.get(input_name)
                comment_val = request.POST.get(comment_name) or ""
                
                # Check student subject registration
                is_reg = one_row(
                    "SELECT 1 FROM student_subjects WHERE pupil_id = %s AND subject_id = %s AND academic_year = %s LIMIT 1",
                    [item["pupil_id"], selected_subject_id, int(selected_year)]
                )
                if not is_reg:
                    invalid_marks.append(f"{item['first_name']} {item['surname']} (Not registered)")
                    continue
                
                sheet = one_row(
                    "SELECT result_id FROM result_sheets WHERE pupil_id = %s AND term = %s AND year = %s",
                    [item["pupil_id"], selected_term, selected_year]
                )
                
                if sheet:
                    result_id = sheet["result_id"]
                else:
                    cursor.execute(
                        """
                        INSERT INTO result_sheets (pupil_id, term, year, status, total_marks, average_mark, teacher_comment, grade_snapshot, class_stream_snapshot, created_at, updated_at)
                        VALUES (%s, %s, %s, 'Draft', 0.0, 0.0, '', %s, %s, %s, %s)
                        """,
                        [item["pupil_id"], selected_term, int(selected_year), grade_name, selected_class.get("class_name"), now_text(), now_text()]
                    )
                    result_id = getattr(cursor, "lastrowid", None)
                    if not result_id:
                        created = one_row("SELECT result_id FROM result_sheets WHERE pupil_id = %s AND term = %s AND year = %s", [item["pupil_id"], selected_term, selected_year])
                        result_id = created["result_id"] if created else None

                if result_id:
                    if mark_val != "" and mark_val is not None:
                        try:
                            mark = float(mark_val)
                            if mark < 0 or mark > 100:
                                raise ValueError
                        except (TypeError, ValueError):
                            invalid_marks.append(f"{item['first_name']} {item['surname']}")
                            continue

                        grade = calculate_grade(mark)
                        
                        # Fetch old mark for auditing
                        old_entry = one_row("SELECT mark FROM result_entries WHERE result_id = %s AND subject_id = %s", [result_id, selected_subject_id])
                        old_mark = old_entry["mark"] if old_entry else None
                        
                        cursor.execute("DELETE FROM result_entries WHERE result_id = %s AND subject_id = %s", [result_id, selected_subject_id])
                        cursor.execute(
                            """
                            INSERT INTO result_entries (result_id, subject_id, mark, grade, subject_comment, created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            [result_id, selected_subject_id, mark, grade, comment_val, now_text(), now_text()]
                        )
                        
                        # Log changes to audit trail
                        if old_mark is not None and float(old_mark) != float(mark):
                            from school_system_django.native import audit_action
                            audit_action(
                                request,
                                "Edit Exam Mark",
                                f"Modified exam mark for student {item['admission_no']} in subject ID {selected_subject_id} on sheet {result_id}. Old: {old_mark}, New: {mark}."
                            )
                        saved_count += 1
                    else:
                        cursor.execute("DELETE FROM result_entries WHERE result_id = %s AND subject_id = %s", [result_id, selected_subject_id])

                    cursor.execute("SELECT mark FROM result_entries WHERE result_id = %s", [result_id])
                    entries = cursor.fetchall()
                    if entries:
                        total_marks = sum(e[0] for e in entries)
                        average_mark = total_marks / len(entries)
                    else:
                        total_marks = 0.0
                        average_mark = 0.0
                        
                    cursor.execute(
                        "UPDATE result_sheets SET total_marks = %s, average_mark = %s, updated_at = %s WHERE result_id = %s",
                        [total_marks, average_mark, now_text(), result_id]
                    )

        if selected_class:
            grade_rec = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class["grade_id"]])
            grade_name = grade_rec["grade_name"] if grade_rec else ""
            if grade_name:
                recalculate_positions(selected_term, int(selected_year), grade_name)

        if invalid_marks:
            messages.error(request, f"Skipped invalid marks for: {', '.join(invalid_marks[:5])}. Marks must be between 0 and 100.")
        messages.success(request, f"Exam marks saved for {saved_count} student(s).")
        return redirect(f"/results?tab=entry&class_id={selected_class_id}&subject_id={selected_subject_id}&term={selected_term}&year={selected_year}")

    tabs = extra_context_tabs("entry")
    context = {
        "classes": classes,
        "subjects": subjects,
        "years": years,
        "selected_class_id": selected_class_id,
        "selected_subject_id": selected_subject_id,
        "selected_term": selected_term,
        "selected_year": selected_year,
        "selected_class": selected_class,
        "selected_subject": selected_subject,
        "students_with_marks": students_with_marks,
        "settings": school_settings(),
        "tabs": tabs,
        "active_tab": "entry",
    }
    return render(request, "exams/class_result_form.html", context)


@permission_required("results.publish")
def result_bulk_publish(request, tabbed=False):
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from school_system_django.native import school_settings, one_row, dict_rows, today_text, now_text, legacy_user_id
    from django.db import connection

    if not tabbed:
        if request.method == "POST":
            return result_bulk_publish(request, tabbed=True)
        params = request.GET.urlencode()
        url = "/results?tab=publish"
        if params:
            url += f"&{params}"
        return redirect(url)

    classes = dict_rows("SELECT class_id, class_name, academic_year, grade_id FROM classes ORDER BY academic_year DESC, class_name")
    for c in classes:
        g = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [c["grade_id"]])
        c["grade_name"] = g["grade_name"] if g else ""

    years = [2026, 2025, 2024, 2023]
    selected_class_id = request.GET.get("class_id") or request.POST.get("class_id")
    selected_term = request.GET.get("term") or request.POST.get("term") or "Term 1"
    selected_year = request.GET.get("year") or request.POST.get("year") or str(school_settings().get("current_year", 2026))

    selected_class = None
    results_list = []
    drafts_count = 0
    published_count = 0

    if selected_class_id:
        selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [selected_class_id])
        if selected_class:
            g = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class["grade_id"]])
            selected_class["grade_name"] = g["grade_name"] if g else ""
            students = active_pupils_for_class(
                selected_class,
                selected_class["grade_name"],
                select_fields="pupil_id, admission_no, first_name, surname",
            )

            if students:
                pupil_ids = [student["pupil_id"] for student in students]
                placeholders = ", ".join(["%s"] * len(pupil_ids))
                results_list = dict_rows(
                    f"""
                    SELECT r.result_id, r.status, r.average_mark, r.class_position, p.admission_no, p.first_name, p.surname
                    FROM result_sheets r
                    JOIN pupils p ON p.pupil_id = r.pupil_id
                    WHERE r.term = %s AND r.year = %s AND r.pupil_id IN ({placeholders})
                    ORDER BY p.first_name, p.surname
                    """,
                    [selected_term, selected_year] + pupil_ids
                )

            drafts_count = sum(1 for r in results_list if r["status"] == "Draft")
            published_count = sum(1 for r in results_list if r["status"] == "Published")

    if request.method == "POST" and selected_class:
        students = active_pupils_for_class(
            selected_class,
            selected_class.get("grade_name") or "",
            select_fields="pupil_id",
        )
        pupil_ids = [student["pupil_id"] for student in students]
        if not pupil_ids:
            messages.error(request, "No active students were found for this class.")
            return redirect(f"/results?tab=publish&class_id={selected_class_id}&term={selected_term}&year={selected_year}")
        placeholders = ", ".join(["%s"] * len(pupil_ids))
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE result_sheets
                SET status = 'Published', published_at = %s, published_by = %s
                WHERE term = %s AND year = %s AND status = 'Draft' AND pupil_id IN ({placeholders})
                """,
                    [now_text(), legacy_user_id(request), selected_term, int(selected_year)] + pupil_ids
            )
            rows_updated = cursor.rowcount

        from school_system_django.native import audit_action
        audit_action(request, "Bulk Publish Results", f"Published {rows_updated} results for {selected_class['grade_name']} {selected_class['class_name']} (Term: {selected_term}, Year: {selected_year})")
        messages.success(request, f"Successfully published {rows_updated} result sheet(s).")
        return redirect(f"/results?tab=publish&class_id={selected_class_id}&term={selected_term}&year={selected_year}")

    tabs = extra_context_tabs("publish")
    context = {
        "classes": classes,
        "years": years,
        "selected_class_id": selected_class_id,
        "selected_term": selected_term,
        "selected_year": selected_year,
        "selected_class": selected_class,
        "results_list": results_list,
        "drafts_count": drafts_count,
        "published_count": published_count,
        "settings": school_settings(),
        "tabs": tabs,
        "active_tab": "publish",
    }
    return render(request, "exams/bulk_publish_form.html", context)


@permission_required("results.publish")
def publish_all_pending(request):
    from django.shortcuts import redirect
    from django.contrib import messages
    from school_system_django.native import school_settings, now_text, legacy_user_id
    from django.db import connection

    settings = school_settings()
    curr_term = settings.get("current_term") or "Term 1"
    curr_year = settings.get("current_year") or 2026

    with connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE result_sheets
            SET status = 'Published', published_at = %s, published_by = %s
            WHERE term = %s AND year = %s AND status = 'Draft'
            """,
            [now_text(), legacy_user_id(request), curr_term, int(curr_year)]
        )
        rows_updated = cursor.rowcount

    from school_system_django.native import audit_action
    audit_action(request, "Publish All Pending Results", f"Published all {rows_updated} pending results for {curr_term} {curr_year}")
    messages.success(request, f"Successfully published {rows_updated} result sheet(s) for {curr_term} {curr_year}.")
    return redirect("/results?tab=publish")


# Create your views here.


def results_verify(request, result_id):
    from school_system_django.native import one_row, dict_rows, school_settings
    from django.shortcuts import render
    
    result = one_row("SELECT * FROM result_sheets WHERE result_id = %s AND status = 'Published'", [result_id])
    if not result:
        return render(request, "exams/verify.html", {"verified": False, "message": "Result slip could not be verified or is not published.", "settings": school_settings()})
        
    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [result["pupil_id"]])
    entries = dict_rows(
        "SELECT s.subject_name, s.subject_code, e.mark, e.grade, e.subject_comment FROM result_entries e LEFT JOIN subjects s ON s.subject_id = e.subject_id WHERE e.result_id = %s ORDER BY s.display_order, s.subject_name",
        [result_id],
    )
    
    # Calculate attendance
    attendance_pct = "100.0%"
    if pupil:
        attendance_records = dict_rows(
            "SELECT status FROM attendance_records WHERE pupil_id = %s AND attendance_date LIKE %s",
            [pupil["pupil_id"], f"{result.get('year') or 2026}-%"]
        )
        if attendance_records:
            present_days = sum(1 for r in attendance_records if r["status"] == "Present")
            attendance_pct = f"{(present_days / len(attendance_records)) * 100:.1f}%"
            
    # Remarks
    avg = float(result.get("average_mark", 0))
    if avg >= 80:
        remarks = "Outstanding"
    elif avg >= 70:
        remarks = "Excellent"
    elif avg >= 60:
        remarks = "Good"
    elif avg >= 50:
        remarks = "Fair"
    else:
        remarks = "Needs Improvement"
        
    return render(
        request, 
        "exams/verify.html", 
        {
            "verified": True, 
            "result": result, 
            "pupil": pupil, 
            "entries": entries, 
            "attendance_pct": attendance_pct,
            "remarks": remarks,
            "settings": school_settings()
        }
    )
