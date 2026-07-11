from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date

from accounts.permissions import permission_required, user_has_permission
from academics.library_services import (
    RETURNED_STATUSES,
    available_copies_for_issue,
    book_from_loan,
    book_options,
    sync_book_availability,
    textbook_has_book_id,
)
from fees.services import auto_bill_student_for_current_term, next_admission_no, payment_history, pupil_by_identifier, student_financial_summary
from students.services import (
    A_LEVEL_START_GRADE,
    O_LEVEL_COMPLETED_GRADE,
    PERMANENT_ARCHIVE_STATUS,
    PENDING_ZIMSEC_STATUS,
    academic_level_for_pupil,
    archive_pupil,
    delete_student_photo,
    display_grade_label,
    ensure_student_photo,
    grade_label_for_number,
    grade_number,
    grade_row_for_number,
    pending_zimsec_is_mature,
    reactivate_for_a_level,
    save_student_photo,
    school_finish_date,
    student_age_text,
    student_photo_url,
)
from school_system_django.native import (
    audit_action,
    delete_record,
    compact_class_label,
    dict_rows,
    hydrate_class_labels,
    insert_record,
    legacy_user_id,
    now_text,
    one_row,
    render_rows_page,
    render_detail_page,
    render_record_form_page,
    render_table_page,
    resolve_legacy_class_record,
    simple_pdf,
    school_settings,
    today_text,
    update_record,
    update_record_fields,
)


PUPIL_FIELDS = [
    "first_name",
    "surname",
    "gender",
    "date_of_birth",
    "grade",
    "class_stream",
    "guardian_name",
    "guardian_phone",
    "address",
    "admission_date",
    "status",
    "medical_notes",
    "grade_id",
    "class_id",
    "guardian_id",
    "remarks",
    "photo_path",
    "national_id",
]

TEXTBOOK_FIELDS = [
    "pupil_id",
    "book_name",
    "borrowed_date",
    "return_date",
    "status",
    "notes",
]


def student_form_fields(values=None, readonly_admission=False):
    values = values or {}
    field_defs = [
        {"name": "admission_no", "label": "Admission Number", "readonly": readonly_admission, "help_text": "Generated automatically in the format A26001, where 26 is the admission year."},
        {"name": "first_name", "label": "First Name", "required": True},
        {"name": "surname", "label": "Surname", "required": True},
        {"name": "gender", "label": "Gender", "widget": "select", "options": ["Male", "Female"], "required": True},
        {"name": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
        {"name": "national_id", "label": "National ID Number"},
        {"name": "grade", "label": "Form", "required": True},
        {"name": "class_stream", "label": "Stream", "required": True},
        {"name": "guardian_name", "label": "Parent/Guardian Name", "required": True},
        {"name": "guardian_phone", "label": "Parent/Guardian Phone", "required": True},
        {"name": "address", "label": "Address", "widget": "textarea"},
        {"name": "admission_date", "label": "Admission Date", "type": "date"},
        {"name": "status", "label": "Status", "widget": "select", "options": ["Active", "Inactive", PENDING_ZIMSEC_STATUS, PERMANENT_ARCHIVE_STATUS, "Transferred", "Withdrawn", "Suspended"]},
        {"name": "medical_notes", "label": "Medical Notes", "widget": "textarea"},
        {"name": "remarks", "label": "Remarks", "widget": "textarea"},
    ]
    fields = []
    for item in field_defs:
        field = dict(item)
        if field["name"] == "admission_date":
            field["value"] = values.get(field["name"]) or today_text()
        elif field["name"] == "status":
            field["value"] = values.get(field["name"]) or "Active"
        else:
            field["value"] = values.get(field["name"], "")
        fields.append(field)
    return fields


def posted_student_data(request, admission_no):
    data = {"admission_no": admission_no}
    for field in PUPIL_FIELDS:
        if field == "photo_path":
            continue
        value = (request.POST.get(field) or "").strip()
        data[field] = None if field in {"grade_id", "class_id", "guardian_id"} and not value else value
    data["admission_date"] = data.get("admission_date") or today_text()
    data["status"] = data.get("status") or "Active"
    uploaded_photo = request.FILES.get("photo_upload")
    if uploaded_photo:
        data["photo_path"] = save_student_photo(uploaded_photo, admission_no)
    return data


def enrich_student_display(pupil):
    if not pupil:
        return pupil
    age = student_age_text(pupil.get("date_of_birth"))
    return {
        **pupil,
        "age": age,
        "photo_path": "",
        "photo_url": "",
        "school_finish_date": school_finish_date(pupil),
    }


def student_from_ref(ref):
    pupil = pupil_by_identifier(ref)
    if pupil:
        return pupil
    return None


def _term_number_from_setting(value):
    text = str(value or "").strip()
    for number in (1, 2, 3):
        if text == str(number) or f"term {number}" in text.lower():
            return number
    return 1


def _enterprise_status_from_legacy_status(value):
    status = str(value or "").strip()
    mapping = {
        "Active": "Active Student",
        "Inactive": "Suspended",
        PENDING_ZIMSEC_STATUS: "Pending ZIMSEC Analysis",
        PERMANENT_ARCHIVE_STATUS: "Archived",
        "Transferred": "Withdrawn",
        "Withdrawn": "Withdrawn",
        "Suspended": "Suspended",
    }
    return mapping.get(status, "Active Student")


def _subject_level_for_form(form_label):
    form_num = grade_number(form_label)
    return "A_LEVEL" if form_num in (5, 6) else "O_LEVEL"


def _date_or_today(value):
    parsed = parse_date(str(value or ""))
    return parsed or parse_date(today_text())


def _ensure_enterprise_academic_context(form_label, stream_name, academic_year_value, term_value):
    from academic_structure.models import AcademicClass, AcademicTerm, AcademicYear, Form, Stream

    form_num = grade_number(form_label)
    year_number = int(academic_year_value)
    term_number = _term_number_from_setting(term_value)

    active_year_exists = AcademicYear.objects.filter(is_active=True).exists()
    academic_year, _ = AcademicYear.objects.get_or_create(
        year=year_number,
        defaults={"is_active": not active_year_exists},
    )

    form_obj, _ = Form.objects.get_or_create(
        form_number=form_num,
        defaults={"name": f"Form {form_num}"},
    )
    stream_obj, _ = Stream.objects.get_or_create(name=stream_name)

    active_term_exists = AcademicTerm.objects.filter(is_active=True).exists()
    academic_term, _ = AcademicTerm.objects.get_or_create(
        academic_year=academic_year,
        term_number=term_number,
        defaults={"is_active": not active_term_exists},
    )

    academic_class, _ = AcademicClass.objects.get_or_create(
        academic_year=academic_year,
        form=form_obj,
        stream=stream_obj,
        defaults={"max_capacity": 40},
    )
    academic_class.full_clean()
    return academic_year, academic_term, academic_class


def _ensure_enterprise_subject(legacy_subject, form_label):
    from subject_management.models import Subject

    raw_code = (legacy_subject.get("subject_code") or "").strip().upper()
    name = (legacy_subject.get("subject_name") or "").strip()
    level = _subject_level_for_form(form_label)
    if not raw_code or not name:
        raise ValueError("Subject code and name are required for enterprise subject sync.")

    by_name = Subject.objects.filter(name__iexact=name, level=level).first()
    if by_name:
        return by_name

    prefix = "AL" if level == "A_LEVEL" else "OL"
    normalized_code = raw_code if raw_code.startswith(f"{prefix}_") else f"{prefix}_{raw_code}"
    by_code = Subject.objects.filter(code=normalized_code).first()
    if by_code:
        return by_code

    subject, created = Subject.objects.get_or_create(
        code=normalized_code,
        defaults={
            "name": name,
            "level": level,
            "department": "Languages",
            "is_active": True,
        },
    )
    changed = False
    if subject.name != name:
        subject.name = name
        changed = True
    if not subject.is_active:
        subject.is_active = True
        changed = True
    if changed:
        subject.save()
    return subject


def sync_enterprise_student_registration(pupil, selected_subject_ids, academic_year_value, term_value=None):
    from student_registry.models import Guardian, Student
    from subject_management.models import StudentSubjectRegistration

    academic_year, academic_term, academic_class = _ensure_enterprise_academic_context(
        pupil.get("grade"),
        pupil.get("class_stream"),
        academic_year_value,
        term_value,
    )

    admission_date = _date_or_today(pupil.get("admission_date"))
    date_of_birth = _date_or_today(pupil.get("date_of_birth"))
    national_id = (pupil.get("national_id") or "").strip() or None

    student = Student.objects.filter(admission_no=pupil.get("admission_no")).first()
    if not student:
        student = Student(
            admission_no=pupil.get("admission_no"),
            first_name=pupil.get("first_name") or "",
            surname=pupil.get("surname") or "",
            gender=pupil.get("gender") or "",
            date_of_birth=date_of_birth,
            admission_date=admission_date,
            academic_class=academic_class,
            national_id=national_id,
            status=_enterprise_status_from_legacy_status(pupil.get("status")),
        )
    else:
        student.first_name = pupil.get("first_name") or student.first_name
        student.surname = pupil.get("surname") or student.surname
        student.gender = pupil.get("gender") or student.gender
        student.date_of_birth = date_of_birth or student.date_of_birth
        student.admission_date = admission_date or student.admission_date
        student.academic_class = academic_class
        student.national_id = national_id
        student.status = _enterprise_status_from_legacy_status(pupil.get("status"))
    student.save()

    guardian_name = (pupil.get("guardian_name") or "").strip()
    guardian_phone = (pupil.get("guardian_phone") or "").strip()
    if guardian_name and guardian_phone:
        student.guardians.exclude(full_name=guardian_name).update(is_primary=False)
        guardian, _ = Guardian.objects.get_or_create(
            student=student,
            full_name=guardian_name,
            defaults={
                "relationship": "Guardian",
                "phone_number": guardian_phone,
                "is_primary": True,
            },
        )
        guardian.relationship = guardian.relationship or "Guardian"
        guardian.phone_number = guardian_phone
        guardian.is_primary = True
        guardian.save()

    selected_subject_ids = [int(subject_id) for subject_id in selected_subject_ids]
    if selected_subject_ids:
        legacy_subjects = dict_rows(
            f"""
            SELECT subject_id, subject_code, subject_name
            FROM subjects
            WHERE subject_id IN ({",".join(["%s"] * len(selected_subject_ids))})
            """,
            selected_subject_ids,
        )
    else:
        legacy_subjects = []

    enterprise_subject_ids = []
    for legacy_subject in legacy_subjects:
        subject = _ensure_enterprise_subject(legacy_subject, pupil.get("grade"))
        enterprise_subject_ids.append(subject.id)
        StudentSubjectRegistration.objects.get_or_create(
            student=student,
            subject=subject,
            academic_year=academic_year,
            academic_term=academic_term,
        )

    StudentSubjectRegistration.objects.filter(
        student=student,
        academic_year=academic_year,
        academic_term=academic_term,
    ).exclude(subject_id__in=enterprise_subject_ids).delete()

    return student


def check_teacher_student_access(request, pupil):
    from school_system_django.native import current_user_role
    from accounts.permissions import assigned_classes_for_teacher
    
    role = current_user_role(request.user)
    if role == "Teacher":
        allowed_class_ids = assigned_classes_for_teacher(request.user)
        if not pupil or pupil.get("class_id") not in allowed_class_ids:
            return False
    return True



@permission_required("students.view")
def records(request):
    from school_system_django.native import current_user_role
    from accounts.permissions import assigned_classes_for_teacher

    role = current_user_role(request.user)
    where = None
    params = None
    if role == "Teacher":
        allowed_class_ids = assigned_classes_for_teacher(request.user)
        if allowed_class_ids:
            placeholders = ", ".join(["%s"] * len(allowed_class_ids))
            where = f"class_id IN ({placeholders})"
            params = allowed_class_ids
        else:
            where = "class_id = -1"
            params = []

    row_actions = [
        {"label": "View", "href": "/pupils/{admission_no}", "icon": "bi-eye", "class": "btn-outline-primary"},
    ]
    if user_has_permission(request.user, "students.manage"):
        row_actions.append({"label": "Edit", "href": "/pupils/{admission_no}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"})
        row_actions.append({"label": "Transition", "href": "/pupils/transition/{pupil_id}", "icon": "bi-arrow-right-short", "class": "btn-outline-warning"})
    if user_has_permission(request.user, "payments.record"):
        row_actions.append({"label": "Pay", "href": "/payments/new?admission_no={admission_no}", "icon": "bi-cash", "class": "btn-outline-success"})
    return render_table_page(
        request,
        "Student Records",
        "pupils",
        ["admission_no", "first_name", "surname", "age", "class_label", "guardian_name", "status"],
        "Search, filter, and review learner records.",
        order_by="surname, first_name",
        search_columns=["admission_no", "first_name", "surname", "guardian_name", "grade", "class_stream", "national_id"],
        filters=[
            {"name": "grade", "label": "Form"},
            {"name": "class_stream", "label": "Stream"},
            {"name": "status", "label": "Status"},
        ],
        where=where,
        params=params,
        pk_column="pupil_id",
        create_href="/pupils/register" if user_has_permission(request.user, "students.manage") else None,
        create_label="Register Student",
        row_actions=row_actions,
    )


@permission_required("students.manage")
def register(request):
    from school_system_django.native import school_settings, dict_rows, insert_record, one_row, audit_action
    from django.db import transaction
    
    settings = school_settings()
    current_year = settings.get("current_year") or 2026
    
    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        surname = (request.POST.get("surname") or "").strip()
        gender = (request.POST.get("gender") or "").strip()
        date_of_birth = (request.POST.get("date_of_birth") or "").strip()
        national_id = (request.POST.get("national_id") or "").strip()
        form_val = (request.POST.get("grade") or "").strip()
        stream_val = (request.POST.get("class_stream") or "").strip()
        guardian_name = (request.POST.get("guardian_name") or "").strip()
        guardian_phone = (request.POST.get("guardian_phone") or "").strip()
        address = (request.POST.get("address") or "").strip()
        medical_notes = (request.POST.get("medical_notes") or "").strip()
        remarks = (request.POST.get("remarks") or "").strip()
        admission_date = (request.POST.get("admission_date") or today_text()).strip()
        
        selected_subjects = request.POST.getlist("subjects")
        
        # 1. Server-side Form/Stream validation
        is_a_level = form_val in ["Form 5", "Form 6"]
        if is_a_level:
            if stream_val not in ["Arts", "Commercials", "Sciences"]:
                messages.error(request, f"Invalid stream selection '{stream_val}' for A Level ({form_val}). Allowed streams: Arts, Commercials, Sciences.")
                return redirect("/pupils/register/")
        else:
            if stream_val not in ["A", "B", "C"]:
                messages.error(request, f"Invalid stream selection '{stream_val}' for O Level ({form_val}). Allowed streams: A, B, C.")
                return redirect("/pupils/register/")
                
        # 2. Server-side Subject limits validation
        max_subjects = 5 if is_a_level else 10
        if not selected_subjects:
            messages.error(request, "Subject registration is mandatory. Please select at least 1 subject.")
            return redirect("/pupils/register/")
        if len(selected_subjects) > max_subjects:
            messages.error(request, f"Subject registration limit exceeded. For {form_val}, max registered subjects is {max_subjects}. Selected: {len(selected_subjects)}")
            return redirect("/pupils/register/")
            
        # 3. Generate unique Admission Number
        admission_no = next_admission_no(admission_date)
        
        # 4. Resolve grade_id and class_id
        grade_num = grade_number(form_val)
        class_rec = resolve_legacy_class_record(
            grade=form_val,
            stream=stream_val,
            grade_id=grade_num,
            academic_year=current_year,
        )
        class_id = class_rec["class_id"] if class_rec else None
        
        pupil_data = {
            "admission_no": admission_no,
            "first_name": first_name,
            "surname": surname,
            "gender": gender,
            "date_of_birth": date_of_birth,
            "grade": form_val,
            "class_stream": stream_val,
            "guardian_name": guardian_name,
            "guardian_phone": guardian_phone,
            "address": address,
            "admission_date": admission_date,
            "status": "Active",
            "medical_notes": medical_notes,
            "remarks": remarks,
            "grade_id": grade_num,
            "class_id": class_id,
            "photo_path": "",
            "national_id": national_id or None
        }
        
        try:
            with transaction.atomic():
                new_id = insert_record(request, "pupils", pupil_data)
                
                # Insert subject registrations
                from django.db import connection
                for sub_id in selected_subjects:
                    cursor = connection.cursor()
                    cursor.execute(
                        """
                        INSERT INTO student_subjects (pupil_id, subject_id, academic_year, form, stream)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [new_id, int(sub_id), current_year, form_val, stream_val]
                    )

                enterprise_pupil = {**pupil_data, "pupil_id": new_id}
                sync_enterprise_student_registration(
                    enterprise_pupil,
                    selected_subjects,
                    current_year,
                    settings.get("current_term"),
                )
                from parents.views import sync_guardians_from_pupils

                sync_guardians_from_pupils()
                
            # Log creations
            subject_names = []
            if selected_subjects:
                sub_rows = dict_rows(f"SELECT subject_name FROM subjects WHERE subject_id IN ({','.join(['%s']*len(selected_subjects))})", [int(x) for x in selected_subjects])
                subject_names = [s["subject_name"] for s in sub_rows]
                
            audit_action(request, "Register Student", f"Registered student {first_name} {surname} ({admission_no}). Subjects registered ({len(selected_subjects)}): {', '.join(subject_names)}")
            
            # Auto-billing
            pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [new_id])
            if pupil:
                billing = auto_bill_student_for_current_term(pupil)
                bill = billing["bill"]
                if bill:
                    messages.success(request, f"Student saved. Admission number {admission_no} generated. Auto-billed {billing['term']} {billing['year']}: USD {billing['amount']:,.2f}. Offer letter is ready for printing.")
                else:
                    messages.success(request, f"Student saved. Admission number {admission_no} generated. Offer letter is ready for printing.")
                    messages.info(request, f"Auto-billing skipped: No fee structure defined for grade '{pupil.get('grade')}' in {billing['term']} {billing['year']}.")
            else:
                messages.success(request, f"Student saved. Admission number {admission_no} generated. Offer letter is ready for printing.")
                
            return redirect(f"/pupils/{admission_no}")
        except Exception as exc:
            messages.error(request, f"Could not register student: {exc}")
            return redirect("/pupils/register/")
            
    # GET method
    master_subjects = dict_rows("SELECT * FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")
    return render(
        request,
        "students/register.html",
        {
            "master_subjects": master_subjects,
            "app_title": settings.get("school_name", "Raydon High School")
        }
    )


@permission_required("students.archive.view")
def completed(request):
    row_actions = [{"label": "View", "href": "/pupils/{admission_no}", "icon": "bi-eye", "class": "btn-outline-primary"}]
    if user_has_permission(request.user, "students.manage"):
        row_actions.append({"label": "Reactivate", "href": "/pupils/{admission_no}/status/activate", "icon": "bi-arrow-counterclockwise", "class": "btn-outline-success"})
        row_actions.append({"label": "Archive", "href": "/pupils/{admission_no}/status/archive", "icon": "bi-archive", "class": "btn-outline-danger"})
    return render_table_page(
        request,
        "Progression And Archive Database",
        "pupils",
        ["admission_no", "first_name", "surname", "national_id", "class_label", "academic_level", "status", "completed_on", "status_reason"],
        "Completed O Level, Completed A Level, Pending ZIMSEC Analysis, permanent archive, transfers, and reactivations.",
        order_by="completed_on DESC, surname, first_name",
        search_columns=["admission_no", "first_name", "surname", "completed_on", "grade", "status", "national_id"],
        where="COALESCE(status, 'Active') != 'Active'",
        filters=[
            {"name": "status", "label": "Status"},
            {"name": "grade", "label": "Academic Stage/Form"},
        ],
        pk_column="pupil_id",
        row_actions=row_actions,
    )


@permission_required("library.manage")
def textbooks(request):
    q = (request.GET.get("q") or "").strip()
    has_book_id = textbook_has_book_id()
    book_id_select = "tl.book_id" if has_book_id else "NULL AS book_id"
    book_join = "LEFT JOIN library_books lb ON lb.book_id = tl.book_id" if has_book_id else "LEFT JOIN library_books lb ON UPPER(TRIM(lb.title)) = UPPER(TRIM(tl.book_name))"
    clauses = []
    params = []
    if q:
        clauses.append(
            """
            (
                tl.book_name LIKE %s OR lb.title LIKE %s OR tl.status LIKE %s OR
                p.admission_no LIKE %s OR p.first_name LIKE %s OR p.surname LIKE %s
            )
            """
        )
        params.extend([f"%{q}%"] * 6)
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = dict_rows(
        f"""
        SELECT tl.loan_id, tl.pupil_id, {book_id_select}, COALESCE(lb.title, tl.book_name) AS book_name,
               tl.borrowed_date, tl.return_date, tl.status, tl.notes, tl.cleared_date,
               p.admission_no, p.first_name, p.surname, p.grade, p.class_stream, p.grade_id, p.class_id
        FROM textbook_loans tl
        LEFT JOIN pupils p ON p.pupil_id = tl.pupil_id
        {book_join}
        {where}
        ORDER BY tl.loan_id DESC
        """,
        params,
    )
    rows = hydrate_class_labels(rows)
    for row in rows:
        row["student_name"] = f"{row.get('first_name') or ''} {row.get('surname') or ''}".strip()
    return render_rows_page(
        request,
        "Textbook Loans",
        rows,
        ["admission_no", "student_name", "class_label", "book_name", "borrowed_date", "return_date", "status", "notes"],
        "Textbook issue, return, and clearance records.",
        actions=[{"label": "Issue Textbook", "href": "/textbook-loans/new", "icon": "bi-plus-circle"}],
        row_actions=[
            {"label": "Edit", "href": "/textbook-loans/{loan_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Return", "href": "/textbook-loans/{loan_id}/return", "icon": "bi-check2-circle", "class": "btn-outline-success", "method": "post", "confirm": "Mark this textbook as returned?"},
            {"label": "Delete", "href": "/textbook-loans/{loan_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this textbook loan?"},
        ],
        total=len(rows),
        page=1,
        per_page=max(len(rows), 10),
    )


def student_profile_pdf_response(pupil, summary):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.http import HttpResponse
    from school_system_django.native import school_settings
    from django.conf import settings as django_settings
    import os

    settings = school_settings()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=15 * mm, leftMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ProfileTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=colors.HexColor('#102a43'),
        alignment=0,
        spaceAfter=5
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

    from school_system_django.native import get_pdf_header
    story.append(get_pdf_header(settings, 180 * mm))
    story.append(Paragraph("<b>STUDENT PROFILE RECORD</b>", styles["Heading3"]))
    story.append(Spacer(1, 10))

    photo = None

    meta = [
        [Paragraph("Admission Number", label_style), Paragraph(pupil.get("admission_no") or "-", val_style)],
        [Paragraph("Full Name", label_style), Paragraph(f"{pupil.get('first_name')} {pupil.get('surname')}", val_style)],
        [Paragraph("Gender", label_style), Paragraph(pupil.get("gender") or "-", val_style)],
        [Paragraph("Date of Birth", label_style), Paragraph(pupil.get("date_of_birth") or "-", val_style)],
        [Paragraph("Age", label_style), Paragraph(pupil.get("age") or "-", val_style)],
        [Paragraph("Grade / Stream", label_style), Paragraph(compact_class_label(grade=pupil.get("grade"), stream=pupil.get("class_stream"), grade_id=pupil.get("grade_id")) or "-", val_style)],
        [Paragraph("Parent/Guardian", label_style), Paragraph(pupil.get("guardian_name") or "-", val_style)],
        [Paragraph("Parent/Guardian Phone", label_style), Paragraph(pupil.get("guardian_phone") or "-", val_style)],
        [Paragraph("Address", label_style), Paragraph(pupil.get("address") or "-", val_style)],
        [Paragraph("Admission Date", label_style), Paragraph(pupil.get("admission_date") or "-", val_style)],
        [Paragraph("Status", label_style), Paragraph(pupil.get("status") or "-", val_style)],
        [Paragraph("Medical Notes", label_style), Paragraph(pupil.get("medical_notes") or "-", val_style)],
        [Paragraph("Current Fees Balance", label_style), Paragraph(f"USD {float(summary.get('overall_balance') or 0):,.2f}", val_style)],
    ]

    meta_table = Table(meta, colWidths=[50 * mm, 120 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4f8")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9e2ec")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([meta_table, Spacer(1, 25)])
    story.append(Paragraph("Office Copy Stamp: ____________________    Date: ____________________", val_style))

    document.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="student-profile-{pupil["admission_no"]}.pdf"'
    return response


@permission_required("students.view")
def detail(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to view this student profile.")
        return redirect("/pupils")
    summary = student_financial_summary(pupil=pupil)
    pupil = enrich_student_display(pupil)
    
    # Query registered subjects
    settings = school_settings()
    current_year = settings.get("current_year") or 2026
    registered_subjects = dict_rows(
        """
        SELECT s.subject_id, s.subject_code, s.subject_name
        FROM student_subjects ss
        JOIN subjects s ON s.subject_id = ss.subject_id
        WHERE ss.pupil_id = %s AND ss.academic_year = %s
        ORDER BY s.display_order, s.subject_name
        """,
        [pupil["pupil_id"], current_year]
    )
    
    if request.GET.get("format") == "pdf" or request.path.endswith("/print"):
        return student_profile_pdf_response(pupil, summary)
    return render(request, "students/student_profile.html", {
        "pupil": pupil, 
        "summary": summary,
        "registered_subjects": registered_subjects
    })


@permission_required("students.manage")
def edit(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to manage this student.")
        return redirect("/pupils")
    fields = student_form_fields(pupil, readonly_admission=True)
    if request.method == "POST":
        try:
            data = posted_student_data(request, pupil["admission_no"])
            
            # Form and Stream validation
            form_val = data.get("grade")
            stream_val = data.get("class_stream")
            
            is_a_level = form_val in ["Form 5", "Form 6"]
            if is_a_level:
                if stream_val not in ["Arts", "Commercials", "Sciences"]:
                    raise Exception(f"Invalid stream selection '{stream_val}' for A Level ({form_val}). Allowed streams: Arts, Commercials, Sciences.")
            else:
                if stream_val not in ["A", "B", "C"]:
                    raise Exception(f"Invalid stream selection '{stream_val}' for O Level ({form_val}). Allowed streams: A, B, C.")
                    
            # Resolve grade_id and class_id
            grade_num = grade_number(form_val)
            data["grade_id"] = grade_num
            
            settings = school_settings()
            current_year = settings.get("current_year") or 2026
            class_rec = resolve_legacy_class_record(
                grade=form_val,
                stream=stream_val,
                grade_id=grade_num,
                academic_year=current_year,
            )
            data["class_id"] = class_rec["class_id"] if class_rec else None
            
            # Set dummy photo path
            data["photo_path"] = ""
            
            response = update_record_fields(
                request,
                "pupils",
                "pupil_id",
                pupil["pupil_id"],
                data,
                "Student record updated.",
                f"/pupils/{pupil['admission_no']}",
            )
            settings = school_settings()
            sync_enterprise_student_registration(
                {**pupil, **data, "pupil_id": pupil["pupil_id"]},
                [
                    row["subject_id"]
                    for row in dict_rows(
                        "SELECT subject_id FROM student_subjects WHERE pupil_id = %s AND academic_year = %s",
                        [pupil["pupil_id"], settings.get("current_year") or 2026],
                    )
                ],
                settings.get("current_year") or 2026,
                settings.get("current_term"),
            )
            from parents.views import sync_guardians_from_pupils

            sync_guardians_from_pupils()
            return response
        except Exception as exc:
            messages.error(request, f"Could not update student: {exc}")
            data_dict = {field: (request.POST.get(field) or pupil.get(field) or "") for field in PUPIL_FIELDS}
            fields = student_form_fields({**pupil, **data_dict}, readonly_admission=True)
    return render(request, "school/form_page.html", {"title": "Edit Student", "subtitle": "Student edit form.", "fields": fields})


@permission_required("students.manage")
def student_subjects_edit(request, admission_no=None, pupil_id=None):
    from school_system_django.native import school_settings, dict_rows, one_row, audit_action
    from django.db import transaction, connection
    
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
        
    settings = school_settings()
    current_year = settings.get("current_year") or 2026
    
    form_val = pupil.get("grade")
    is_a_level = form_val in ["Form 5", "Form 6"]
    max_subjects = 5 if is_a_level else 10
    
    # Query current subjects
    current_subs = dict_rows(
        """
        SELECT s.subject_id, s.subject_code, s.subject_name
        FROM student_subjects ss
        JOIN subjects s ON s.subject_id = ss.subject_id
        WHERE ss.pupil_id = %s AND ss.academic_year = %s
        """,
        [pupil["pupil_id"], current_year]
    )
    current_ids = {r["subject_id"] for r in current_subs}
    current_codes = {r["subject_code"]: r["subject_name"] for r in current_subs}
    
    if request.method == "POST":
        selected_subjects = [int(x) for x in request.POST.getlist("subjects")]
        reason = (request.POST.get("reason") or "").strip()
        
        # Validation
        if not selected_subjects:
            messages.error(request, "Subject registration is mandatory. Please select at least 1 subject.")
            return redirect(request.path)
            
        if len(selected_subjects) > max_subjects:
            messages.error(request, f"Subject registration limit exceeded. For {form_val}, max registered subjects is {max_subjects}. Selected: {len(selected_subjects)}")
            return redirect(request.path)
            
        # Compute differences
        added = [x for x in selected_subjects if x not in current_ids]
        removed = [x for x in current_ids if x not in selected_subjects]
        
        try:
            with transaction.atomic():
                cursor = connection.cursor()
                if removed:
                    cursor.execute(
                        f"DELETE FROM student_subjects WHERE pupil_id = %s AND academic_year = %s AND subject_id IN ({','.join(['%s']*len(removed))})",
                        [pupil["pupil_id"], current_year] + removed
                    )
                for sub_id in added:
                    cursor.execute(
                        """
                        INSERT INTO student_subjects (pupil_id, subject_id, academic_year, form, stream)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        [pupil["pupil_id"], sub_id, current_year, form_val, pupil.get("class_stream")]
                    )
                sync_enterprise_student_registration(
                    pupil,
                    selected_subjects,
                    current_year,
                    settings.get("current_term"),
                )
            
            # Log to audit trail
            new_subs = dict_rows(f"SELECT subject_code, subject_name FROM subjects WHERE subject_id IN ({','.join(['%s']*len(selected_subjects))})", selected_subjects)
            prev_str = ", ".join([f"{name} ({code})" for code, name in current_codes.items()])
            new_str = ", ".join([f"{r['subject_name']} ({r['subject_code']})" for r in new_subs])
            
            log_details = f"Student: {pupil['admission_no']}. Prev: [{prev_str}]. New: [{new_str}]."
            if reason:
                log_details += f" Reason: {reason}"
            audit_action(request, "Subject Registration Update", log_details)
            
            messages.success(request, "Registered subjects updated successfully.")
            return redirect(f"/pupils/{pupil['admission_no']}")
        except Exception as exc:
            messages.error(request, f"Could not update subject registration: {exc}")
            return redirect(request.path)
            
    # GET method
    master_subjects = dict_rows("SELECT * FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")
    
    # Query registration history
    history = dict_rows(
        """
        SELECT ss.form, ss.stream, ss.academic_year, GROUP_CONCAT(s.subject_name, ', ') as subjects_list
        FROM student_subjects ss
        JOIN subjects s ON s.subject_id = ss.subject_id
        WHERE ss.pupil_id = %s
        GROUP BY ss.academic_year, ss.form, ss.stream
        ORDER BY ss.academic_year DESC
        """,
        [pupil["pupil_id"]]
    )
    
    return render(
        request,
        "students/student_subjects_edit.html",
        {
            "pupil": pupil,
            "master_subjects": master_subjects,
            "current_ids": current_ids,
            "max_subjects": max_subjects,
            "history": history,
            "settings": settings
        }
    )


def student_offer_letter_pdf_response(pupil, request=None):
    from io import BytesIO
    import hashlib
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.conf import settings as django_settings
    from django.http import HttpResponse
    from school_system_django.native import get_pdf_header, now_text, school_settings, today_text
    from school_system_django.official_docs import create_reportlab_stamp, qr_flowable
    import os

    pupil = enrich_student_display(pupil)
    settings = school_settings()
    generated_at = now_text()
    verification_raw = f"ADMISSION|{pupil.get('admission_no')}|{pupil.get('admission_date')}|{pupil.get('pupil_id')}"
    verification_code = hashlib.sha256(verification_raw.encode("utf-8")).hexdigest()[:16].upper()
    verify_url = request.build_absolute_uri(f"/pupils/{pupil.get('admission_no')}") if request else f"/pupils/{pupil.get('admission_no')}"
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm)
    styles = getSampleStyleSheet()
    body_style = ParagraphStyle("OfferBody", parent=styles["Normal"], fontSize=11, leading=16, textColor=colors.HexColor("#102a43"), spaceAfter=11)
    label_style = ParagraphStyle("OfferLabel", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#486581"))
    value_style = ParagraphStyle("OfferValue", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#102a43"))

    story = [get_pdf_header(settings, 170 * mm), Spacer(1, 8)]
    divider = Table([[""]], colWidths=[170 * mm])
    divider.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 1.4, colors.HexColor("#102a43"))]))
    story.extend([divider, Spacer(1, 18)])
    story.append(Paragraph("<b>ADMISSION LETTER</b>", styles["Heading2"]))
    story.append(Paragraph(f"Date: {today_text()}", body_style))

    full_name = f"{pupil.get('first_name', '')} {pupil.get('surname', '')}".strip()
    class_label = compact_class_label(grade=pupil.get("grade"), stream=pupil.get("class_stream"), grade_id=pupil.get("grade_id")) or "-"
    intro = (
        f"We are pleased to confirm that <b>{full_name}</b>, admission number "
        f"<b>{pupil.get('admission_no')}</b>, has been admitted to <b>{class_label}</b>."
    )
    story.append(Paragraph(intro, body_style))
    story.append(Paragraph("This letter confirms the student's registration in the school system and may be printed for the parent or guardian records.", body_style))

    details = [
        [Paragraph("Student", label_style), Paragraph(full_name, value_style)],
        [Paragraph("Admission Number", label_style), Paragraph(pupil.get("admission_no") or "-", value_style)],
        [Paragraph("Date of Birth", label_style), Paragraph(pupil.get("date_of_birth") or "-", value_style)],
        [Paragraph("Age", label_style), Paragraph(pupil.get("age") or "-", value_style)],
        [Paragraph("Class", label_style), Paragraph(class_label, value_style)],
        [Paragraph("Guardian", label_style), Paragraph(pupil.get("guardian_name") or "-", value_style)],
        [Paragraph("Admission Date", label_style), Paragraph(pupil.get("admission_date") or today_text(), value_style)],
        [Paragraph("Verification Code", label_style), Paragraph(verification_code, value_style)],
    ]
    detail_table = Table(details, colWidths=[48 * mm, 100 * mm])
    detail_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4f8")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d9e2ec")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    photo = None
    if pupil.get("photo_path"):
        photo_file = os.path.join(django_settings.MEDIA_ROOT, pupil.get("photo_path"))
        if os.path.exists(photo_file):
            photo = Image(photo_file, width=38 * mm, height=38 * mm)
    if photo:
        story.append(Table([[photo, detail_table]], colWidths=[42 * mm, 128 * mm], style=[("VALIGN", (0, 0), (-1, -1), "TOP")]))
    else:
        story.append(detail_table)

    qr = qr_flowable(f"{verify_url}\nAdmission: {pupil.get('admission_no')}\nCode: {verification_code}", size_mm=30)
    stamp = create_reportlab_stamp(
        settings.get("school_name") or "Raydon School System",
        today_text(),
        generated_at[11:16] if len(generated_at) >= 16 else "",
        status_str="ADMISSION VERIFIED",
    )
    auth_cells = [stamp, qr or Paragraph(verification_code, value_style), Paragraph("Scan the QR code to verify this admission record against the live school system.", value_style)]
    auth_table = Table([auth_cells], colWidths=[42 * mm, 35 * mm, 93 * mm])
    auth_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))

    story.extend([
        Spacer(1, 24),
        Paragraph("Please keep this letter safely and present it when requested by the school office.", body_style),
        auth_table,
        Spacer(1, 26),
        Paragraph("________________________________________", body_style),
        Paragraph(f"<b>{settings.get('headmaster_name') or 'Headmaster / School Registrar'}</b>", body_style),
        Paragraph(settings.get("school_name") or "Raydon School System", body_style),
    ])
    document.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="admission-letter-{pupil["admission_no"]}.pdf"'
    return response


@permission_required("students.view")
def offer_letter(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to access this student's offer letter.")
        return redirect("/pupils")
    return student_offer_letter_pdf_response(pupil, request=request)


@permission_required("students.manage")
def delete(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to delete this student.")
        return redirect("/pupils")
    if request.method == "POST":
        return delete_record(request, "Student", "pupils", "pupil_id", pupil["pupil_id"], "/pupils")
    row = {
        "admission_no": pupil.get("admission_no"),
        "student_name": f"{pupil.get('first_name')} {pupil.get('surname')}",
        "class": pupil.get("grade"),
        "stream": pupil.get("class_stream"),
        "status": pupil.get("status"),
    }
    return render(
        request,
        "school/detail_page.html",
        {
            "title": "Delete Student",
            "row": row,
            "delete_confirm": True,
            "actions": [{"label": "Cancel", "href": f"/pupils/{pupil['admission_no']}", "icon": "bi-x-circle"}],
        },
    )


@permission_required("students.manage")
def status(request, pupil_id=None, action=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to change this student's status.")
        return redirect("/pupils")
    status_map = {
        "activate": "Active",
        "active": "Active",
        "complete": PENDING_ZIMSEC_STATUS,
        "completed": PENDING_ZIMSEC_STATUS,
        "archive": PERMANENT_ARCHIVE_STATUS,
        "archived": PERMANENT_ARCHIVE_STATUS,
        "deactivate": "Inactive",
        "inactive": "Inactive",
        "transfer": "Transferred",
        "withdraw": "Withdrawn",
        "withdrawn": "Withdrawn",
        "suspend": "Suspended",
    }
    if action == "transfer":
        summary = student_financial_summary(pupil=pupil, ensure_bill=True)
        balance = float(summary.get("overall_balance") or 0) if summary else 0
        if balance > 0:
            messages.error(request, f"Cannot transfer {pupil['admission_no']}: fees arrears are USD {balance:,.2f}. Clear the balance first.")
            return redirect(f"/pupils/{pupil['admission_no']}")
    if request.method == "POST":
        new_status = "Transferred" if action == "transfer" else request.POST.get("status") or status_map.get(action, action.title())
        if action in {"complete", "completed"}:
            from students.services import complete_pupil
            complete_pupil(pupil, int(today_text()[:4]))
            level = academic_level_for_pupil(student_from_ref(admission_no or pupil_id))
            audit_action(request, "Complete Student", f"{pupil['admission_no']} moved to {level} Pending ZIMSEC Analysis.")
            messages.success(request, f"Student moved to Completed {level} - Pending ZIMSEC Analysis.")
            return redirect(f"/pupils/{pupil['admission_no']}")
        if action in {"archive", "archived"} or new_status == PERMANENT_ARCHIVE_STATUS:
            archive_pupil(pupil, request.POST.get("status_reason") or None)
            audit_action(request, "Archive Student", f"{pupil['admission_no']} permanently archived.")
            messages.success(request, "Student permanently archived.")
            return redirect(f"/pupils/{pupil['admission_no']}")
        if new_status == "Active" and grade_number(pupil.get("grade") or pupil.get("grade_id")) == O_LEVEL_COMPLETED_GRADE:
            reactivate_for_a_level(
                pupil,
                stream=request.POST.get("class_stream") or pupil.get("class_stream"),
                reason=request.POST.get("status_reason") or None,
            )
            audit_action(request, "Reactivate for A Level", f"{pupil['admission_no']} reactivated into Form 5.")
            messages.success(request, "Student reactivated into Form 5 for A Level. Current-term billing will now use the A Level fee structure.")
            return redirect(f"/pupils/{pupil['admission_no']}")
        fields = {
            "status": new_status,
            "status_reason": request.POST.get("status_reason") or "",
            "transfer_destination": request.POST.get("transfer_destination") or "",
            "status_changed_on": today_text(),
        }
        if new_status != "Active":
            fields["completed_on"] = today_text()
        if new_status == "Transferred":
            fields["transfer_letter_no"] = request.POST.get("transfer_letter_no") or f"TL-{pupil['admission_no']}-{today_text().replace('-', '')}"
        if new_status == "Transferred":
            try:
                update_record(request, "pupils", "pupil_id", pupil["pupil_id"], fields)
                audit_action(request, "Transfer Student", f"Transferred {pupil['admission_no']} and generated transfer letter {fields['transfer_letter_no']}.")
                messages.success(request, f"Student marked Transferred. Transfer letter generated.")
                return redirect(f"/pupils/{pupil['admission_no']}/transfer-letter/pdf")
            except Exception as exc:
                messages.error(request, f"Could not transfer student: {exc}")
        return update_record_fields(request, "pupils", "pupil_id", pupil["pupil_id"], fields, f"Student marked {new_status}.", f"/pupils/{pupil['admission_no']}")
    fields = [
        {"name": "status", "label": "Status", "widget": "select", "options": ["Active", "Inactive", PENDING_ZIMSEC_STATUS, PERMANENT_ARCHIVE_STATUS, "Transferred", "Withdrawn", "Suspended"], "value": status_map.get(action, action.title()), "readonly": action == "transfer"},
        {"name": "transfer_destination", "label": "Transfer destination"},
        {"name": "transfer_letter_no", "label": "Transfer letter number"},
        {"name": "status_reason", "label": "Reason", "widget": "textarea"},
    ]
    subtitle = "Student status workflow."
    if action == "activate" and grade_number(pupil.get("grade") or pupil.get("grade_id")) == O_LEVEL_COMPLETED_GRADE:
        fields.insert(1, {"name": "class_stream", "label": "Form 5 Stream", "value": pupil.get("class_stream") or "A", "required": True})
        subtitle = "Approve A Level application and reactivate the learner into Form 5."
    if action in {"archive", "archived"}:
        subtitle = "Move this learner into the permanent archive after the ZIMSEC analysis period."
    if action == "transfer":
        subtitle = f"Transfer is allowed because current arrears are USD {balance:,.2f}."
    return render(request, "school/form_page.html", {"title": f"Student {action.title()}", "subtitle": subtitle, "fields": fields})


def student_transfer_letter_pdf_response(pupil):
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from django.http import HttpResponse
    from school_system_django.native import school_settings, today_text

    settings = school_settings()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20 * mm, leftMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'SchoolTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=colors.HexColor('#102a43'),
        alignment=1,
        spaceAfter=5
    )

    meta_style = ParagraphStyle(
        'SchoolMeta',
        fontName='Helvetica',
        fontSize=9,
        textColor=colors.HexColor('#486581'),
        alignment=1
    )

    body_style = ParagraphStyle(
        'LetterBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=16,
        textColor=colors.HexColor('#102a43'),
        spaceAfter=12
    )

    story = []

    # Letterhead
    from school_system_django.native import get_pdf_header
    story.append(get_pdf_header(settings, 170 * mm))
    story.append(Spacer(1, 5))
    # Horizontal divider rule
    divider = Table([[""]], colWidths=[170 * mm])
    divider.setStyle(TableStyle([('LINEBELOW', (0,0), (-1,-1), 1.5, colors.HexColor('#102a43'))]))
    story.extend([divider, Spacer(1, 20)])

    # Date
    story.append(Paragraph(f"Date: {today_text()}", body_style))
    story.append(Spacer(1, 10))

    # Salutation
    story.append(Paragraph("<b>TO WHOM IT MAY CONCERN</b>", body_style))
    story.append(Spacer(1, 10))

    # Body
    student_name = f"<b>{pupil.get('first_name', '')} {pupil.get('surname', '')}</b>"
    admission_no = f"<b>{pupil.get('admission_no', '')}</b>"
    grade = f"<b>{compact_class_label(grade=pupil.get('grade'), stream=pupil.get('class_stream'), grade_id=pupil.get('grade_id'))}</b>"
    dest = f"<b>{pupil.get('transfer_destination') or 'another institution'}</b>"
    reason = pupil.get('status_reason') or 'family relocation/academic transition'

    p1 = f"This is to certify that {student_name}, registered under admission number {admission_no}, was a student at our school in grade {grade}."
    p2 = f"This student has officially transferred to {dest} effective {pupil.get('status_changed_on') or today_text()}."
    p3 = f"Reason for transfer: {reason}."
    p4 = "During their time at our school, they showed good conduct and academic effort. We wish them success in their future academic endeavors."

    story.append(Paragraph(p1, body_style))
    story.append(Paragraph(p2, body_style))
    story.append(Paragraph(p3, body_style))
    story.append(Paragraph(p4, body_style))
    story.append(Spacer(1, 30))

    # Sign-off
    story.append(Paragraph("Sincerely,", body_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph("________________________________________", body_style))
    story.append(Paragraph("<b>Headmaster / School Registrar</b>", body_style))
    story.append(Paragraph(settings.get("school_name") or "Raydon School System", body_style))

    document.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="transfer-letter-{pupil["admission_no"]}.pdf"'
    return response


@permission_required("students.view")
def transfer_letter(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to access this student's transfer letter.")
        return redirect("/pupils")
    if (pupil.get("status") or "") != "Transferred":
        messages.error(request, "Transfer letter can only be generated after the student is marked Transferred.")
        return redirect(f"/pupils/{pupil['admission_no']}")
    if request.path.endswith("/pdf") or request.GET.get("format") == "pdf":
        return student_transfer_letter_pdf_response(pupil)
    return render(request, "students/student_profile.html", {"pupil": pupil, "summary": student_financial_summary(pupil=pupil)})


@permission_required("fees.view")
def payment_history_view(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to view this student's payments.")
        return redirect("/pupils")
    rows = payment_history(pupil["pupil_id"], limit=100)
    return render_rows_page(
        request,
        f"Payment History - {pupil['admission_no']}",
        rows,
        ["receipt_no", "amount_paid", "payment_date", "payment_method", "term", "year", "reference_no"],
        subtitle=f"{pupil['first_name']} {pupil['surname']}",
        row_actions=[
            {"label": "Receipt", "href": "/receipt/{receipt_no}", "icon": "bi-receipt", "class": "btn-outline-primary"},
            {"label": "PDF", "href": "/receipt/{receipt_no}/pdf", "icon": "bi-file-earmark-pdf", "class": "btn-outline-info"},
        ],
    )


@permission_required("fees.view")
def balance(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to view this student's balance.")
        return redirect("/pupils")
    summary = student_financial_summary(pupil=pupil)
    return render(request, "students/student_balance.html", {"pupil": pupil, "summary": summary})


@permission_required("students.manage")
def promote(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if not pupil:
        messages.error(request, "Student was not found.")
        return redirect("/pupils")
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to promote this student.")
        return redirect("/pupils")
    if request.method == "POST":
        target_grade = request.POST.get("grade") or pupil.get("grade")
        target_number = grade_number(target_grade)
        if grade_number(pupil.get("grade") or pupil.get("grade_id")) == O_LEVEL_COMPLETED_GRADE and target_number != A_LEVEL_START_GRADE:
            messages.error(request, "Completed O Level learners may only be reactivated into Form 5 after approval.")
            return redirect(f"/pupils/{pupil['admission_no']}")
        grade_row = grade_row_for_number(target_number) if target_number else None
        target_stream = request.POST.get("class_stream") or pupil.get("class_stream")
        target_grade_id = (grade_row or {}).get("grade_id") if grade_row else target_number
        settings = school_settings()
        class_rec = resolve_legacy_class_record(
            grade=grade_label_for_number(target_number) if target_number else target_grade,
            stream=target_stream,
            grade_id=target_grade_id,
            academic_year=settings.get("current_year") or 2026,
        )
        fields = {
            "grade": grade_label_for_number(target_number) if target_number else target_grade,
            "grade_id": target_grade_id,
            "class_stream": target_stream,
            "class_id": class_rec["class_id"] if class_rec else None,
            "remarks": request.POST.get("remarks") or pupil.get("remarks") or "",
            "status": "Active",
            "status_changed_on": today_text(),
            "status_reason": "Reactivated for A Level" if target_number == A_LEVEL_START_GRADE else f"Promoted to {display_grade_label(target_grade)}",
        }
        return update_record_fields(request, "pupils", "pupil_id", pupil["pupil_id"], fields, "Student promoted.", f"/pupils/{pupil['admission_no']}")
    fields = [
        {"name": "grade", "label": "New Class", "value": display_grade_label(pupil.get("grade"), pupil.get("grade_id")), "required": True},
        {"name": "class_stream", "label": "New Stream", "value": pupil.get("class_stream"), "required": True},
        {"name": "remarks", "label": "Promotion Notes", "widget": "textarea"},
    ]
    return render(request, "school/form_page.html", {"title": "Promote Student", "subtitle": pupil["admission_no"], "fields": fields})


@permission_required("students.manage")
def deactivate(request, pupil_id=None, admission_no=None):
    pupil = student_from_ref(admission_no or pupil_id)
    if pupil and not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to deactivate this student.")
        return redirect("/pupils")
    if request.method == "POST":
        return status(request, pupil_id=pupil_id, admission_no=admission_no, action="deactivate")
    return status(request, pupil_id=pupil_id, admission_no=admission_no, action="deactivate")


@permission_required("fees.manage")
def fee_override(request, pupil_id):
    from school_system_django.native import one_row
    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil_id])
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to manage this student's fee overrides.")
        return redirect("/pupils")
    return render_table_page(
        request,
        "Student Fee Override",
        "pupil_fee_overrides",
        ["override_id", "pupil_id", "term", "year", "amount_required", "notes"],
        "Learner-specific fee overrides.",
        order_by="year DESC, term DESC",
        where="pupil_id = %s",
        params=[pupil_id],
        pk_column="override_id",
        create_href=f"/pupils/{pupil_id}/fee-override/new",
        row_actions=[],
    )


@permission_required("fees.manage")
def balance_adjustments(request, pupil_id):
    from school_system_django.native import one_row
    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil_id])
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to manage this student's balance adjustments.")
        return redirect("/pupils")
    return render_table_page(
        request,
        "Balance Adjustments",
        "balance_adjustments",
        ["adjustment_id", "pupil_id", "term", "year", "entry_type", "amount", "notes"],
        "Opening balances, adjustments, and corrections.",
        order_by="year DESC, term DESC",
        where="pupil_id = %s",
        params=[pupil_id],
        pk_column="adjustment_id",
        create_href=f"/pupils/{pupil_id}/balance-adjustments/new",
        row_actions=[],
    )


@permission_required("fees.manage")
def fee_override_new(request, pupil_id):
    from school_system_django.native import one_row
    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil_id])
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to manage this student's fee overrides.")
        return redirect("/pupils")
    return render_record_form_page(
        request,
        "Student Fee Override",
        "pupil_fee_overrides",
        ["term", "year", "amount_required", "notes"],
        subtitle="Learner-specific fee override.",
        redirect_to=f"/pupils/{pupil_id}/fee-override",
        extra_defaults={"pupil_id": pupil_id},
    )


@permission_required("fees.manage")
def balance_adjustment_new(request, pupil_id):
    from school_system_django.native import one_row
    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil_id])
    if not check_teacher_student_access(request, pupil):
        messages.error(request, "You do not have permission to manage this student's balance adjustments.")
        return redirect("/pupils")
    return render_record_form_page(
        request,
        "Balance Adjustment",
        "balance_adjustments",
        ["term", "year", "entry_type", "source_term", "source_year", "entry_date", "amount", "notes"],
        subtitle="Opening balances, adjustments, and corrections.",
        redirect_to=f"/pupils/{pupil_id}/balance-adjustments",
        extra_defaults={"pupil_id": pupil_id},
    )


@permission_required("library.manage")
def textbook_new(request):
    books = book_options()
    loan = {"borrowed_date": today_text(), "status": "Borrowed"}
    current_book_id = None
    if request.method == "POST":
        status_val = request.POST.get("status") or "Borrowed"
        current_book_id = request.POST.get("book_id")
        loan = {
            "pupil_id": request.POST.get("pupil_id"),
            "book_id": current_book_id,
            "borrowed_date": request.POST.get("borrowed_date") or today_text(),
            "return_date": request.POST.get("return_date") or "",
            "status": status_val,
            "notes": request.POST.get("notes") or "",
        }
        try:
            pupil_id = int(request.POST.get("pupil_id") or 0)
            book_id = int(request.POST.get("book_id") or 0)
            pupil = one_row("SELECT pupil_id FROM pupils WHERE pupil_id = %s", [pupil_id])
            if not pupil:
                raise ValueError("Select a valid student.")
            book = one_row("SELECT * FROM library_books WHERE book_id = %s", [book_id])
            if not book:
                raise ValueError("Selected library book was not found.")
            if status_val not in RETURNED_STATUSES and available_copies_for_issue(book_id) <= 0:
                raise ValueError(f"Cannot issue textbook: '{book['title']}' is out of stock in the library.")

            data = {
                "pupil_id": pupil_id,
                "book_id": book_id,
                "book_name": book["title"],
                "borrowed_date": loan["borrowed_date"],
                "return_date": loan["return_date"],
                "status": status_val,
                "notes": loan["notes"],
                "recorded_by": legacy_user_id(request),
                "created_at": now_text(),
                "updated_at": now_text(),
            }
            if status_val in RETURNED_STATUSES:
                data["cleared_date"] = today_text()
                data["cleared_by"] = legacy_user_id(request)
            insert_record(request, "textbook_loans", data)
            sync_book_availability(book_id)
            messages.success(request, f"Textbook '{book['title']}' issued successfully.")
            return redirect("/textbook-loans")
        except Exception as exc:
            messages.error(request, f"Could not issue textbook: {exc}")
            
    return render(
        request,
        "students/textbook_form.html",
        {
            "title": "Issue Textbook",
            "subtitle": "Record a new textbook issue record.",
            "is_edit": False,
            "today": today_text(),
            "books": books,
            "loan": loan,
            "current_book_id": current_book_id,
            "settings": school_settings(),
        }
    )


@permission_required("library.manage")
def textbook_edit(request, loan_id):
    loan = one_row("SELECT * FROM textbook_loans WHERE loan_id = %s", [loan_id])
    if not loan:
        messages.error(request, "Textbook loan record not found.")
        return redirect("/textbook-loans")

    pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [loan["pupil_id"]])
    if pupil:
        pupil = hydrate_class_labels([pupil])[0]
    current_book = book_from_loan(loan)
    current_book_id = current_book["book_id"] if current_book else loan.get("book_id")
    books = book_options(current_book_id)

    if request.method == "POST":
        status_val = request.POST.get("status") or "Borrowed"
        current_book_id = request.POST.get("book_id")
        try:
            book_id = int(request.POST.get("book_id") or 0)
            book = one_row("SELECT * FROM library_books WHERE book_id = %s", [book_id])
            if not book:
                raise ValueError("Selected library book was not found.")
            if status_val not in RETURNED_STATUSES and available_copies_for_issue(book_id, exclude_loan_id=loan_id) <= 0:
                raise ValueError(f"Cannot select book: '{book['title']}' is out of stock.")

            old_book = book_from_loan(loan)
            data = {
                "book_id": book_id,
                "book_name": book["title"],
                "borrowed_date": request.POST.get("borrowed_date") or today_text(),
                "return_date": request.POST.get("return_date") or "",
                "status": status_val,
                "notes": request.POST.get("notes") or "",
                "updated_at": now_text(),
            }
            if status_val in RETURNED_STATUSES:
                data["cleared_date"] = today_text()
                data["cleared_by"] = legacy_user_id(request)
            else:
                data["cleared_date"] = ""
                data["cleared_by"] = None
            update_record(request, "textbook_loans", "loan_id", loan_id, data)
            if old_book:
                sync_book_availability(old_book["book_id"])
            sync_book_availability(book_id)
            messages.success(request, "Textbook loan record updated.")
            return redirect("/textbook-loans")
        except Exception as exc:
            messages.error(request, f"Could not update loan: {exc}")
            loan = {**loan, **request.POST, "book_id": current_book_id}
            
    return render(
        request,
        "students/textbook_form.html",
        {
            "title": "Edit Textbook Loan",
            "subtitle": "Update details of textbook issue.",
            "is_edit": True,
            "loan": loan,
            "pupil": pupil,
            "today": today_text(),
            "books": books,
            "current_book_id": current_book_id,
            "settings": school_settings(),
        }
    )


@permission_required("library.manage")
def textbook_delete(request, loan_id):
    loan = one_row("SELECT * FROM textbook_loans WHERE loan_id = %s", [loan_id])
    if not loan:
        messages.error(request, "Textbook loan record not found.")
        return redirect("/textbook-loans")
    old_book = book_from_loan(loan)
    response = delete_record(request, "Textbook Loan", "textbook_loans", "loan_id", loan_id, "/textbook-loans")
    if request.method == "POST" and old_book:
        sync_book_availability(old_book["book_id"])
    return response


@permission_required("library.manage")
def textbook_return(request, loan_id):
    loan = one_row("SELECT * FROM textbook_loans WHERE loan_id = %s", [loan_id])
    if not loan:
        messages.error(request, "Textbook loan record not found.")
        return redirect("/textbook-loans")
    if loan.get("status") in RETURNED_STATUSES:
        messages.info(request, "This textbook is already marked as returned.")
        return redirect("/textbook-loans")
    book = book_from_loan(loan)
    data = {
        "status": "Returned",
        "cleared_date": today_text(),
        "cleared_by": legacy_user_id(request),
        "updated_at": now_text(),
    }
    if not loan.get("return_date"):
        data["return_date"] = today_text()
    update_record(request, "textbook_loans", "loan_id", loan_id, data)
    if book:
        sync_book_availability(book["book_id"])
    messages.success(request, "Textbook marked as returned and stock updated.")
    return redirect("/textbook-loans")

# Create your views here.
