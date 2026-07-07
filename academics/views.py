from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse
from django.db import connection
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.permissions import permission_required, assigned_classes_for_teacher, normalized_role, ROLE_TEACHER
from academics.library_services import (
    active_library_issue_count,
    active_textbook_loan_count,
    library_book_rows,
    sync_all_library_availability,
    sync_book_availability,
)
from school_system_django.native import delete_record, hydrate_class_labels, insert_record, render_detail_page, render_record_form_page, render_rows_page, render_table_page, today_text, update_record, update_record_fields, one_row, dict_rows, school_settings, hydrate_admission_numbers


CLASS_FIELDS = ["class_name", "grade_id", "academic_year", "class_teacher", "class_teacher_id"]
SUBJECT_FIELDS = ["subject_code", "subject_name", "grade", "display_order", "status"]
TIMETABLE_FIELDS = ["class_id", "academic_year", "day_name", "day_order", "period_no", "start_time", "end_time", "subject_id", "subject_name", "teacher_name", "room_name"]
ASSIGNMENT_FIELDS = ["title", "grade", "class_stream", "subject_id", "term", "year", "instructions", "file_path", "original_filename", "due_date", "max_score", "status"]
LIBRARY_BOOK_FIELDS = ["title", "author", "isbn", "category", "total_copies", "fine_per_day", "status"]

TIMETABLE_DAYS = [("Monday", 1), ("Tuesday", 2), ("Wednesday", 3), ("Thursday", 4), ("Friday", 5)]
TIMETABLE_PERIODS = [
    (1, "08:00", "08:40"),
    (2, "08:40", "09:20"),
    (3, "09:40", "10:20"),
    (4, "10:20", "11:00"),
    (5, "11:30", "12:10"),
    (6, "12:10", "12:50"),
    (7, "13:30", "14:10"),
    (8, "14:10", "14:50"),
]


def active_academic_year():
    actual_year = timezone.localdate().year
    settings_year = school_settings().get("current_year")
    try:
        configured_year = int(settings_year)
    except (TypeError, ValueError):
        configured_year = actual_year
    return min(configured_year, actual_year)


def clean_int(value, field_label, required=True):
    text = str(value or "").strip()
    if not text:
        if required:
            raise ValueError(f"{field_label} is required.")
        return None
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"{field_label} must be a number.")


def active_teacher_options(selected_id=None):
    options = [{"value": "", "label": "-- Unassigned --"}]
    rows = dict_rows(
        """
        SELECT user_id, username, full_name
        FROM users
        WHERE role = 'Teacher'
          AND COALESCE(status, 'Active') = 'Active'
        ORDER BY full_name, username
        """
    )
    seen = set()
    for row in rows:
        value = str(row["user_id"])
        seen.add(value)
        label = row.get("full_name") or row.get("username")
        options.append({"value": value, "label": label})
    if selected_id and str(selected_id) not in seen:
        teacher = one_row("SELECT user_id, username, full_name FROM users WHERE user_id = %s", [selected_id])
        if teacher:
            options.append({"value": str(teacher["user_id"]), "label": f"{teacher.get('full_name') or teacher.get('username')} (inactive)"})
    return options


def teacher_from_posted_id(value):
    teacher_id = clean_int(value, "Class Teacher", required=False)
    if not teacher_id:
        return None
    teacher = one_row(
        """
        SELECT user_id, username, full_name
        FROM users
        WHERE user_id = %s
          AND role = 'Teacher'
          AND COALESCE(status, 'Active') = 'Active'
        """,
        [teacher_id],
    )
    if not teacher:
        raise ValueError("Class teacher must be an active Teacher in the school database.")
    return teacher


def class_form_fields(row=None):
    row = row or {}
    current_year = active_academic_year()
    year_value = row.get("academic_year") or current_year
    try:
        if int(year_value) > current_year:
            year_value = current_year
    except (TypeError, ValueError):
        year_value = current_year
    return [
        {"name": "class_name", "label": "Class Stream", "value": row.get("class_name", ""), "required": True},
        {"name": "grade_id", "label": "Grade ID", "type": "number", "value": row.get("grade_id", ""), "required": True},
        {
            "name": "academic_year",
            "label": "Academic Year",
            "type": "number",
            "value": year_value,
            "readonly": True,
            "help_text": f"Uses the active school year. Future years are blocked until the calendar reaches them.",
        },
        {"name": "class_teacher", "label": "Class Teacher", "widget": "hidden", "value": row.get("class_teacher", "")},
        {
            "name": "class_teacher_id",
            "label": "Class Teacher",
            "widget": "select",
            "options": active_teacher_options(row.get("class_teacher_id")),
            "value": row.get("class_teacher_id", ""),
            "required": False,
            "help_text": "Only active Teacher accounts from the school database can be assigned.",
        },
    ]


def posted_class_data(request, existing=None):
    current_year = active_academic_year()
    posted_year = clean_int(request.POST.get("academic_year") or current_year, "Academic year")
    if posted_year > current_year:
        raise ValueError(f"Academic year cannot be {posted_year} while the active year is {current_year}.")
    teacher = teacher_from_posted_id(request.POST.get("class_teacher_id"))
    data = {
        "class_name": (request.POST.get("class_name") or "").strip().upper(),
        "grade_id": clean_int(request.POST.get("grade_id"), "Grade ID"),
        "academic_year": posted_year,
        "class_teacher": (teacher.get("full_name") or teacher.get("username")) if teacher else None,
        "class_teacher_id": teacher.get("user_id") if teacher else None,
    }
    if not data["class_name"]:
        raise ValueError("Class stream is required.")
    duplicate = one_row(
        """
        SELECT class_id
        FROM classes
        WHERE UPPER(class_name) = %s AND grade_id = %s AND academic_year = %s
        """,
        [data["class_name"], data["grade_id"], data["academic_year"]],
    )
    if duplicate and (not existing or duplicate["class_id"] != existing.get("class_id")):
        raise ValueError(f"Class {data['class_name']} already exists for this grade in {data['academic_year']}.")
    return data


def academic_year_field():
    return {
        "name": "academic_year",
        "label": "Academic Year",
        "type": "number",
        "value": active_academic_year(),
        "readonly": True,
        "help_text": "Current active school year only.",
    }


def timetable_class_options():
    rows = hydrate_class_labels(
        dict_rows(
            """
            SELECT c.class_id, c.class_name, c.grade_id, g.grade_name, c.academic_year
            FROM classes c
            LEFT JOIN grades g ON g.grade_id = c.grade_id
            WHERE c.academic_year = %s
            ORDER BY c.grade_id, c.class_name
            """,
            [active_academic_year()],
        )
    )
    return [{"value": "", "label": "All active classes"}] + [
        {"value": str(row["class_id"]), "label": f"{row.get('class_label') or row.get('class_name')} ({row.get('academic_year')})"}
        for row in rows
    ]


def subjects_for_grade(grade_name):
    subjects = dict_rows(
        """
        SELECT subject_id, subject_code, subject_name
        FROM subjects
        WHERE status = 'Active'
          AND (grade = 'All Forms' OR grade = %s)
        ORDER BY display_order, subject_name
        """,
        [grade_name],
    )
    if not subjects:
        subjects = dict_rows(
            """
            SELECT subject_id, subject_code, subject_name
            FROM subjects
            WHERE status = 'Active'
            ORDER BY display_order, subject_name
            """
        )
    return subjects


def generate_timetable_entries(request, class_id=None, replace=False):
    current_year = active_academic_year()
    params = [current_year]
    where = "WHERE c.academic_year = %s"
    if class_id:
        where += " AND c.class_id = %s"
        params.append(class_id)
    classes = dict_rows(
        f"""
        SELECT c.class_id, c.class_name, c.grade_id, c.academic_year, c.class_teacher, g.grade_name
        FROM classes c
        LEFT JOIN grades g ON g.grade_id = c.grade_id
        {where}
        ORDER BY c.grade_id, c.class_name
        """,
        params,
    )
    created = 0
    skipped = 0
    teacher_slots = set()
    with connection.cursor() as cursor:
        for class_index, class_row in enumerate(classes):
            existing = one_row(
                "SELECT COUNT(*) AS total FROM class_timetable_entries WHERE class_id = %s AND academic_year = %s",
                [class_row["class_id"], current_year],
            )
            if existing and int(existing["total"] or 0) and not replace:
                skipped += 1
                continue
            if replace:
                cursor.execute(
                    "DELETE FROM class_timetable_entries WHERE class_id = %s AND academic_year = %s",
                    [class_row["class_id"], current_year],
                )
            subjects = subjects_for_grade(class_row.get("grade_name") or "")
            if not subjects:
                skipped += 1
                continue
            teacher_name = class_row.get("class_teacher") or ""
            for day_index, (day_name, day_order) in enumerate(TIMETABLE_DAYS):
                for period_index, (period_no, start_time, end_time) in enumerate(TIMETABLE_PERIODS):
                    subject = subjects[(day_index * len(TIMETABLE_PERIODS) + period_index + class_index) % len(subjects)]
                    assigned_teacher = teacher_name
                    slot_key = (assigned_teacher.upper().strip(), day_order, period_no)
                    if assigned_teacher and slot_key in teacher_slots:
                        assigned_teacher = ""
                    if assigned_teacher:
                        teacher_slots.add(slot_key)
                    cursor.execute(
                        """
                        INSERT INTO class_timetable_entries
                            (class_id, academic_year, day_name, day_order, period_no, start_time, end_time,
                             subject_id, subject_name, teacher_name, generated_by, generated_at, room_name)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        [
                            class_row["class_id"],
                            current_year,
                            day_name,
                            day_order,
                            period_no,
                            start_time,
                            end_time,
                            subject["subject_id"],
                            subject.get("subject_name") or subject.get("subject_code"),
                            assigned_teacher,
                            getattr(getattr(request.user, "profile", None), "legacy_user_id", None),
                            today_text(),
                            f"Room {class_row['class_id']}",
                        ],
                    )
                    created += 1
    return {"classes": len(classes), "created": created, "skipped": skipped}


@permission_required("classes.view")
def classes(request):
    current_year = active_academic_year()
    clauses = ["c.academic_year = %s"]
    params = [current_year]
    role = normalized_role(request.user)
    if role == ROLE_TEACHER:
        allowed_ids = assigned_classes_for_teacher(request.user)
        if allowed_ids:
            clauses.append(f"c.class_id IN ({', '.join(['%s'] * len(allowed_ids))})")
            params.extend(allowed_ids)
        else:
            clauses.append("1=0")
    q = (request.GET.get("q") or "").strip()
    if q:
        clauses.append("(c.class_name LIKE %s OR g.grade_name LIKE %s OR c.class_teacher LIKE %s)")
        params.extend([f"%{q}%"] * 3)
    where_sql = " AND ".join(clauses)
    rows = dict_rows(
        f"""
        SELECT c.class_id, c.class_name, c.grade_id, g.grade_name, c.academic_year, c.class_teacher
        FROM classes c
        LEFT JOIN grades g ON g.grade_id = c.grade_id
        WHERE {where_sql}
        ORDER BY c.grade_id, c.class_name
        """,
        params,
    )
    rows = hydrate_class_labels(rows)
    return render_rows_page(
        request,
        "Classes and Streams",
        rows,
        ["class_label", "grade_name", "class_name", "academic_year", "class_teacher"],
        f"Active class streams for {current_year}. Future-year classes are hidden until their year starts.",
        actions=[{"label": "New Class", "href": "/classes/new", "icon": "bi-plus-circle"}],
        total=len(rows),
        page=1,
        per_page=max(len(rows), 10),
        row_actions=[
            {"label": "View", "href": "/classes/{class_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/classes/{class_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/classes/{class_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this class?"},
        ],
    )


@permission_required("timetable.view")
def timetables(request):
    from school_system_django.native import current_user_role
    role = current_user_role(request.user)
    teacher_name = request.GET.get("teacher_name")
    current_year = active_academic_year()

    if role == "Teacher":
        profile = getattr(request.user, "profile", None)
        teacher_name = profile.full_name if profile else ""

    if teacher_name:
        # Render teacher timetable grid
        entries = dict_rows(
            """
            SELECT t.day_name, t.day_order, t.period_no, t.start_time, t.end_time, t.subject_name, t.room_name,
                   c.class_name, g.grade_name
            FROM class_timetable_entries t
            LEFT JOIN classes c ON c.class_id = t.class_id
            LEFT JOIN grades g ON g.grade_id = c.grade_id
            WHERE UPPER(t.teacher_name) = %s
              AND t.academic_year = %s
            ORDER BY t.day_order, t.period_no
            """,
            [teacher_name.upper().strip(), current_year]
        )
        
        periods = []
        seen_periods = set()
        for entry in entries:
            p_no = entry.get('period_no')
            if p_no and p_no not in seen_periods:
                seen_periods.add(p_no)
                periods.append({
                    'period_no': p_no,
                    'start_time': entry.get('start_time'),
                    'end_time': entry.get('end_time')
                })
        periods.sort(key=lambda x: x['period_no'])
        if not periods:
            periods = [{'period_no': i, 'start_time': '', 'end_time': ''} for i in range(1, 9)]

        days_list = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        for entry in entries:
            d_name = entry.get('day_name')
            if d_name and d_name not in days_list:
                days_list.append(d_name)

        timetable_rows = []
        for day in days_list:
            row_cells = []
            for p in periods:
                match = None
                for entry in entries:
                    if entry.get('day_name') == day and entry.get('period_no') == p['period_no']:
                        match = entry
                        break
                row_cells.append(match)
            timetable_rows.append({
                'day_name': day,
                'cells': row_cells
            })

        entries = hydrate_class_labels(entries)
        context = {
            "teacher_name": teacher_name,
            "periods": periods,
            "timetable_rows": timetable_rows,
            "settings": school_settings(),
            "is_teacher": role == "Teacher",
        }
        return render(request, "academics/teacher_timetable.html", context)

    # For admin/staff, render standard list but include teacher search/dropdown in extra_context
    teachers = dict_rows("SELECT DISTINCT teacher_name FROM class_timetable_entries WHERE teacher_name IS NOT NULL AND teacher_name != '' ORDER BY teacher_name")

    return render_table_page(
        request,
        "Timetables",
        "class_timetable_entries",
        ["timetable_id", "class_id", "academic_year", "day_name", "period_no", "subject_name", "teacher_name", "room_name"],
        f"Class timetable entries for {current_year}.",
        order_by="academic_year DESC, class_id, day_order, period_no",
        search_columns=["subject_name", "teacher_name", "room_name"],
        where="academic_year = %s",
        params=[current_year],
        pk_column="timetable_id",
        actions=[
            {"label": "Auto Generate", "href": "/timetables/generate", "icon": "bi-magic"},
            {"label": "New Timetable Entry", "href": "/timetables/new", "icon": "bi-plus-circle"},
        ],
        row_actions=[
            {"label": "Edit", "href": "/timetables/{timetable_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/timetables/{timetable_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this timetable entry?"},
        ],
        extra_context={"teachers": teachers}
    )


@permission_required("timetable.manage")
def timetable_generate(request):
    fields = [
        {
            "name": "class_id",
            "label": "Class",
            "widget": "select",
            "options": timetable_class_options(),
            "value": request.POST.get("class_id") or "",
            "help_text": "Choose one class, or leave as all active classes.",
        },
        {
            "name": "replace",
            "label": "Replace Existing Entries",
            "widget": "select",
            "options": [{"value": "no", "label": "No, skip classes with timetables"}, {"value": "yes", "label": "Yes, replace current-year entries"}],
            "value": request.POST.get("replace") or "no",
        },
    ]
    if request.method == "POST":
        selected_class_id = clean_int(request.POST.get("class_id"), "Class", required=False)
        result = generate_timetable_entries(request, class_id=selected_class_id, replace=request.POST.get("replace") == "yes")
        messages.success(
            request,
            f"Timetable generation complete: {result['created']} entries created, {result['skipped']} class(es) skipped.",
        )
        return redirect("/timetables")
    return render(
        request,
        "school/form_page.html",
        {
            "title": "Auto Generate Timetables",
            "subtitle": "Creates a current-year weekly timetable from classes, subjects, and assigned class teachers.",
            "fields": fields,
            "settings": school_settings(),
        },
    )


@permission_required("elearning.manage")
def e_learning(request):
    from accounts.permissions import normalized_role, ROLE_TEACHER
    
    role = normalized_role(request.user)
    if role == ROLE_TEACHER and hasattr(request.user, "profile"):
        profile_id = request.user.profile.id
        legacy_id = request.user.profile.legacy_user_id or request.user.id
        
        assignments = dict_rows(
            """
            SELECT a.*, s.subject_name,
                   (SELECT COUNT(*) FROM e_learning_submissions sub WHERE sub.assignment_id = a.assignment_id) AS submissions_count,
                   (SELECT COUNT(*) FROM e_learning_submissions sub WHERE sub.assignment_id = a.assignment_id AND sub.status = 'Submitted') AS pending_count
            FROM e_learning_assignments a
            LEFT JOIN subjects s ON s.subject_id = a.subject_id
            WHERE a.uploaded_by = %s OR EXISTS (
                SELECT 1 FROM timetable_subjectallocation sa
                JOIN classes c ON c.class_id = sa.class_id
                JOIN grades g ON g.grade_id = c.grade_id
                WHERE sa.teacher_id = %s 
                  AND g.grade_name = a.grade 
                  AND (c.class_name = a.class_stream OR a.class_stream = 'All Streams')
                  AND sa.subject_id = a.subject_id
            )
            ORDER BY a.assignment_id DESC
            """,
            [legacy_id, profile_id]
        )
        notes = dict_rows(
            """
            SELECT n.*, s.subject_name
            FROM e_learning_notes n
            LEFT JOIN subjects s ON s.subject_id = n.subject_id
            WHERE n.uploaded_by = %s OR EXISTS (
                SELECT 1 FROM timetable_subjectallocation sa
                JOIN classes c ON c.class_id = sa.class_id
                JOIN grades g ON g.grade_id = c.grade_id
                WHERE sa.teacher_id = %s 
                  AND g.grade_name = n.grade 
                  AND (c.class_name = n.class_stream OR n.class_stream = 'All Streams')
                  AND sa.subject_id = n.subject_id
            )
            ORDER BY n.note_id DESC
            """,
            [legacy_id, profile_id]
        )
    else:
        assignments = dict_rows(
            """
            SELECT a.*, s.subject_name,
                   (SELECT COUNT(*) FROM e_learning_submissions sub WHERE sub.assignment_id = a.assignment_id) AS submissions_count,
                   (SELECT COUNT(*) FROM e_learning_submissions sub WHERE sub.assignment_id = a.assignment_id AND sub.status = 'Submitted') AS pending_count
            FROM e_learning_assignments a
            LEFT JOIN subjects s ON s.subject_id = a.subject_id
            ORDER BY a.assignment_id DESC
            """
        )
        notes = dict_rows(
            """
            SELECT n.*, s.subject_name
            FROM e_learning_notes n
            LEFT JOIN subjects s ON s.subject_id = n.subject_id
            ORDER BY n.note_id DESC
            """
        )
        
    return render(
        request,
        "academics/e_learning.html",
        {
            "assignments": assignments,
            "notes": notes,
            "settings": school_settings(),
        }
    )


@permission_required("classes.view")
def class_detail(request, class_id):
    allowed_class_ids = assigned_classes_for_teacher(request.user)
    if allowed_class_ids and int(class_id) not in allowed_class_ids:
        messages.error(request, "You are not assigned to this class.")
        return redirect("/classes")

    class_record = one_row("SELECT * FROM classes WHERE class_id = %s", [class_id])
    if not class_record:
        messages.error(request, "Class was not found.")
        return redirect("/classes")
    current_year = active_academic_year()
    if int(class_record.get("academic_year") or 0) > current_year:
        messages.error(request, f"This class is for {class_record['academic_year']}. The active academic year is {current_year}.")
        return redirect("/classes")
    class_record = hydrate_class_labels([class_record])[0]
        
    students = dict_rows(
        "SELECT pupil_id, admission_no, first_name, surname, gender, status FROM pupils WHERE class_id = %s ORDER BY first_name, surname",
        [class_id]
    )
    students = hydrate_admission_numbers(students)
    
    timetable_entries = dict_rows(
        """
        SELECT day_name, day_order, period_no, start_time, end_time, subject_name, teacher_name, room_name
        FROM class_timetable_entries
        WHERE class_id = %s
        ORDER BY day_order, period_no
        """,
        [class_id]
    )
    
    periods = []
    seen_periods = set()
    for entry in timetable_entries:
        p_no = entry.get('period_no')
        if p_no and p_no not in seen_periods:
            seen_periods.add(p_no)
            periods.append({
                'period_no': p_no,
                'start_time': entry.get('start_time'),
                'end_time': entry.get('end_time')
            })
    periods.sort(key=lambda x: x['period_no'])

    days_list = []
    seen_days = set()
    for entry in timetable_entries:
        d_order = entry.get('day_order')
        d_name = entry.get('day_name')
        if d_order and d_order not in seen_days:
            seen_days.add(d_order)
            days_list.append({
                'day_order': d_order,
                'day_name': d_name
            })
    days_list.sort(key=lambda x: x['day_order'])

    timetable_rows = []
    for d in days_list:
        row_cells = []
        for p in periods:
            match = None
            for entry in timetable_entries:
                if entry.get('day_name') == d['day_name'] and entry.get('period_no') == p['period_no']:
                    match = entry
                    break
            row_cells.append(match)
        timetable_rows.append({
            'day_name': d['day_name'],
            'cells': row_cells
        })

    context = {
        "class_record": class_record,
        "students": students,
        "periods": periods,
        "timetable_rows": timetable_rows,
        "settings": school_settings(),
    }
    return render(request, "academics/class_detail.html", context)


@permission_required("classes.manage")
def class_new(request):
    fields = class_form_fields()
    if request.method == "POST":
        try:
            data = posted_class_data(request)
            insert_record(request, "classes", data)
            messages.success(request, f"Class saved for academic year {data['academic_year']}.")
            return redirect("/classes")
        except Exception as exc:
            messages.error(request, f"Could not save class: {exc}")
            posted = {field["name"]: request.POST.get(field["name"], "") for field in fields}
            fields = class_form_fields(posted)
    return render(
        request,
        "school/form_page.html",
        {"title": "New Class", "subtitle": f"Active academic year: {active_academic_year()}.", "fields": fields, "settings": school_settings()},
    )


@permission_required("classes.manage")
def class_edit(request, class_id):
    row = one_row("SELECT * FROM classes WHERE class_id = %s", [class_id])
    if not row:
        messages.error(request, "Class was not found.")
        return redirect("/classes")
    current_year = active_academic_year()
    if int(row.get("academic_year") or 0) > current_year:
        messages.error(request, f"This class is for {row['academic_year']}. Future academic years cannot be edited while the active year is {current_year}.")
        return redirect("/classes")
    fields = class_form_fields(row)
    if request.method == "POST":
        try:
            data = posted_class_data(request, existing=row)
            update_record(request, "classes", "class_id", class_id, data)
            messages.success(request, "Class updated.")
            return redirect(f"/classes/{class_id}")
        except Exception as exc:
            messages.error(request, f"Could not update class: {exc}")
            posted = {field["name"]: request.POST.get(field["name"], "") for field in fields}
            posted["class_id"] = class_id
            fields = class_form_fields(posted)
    return render(
        request,
        "school/form_page.html",
        {"title": "Edit Class", "subtitle": f"Active academic year: {current_year}.", "fields": fields, "settings": school_settings()},
    )


@permission_required("classes.manage")
def class_delete(request, class_id):
    return delete_record(request, "Class", "classes", "class_id", class_id, "/classes")


@permission_required("classes.view")
def subjects(request):
    return render_table_page(
        request,
        "Subjects",
        "subjects",
        ["subject_id", "subject_code", "subject_name", "grade", "display_order", "status"],
        "Subject setup and allocation.",
        order_by="grade, display_order, subject_name",
        search_columns=["subject_code", "subject_name", "grade", "status"],
        pk_column="subject_id",
        create_href="/subjects/new",
        create_label="New Subject",
        row_actions=[
            {"label": "View", "href": "/subjects/{subject_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/subjects/{subject_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/subjects/{subject_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this subject?"},
        ],
    )


@permission_required("classes.view")
def subject_detail(request, subject_id):
    return render_detail_page(request, "Subject", "subjects", "subject_id", subject_id)


@permission_required("classes.manage")
def subject_new(request):
    return render_record_form_page(request, "New Subject", "subjects", SUBJECT_FIELDS, redirect_to="/subjects")


@permission_required("classes.manage")
def subject_edit(request, subject_id):
    return render_record_form_page(request, "Edit Subject", "subjects", SUBJECT_FIELDS, pk_column="subject_id", pk_value=subject_id, redirect_to=f"/subjects/{subject_id}")


@permission_required("classes.manage")
def subject_delete(request, subject_id):
    from school_system_django.native import one_row, delete_record
    
    # Check dependencies
    # 1. Result entries
    res = one_row("SELECT COUNT(*) as cnt FROM result_entries WHERE subject_id = %s", [subject_id])
    if res and res["cnt"] > 0:
        messages.error(request, "Cannot delete subject: active historical result entries reference this subject.")
        return redirect("/subjects")
        
    # 2. Timetable entries
    time_ent = one_row("SELECT COUNT(*) as cnt FROM class_timetable_entries WHERE subject_id = %s", [subject_id])
    if time_ent and time_ent["cnt"] > 0:
        messages.error(request, "Cannot delete subject: active timetable entries reference this subject.")
        return redirect("/subjects")
        
    # 3. Student subject registrations
    stud_sub = one_row("SELECT COUNT(*) as cnt FROM student_subjects WHERE subject_id = %s", [subject_id])
    if stud_sub and stud_sub["cnt"] > 0:
        messages.error(request, "Cannot delete subject: active student registrations reference this subject.")
        return redirect("/subjects")
        
    # 4. Teacher subject allocations
    teach_alloc = one_row("SELECT COUNT(*) as cnt FROM timetable_subjectallocation WHERE subject_id = %s", [subject_id])
    if teach_alloc and teach_alloc["cnt"] > 0:
        messages.error(request, "Cannot delete subject: active teacher allocations reference this subject.")
        return redirect("/subjects")
        
    # 5. E-learning assignments & notes
    el_assign = one_row("SELECT COUNT(*) as cnt FROM e_learning_assignments WHERE subject_id = %s", [subject_id])
    if el_assign and el_assign["cnt"] > 0:
        messages.error(request, "Cannot delete subject: active E-Learning assignments reference this subject.")
        return redirect("/subjects")
        
    el_notes = one_row("SELECT COUNT(*) as cnt FROM e_learning_notes WHERE subject_id = %s", [subject_id])
    if el_notes and el_notes["cnt"] > 0:
        messages.error(request, "Cannot delete subject: active E-Learning notes reference this subject.")
        return redirect("/subjects")
        
    return delete_record(request, "Subject", "subjects", "subject_id", subject_id, "/subjects")


@permission_required("timetable.manage")
def timetable_new(request):
    fields = [academic_year_field() if field == "academic_year" else field for field in TIMETABLE_FIELDS]
    return render_record_form_page(
        request,
        "New Timetable Entry",
        "class_timetable_entries",
        fields,
        redirect_to="/timetables",
        extra_defaults={"academic_year": active_academic_year()},
    )


@permission_required("timetable.manage")
def timetable_edit(request, timetable_id):
    row = one_row("SELECT * FROM class_timetable_entries WHERE timetable_id = %s", [timetable_id])
    if row and int(row.get("academic_year") or 0) > active_academic_year():
        messages.error(request, "Future-year timetable entries cannot be edited until that academic year starts.")
        return redirect("/timetables")
    fields = [academic_year_field() if field == "academic_year" else field for field in TIMETABLE_FIELDS]
    return render_record_form_page(
        request,
        "Edit Timetable Entry",
        "class_timetable_entries",
        fields,
        pk_column="timetable_id",
        pk_value=timetable_id,
        redirect_to="/timetables",
        extra_defaults={"academic_year": active_academic_year()},
    )


@permission_required("timetable.manage")
def timetable_delete(request, timetable_id):
    return delete_record(request, "Timetable Entry", "class_timetable_entries", "timetable_id", timetable_id, "/timetables")


@permission_required("elearning.manage")
def e_learning_detail(request, assignment_id):
    assignment = one_row(
        """
        SELECT a.*, s.subject_name, s.subject_code
        FROM e_learning_assignments a
        LEFT JOIN subjects s ON s.subject_id = a.subject_id
        WHERE a.assignment_id = %s
        """,
        [assignment_id]
    )
    if not assignment:
        messages.error(request, "Assignment not found.")
        return redirect("/e-learning")
        
    from accounts.permissions import check_teacher_assignment_access
    if not check_teacher_assignment_access(request.user, assignment["grade"], assignment["class_stream"], assignment["subject_id"], assignment["uploaded_by"]):
        messages.error(request, "You do not have permission to view this assignment.")
        return redirect("/e-learning")
        
    grade = assignment["grade"]
    stream = assignment["class_stream"]
    
    if stream and stream != "All Streams" and stream.strip() != "":
        pupils = dict_rows(
            "SELECT pupil_id, admission_no, first_name, surname, class_stream FROM pupils WHERE grade = %s AND class_stream = %s AND status = 'Active' ORDER BY first_name, surname",
            [grade, stream]
        )
    else:
        pupils = dict_rows(
            "SELECT pupil_id, admission_no, first_name, surname, class_stream FROM pupils WHERE grade = %s AND status = 'Active' ORDER BY first_name, surname",
            [grade]
        )
        
    submissions = dict_rows("SELECT * FROM e_learning_submissions WHERE assignment_id = %s", [assignment_id])
    sub_map = {s["pupil_id"]: s for s in submissions}
    
    students_grid = []
    for p in pupils:
        sub = sub_map.get(p["pupil_id"])
        students_grid.append({
            "pupil_id": p["pupil_id"],
            "admission_no": p["admission_no"],
            "name": f"{p['first_name']} {p['surname']}",
            "class_stream": p["class_stream"],
            "status": sub["status"] if sub else "Not Submitted",
            "score": sub["score"] if sub and sub["score"] is not None else "",
            "feedback": sub["feedback"] if sub and sub["feedback"] is not None else "",
            "answer_text": sub["answer_text"] if sub else "",
            "file_path": sub["file_path"] if sub else "",
            "original_filename": sub["original_filename"] if sub else "",
            "submitted_at": sub["submitted_at"] if sub else "",
            "submission_id": sub["submission_id"] if sub else None,
        })
        
    return render(
        request,
        "academics/e_learning_detail.html",
        {
            "assignment": assignment,
            "students": students_grid,
            "settings": school_settings(),
        }
    )


def save_uploaded_assignment_file(uploaded_file):
    import os
    import uuid
    from datetime import datetime
    from saas_tenant_management.models import get_current_tenant
    
    base_dir = "uploads"
    tenant = get_current_tenant()
    tenant_id = getattr(tenant, "tenant_id", None)
    relative_dir = os.path.join("tenants", str(tenant_id), "assignments") if tenant_id else "assignments"
    target_dir = os.path.join(base_dir, relative_dir)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    ext = os.path.splitext(uploaded_file.name)[1]
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{ext}"
    target_path = os.path.join(target_dir, unique_name)
    
    with open(target_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
            
    return os.path.join(relative_dir, unique_name), uploaded_file.name


@permission_required("elearning.manage")
def e_learning_new(request):
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from school_system_django.native import school_settings, dict_rows, insert_record, legacy_user_id, now_text
    
    settings = school_settings()
    grades = ["Form 1", "Form 2", "Form 3", "Form 4", "Form 5", "Form 6"]
    subjects = dict_rows("SELECT subject_id, subject_code, subject_name, grade FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")
    years = [2026, 2025, 2024]
    
    # Filter subjects for teachers
    from accounts.permissions import normalized_role, ROLE_TEACHER, assigned_subject_ids_for_teacher, check_teacher_assignment_access
    role = normalized_role(request.user)
    if role == ROLE_TEACHER:
        assigned_sub_ids = assigned_subject_ids_for_teacher(request.user)
        subjects = [s for s in subjects if s["subject_id"] in assigned_sub_ids]
        
    if request.method == "POST":
        title = request.POST.get("title")
        grade = request.POST.get("grade")
        class_stream = request.POST.get("class_stream")
        subject_id = request.POST.get("subject_id")
        term = request.POST.get("term")
        year = request.POST.get("year")
        instructions = request.POST.get("instructions") or ""
        due_date = request.POST.get("due_date") or None
        max_score = request.POST.get("max_score") or "100"
        status = request.POST.get("status") or "Open"
        
        # Server-side validation of teacher assignment
        if role == ROLE_TEACHER:
            if not check_teacher_assignment_access(request.user, grade, class_stream, subject_id):
                messages.error(request, f"You do not have permission to assign to {grade} - {class_stream} in this subject.")
                return redirect(request.path)
                
        file_path = None
        original_filename = None
        
        if request.FILES.get("file"):
            try:
                file_path, original_filename = save_uploaded_assignment_file(request.FILES["file"])
            except Exception as exc:
                messages.error(request, f"Failed to upload file: {exc}")
                
        data = {
            "title": title,
            "grade": grade,
            "class_stream": class_stream,
            "subject_id": int(subject_id) if subject_id else None,
            "term": term,
            "year": int(year),
            "instructions": instructions,
            "file_path": file_path,
            "original_filename": original_filename,
            "due_date": due_date,
            "max_score": float(max_score) if max_score else 100.0,
            "status": status,
            "uploaded_by": legacy_user_id(request),
            "created_at": now_text(),
            "updated_at": now_text()
        }
        
        try:
            insert_record(request, "e_learning_assignments", data)
            messages.success(request, "E-learning assignment created.")
            return redirect("/e-learning")
        except Exception as exc:
            messages.error(request, f"Could not create assignment: {exc}")
            
    context = {
        "title": "New E-learning Assignment",
        "grades": grades,
        "subjects": subjects,
        "years": years,
        "assignment": {},
        "settings": settings,
    }
    return render(request, "academics/assignment_form.html", context)


@permission_required("elearning.manage")
def e_learning_edit(request, assignment_id):
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from school_system_django.native import school_settings, one_row, dict_rows, update_record, now_text
    
    settings = school_settings()
    assignment = one_row("SELECT * FROM e_learning_assignments WHERE assignment_id = %s", [assignment_id])
    if not assignment:
        messages.error(request, "Assignment was not found.")
        return redirect("/e-learning")
        
    from accounts.permissions import check_teacher_assignment_access, normalized_role, ROLE_TEACHER, assigned_subject_ids_for_teacher
    if not check_teacher_assignment_access(request.user, assignment["grade"], assignment["class_stream"], assignment["subject_id"], assignment["uploaded_by"]):
        messages.error(request, "You do not have permission to edit this assignment.")
        return redirect("/e-learning")
        
    grades = ["Form 1", "Form 2", "Form 3", "Form 4", "Form 5", "Form 6"]
    subjects = dict_rows("SELECT subject_id, subject_code, subject_name, grade FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")
    years = [2026, 2025, 2024]
    
    role = normalized_role(request.user)
    if role == ROLE_TEACHER:
        assigned_sub_ids = assigned_subject_ids_for_teacher(request.user)
        subjects = [s for s in subjects if s["subject_id"] in assigned_sub_ids]
        
    if request.method == "POST":
        title = request.POST.get("title")
        grade = request.POST.get("grade")
        class_stream = request.POST.get("class_stream")
        subject_id = request.POST.get("subject_id")
        term = request.POST.get("term")
        year = request.POST.get("year")
        instructions = request.POST.get("instructions") or ""
        due_date = request.POST.get("due_date") or None
        max_score = request.POST.get("max_score") or "100"
        status = request.POST.get("status") or "Open"
        
        if role == ROLE_TEACHER:
            if not check_teacher_assignment_access(request.user, grade, class_stream, subject_id):
                messages.error(request, f"You do not have permission to assign to {grade} - {class_stream} in this subject.")
                return redirect(request.path)
                
        data = {
            "title": title,
            "grade": grade,
            "class_stream": class_stream,
            "subject_id": int(subject_id) if subject_id else None,
            "term": term,
            "year": int(year),
            "instructions": instructions,
            "due_date": due_date,
            "max_score": float(max_score) if max_score else 100.0,
            "status": status,
            "updated_at": now_text()
        }
        
        if request.FILES.get("file"):
            try:
                file_path, original_filename = save_uploaded_assignment_file(request.FILES["file"])
                data["file_path"] = file_path
                data["original_filename"] = original_filename
            except Exception as exc:
                messages.error(request, f"Failed to upload file: {exc}")
                
        try:
            update_record(request, "e_learning_assignments", "assignment_id", assignment_id, data)
            messages.success(request, "Assignment updated.")
            return redirect(f"/e-learning/{assignment_id}")
        except Exception as exc:
            messages.error(request, f"Could not update assignment: {exc}")
            
    context = {
        "title": "Edit E-learning Assignment",
        "grades": grades,
        "subjects": subjects,
        "years": years,
        "assignment": assignment,
        "settings": settings,
    }
    return render(request, "academics/assignment_form.html", context)


@permission_required("elearning.manage")
def e_learning_delete(request, assignment_id):
    from school_system_django.native import one_row
    assignment = one_row("SELECT * FROM e_learning_assignments WHERE assignment_id = %s", [assignment_id])
    if assignment:
        from accounts.permissions import check_teacher_assignment_access
        if not check_teacher_assignment_access(request.user, assignment["grade"], assignment["class_stream"], assignment["subject_id"], assignment["uploaded_by"]):
            messages.error(request, "You do not have permission to delete this assignment.")
            return redirect("/e-learning")
    return delete_record(request, "E-learning Assignment", "e_learning_assignments", "assignment_id", assignment_id, "/e-learning")


def download(request, file_type, item_id):
    from pathlib import Path
    from school_system_django.native import one_row, table_exists
    from accounts.permissions import check_teacher_assignment_access, normalized_role, user_has_permission

    has_access = False
    if request.user.is_authenticated and user_has_permission(request.user, "elearning.manage"):
        if normalized_role(request.user) != "Teacher":
            has_access = True
        elif file_type == "submission":
            row = one_row(
                """
                SELECT sub.submission_id, a.grade, a.class_stream, a.subject_id, a.uploaded_by
                FROM e_learning_submissions sub
                JOIN e_learning_assignments a ON a.assignment_id = sub.assignment_id
                WHERE sub.submission_id = %s
                """,
                [item_id],
            ) if table_exists("e_learning_submissions") else None
            has_access = bool(
                row
                and check_teacher_assignment_access(
                    request.user,
                    row["grade"],
                    row["class_stream"],
                    row["subject_id"],
                    row["uploaded_by"],
                )
            )
        elif file_type in {"assignment", "note"}:
            table = {"assignment": "e_learning_assignments", "note": "e_learning_notes"}[file_type]
            pk = {"assignment": "assignment_id", "note": "note_id"}[file_type]
            row = one_row(f"SELECT * FROM {table} WHERE {pk} = %s", [item_id]) if table_exists(table) else None
            has_access = bool(
                row
                and check_teacher_assignment_access(
                    request.user,
                    row.get("grade"),
                    row.get("class_stream"),
                    row.get("subject_id"),
                    row.get("uploaded_by"),
                )
            )
    elif request.session.get("student_pupil_id"):
        pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [request.session.get("student_pupil_id")])
        if file_type == "submission":
            has_access = bool(
                table_exists("e_learning_submissions")
                and one_row(
                    "SELECT submission_id FROM e_learning_submissions WHERE submission_id = %s AND pupil_id = %s",
                    [item_id, request.session.get("student_pupil_id")],
                )
            )
        elif file_type in {"assignment", "note"} and pupil:
            table = {"assignment": "e_learning_assignments", "note": "e_learning_notes"}[file_type]
            pk = {"assignment": "assignment_id", "note": "note_id"}[file_type]
            row = one_row(
                f"""
                SELECT *
                FROM {table}
                WHERE {pk} = %s
                  AND grade = %s
                  AND (class_stream = %s OR class_stream = 'All Streams' OR class_stream IS NULL OR TRIM(class_stream) = '')
                """,
                [item_id, pupil.get("grade"), pupil.get("class_stream") or ""],
            ) if table_exists(table) else None
            if row and row.get("subject_id") and table_exists("student_subjects"):
                has_access = bool(
                    one_row(
                        "SELECT id FROM student_subjects WHERE pupil_id = %s AND subject_id = %s AND academic_year = %s",
                        [pupil["pupil_id"], row["subject_id"], row.get("year")],
                    )
                )
            else:
                has_access = bool(row)

    redirect_target = "/student-portal/e-learning" if request.session.get("student_pupil_id") else "/e-learning"

    if not has_access:
        messages.error(request, "You do not have permission to download this file.")
        return redirect(redirect_target)

    table = {"assignment": "e_learning_assignments", "note": "e_learning_notes", "submission": "e_learning_submissions"}.get(file_type)
    pk = {"assignment": "assignment_id", "note": "note_id", "submission": "submission_id"}.get(file_type)
    if not table:
        messages.error(request, "Unknown file type.")
        return redirect(redirect_target)
    row = one_row(f"SELECT file_path, original_filename FROM {table} WHERE {pk} = %s", [item_id])
    if not row or not row.get("file_path"):
        messages.error(request, "The requested file could not be found.")
        return redirect(redirect_target)
        
    path_obj = Path(row["file_path"])
    if not path_obj.exists():
        path_obj = Path("uploads") / row["file_path"]
        
    if not path_obj.exists():
        messages.error(request, "The requested file could not be found on the server.")
        return redirect(redirect_target)
        
    return FileResponse(open(path_obj, "rb"), as_attachment=True, filename=row.get("original_filename") or path_obj.name)


@permission_required("elearning.manage")
def mark_submission(request, submission_id):
    submission = one_row(
        """
        SELECT sub.*, a.grade, a.class_stream, a.subject_id, a.uploaded_by
        FROM e_learning_submissions sub
        JOIN e_learning_assignments a ON a.assignment_id = sub.assignment_id
        WHERE sub.submission_id = %s
        """,
        [submission_id],
    )
    if not submission:
        messages.error(request, "Submission was not found.")
        return redirect("/e-learning")
    from accounts.permissions import check_teacher_assignment_access
    if not check_teacher_assignment_access(
        request.user,
        submission["grade"],
        submission["class_stream"],
        submission["subject_id"],
        submission["uploaded_by"],
    ):
        messages.error(request, "You do not have permission to mark this submission.")
        return redirect("/e-learning")
    if request.method == "POST":
        return update_record_fields(
            request,
            "e_learning_submissions",
            "submission_id",
            submission_id,
            {"score": request.POST.get("score"), "feedback": request.POST.get("feedback"), "status": "Marked", "marked_at": today_text()},
            "Submission marked.",
            "/e-learning",
        )
    fields = [
        {"name": "score", "label": "Score", "type": "number"},
        {"name": "feedback", "label": "Feedback", "widget": "textarea"},
    ]
    from django.shortcuts import render

    return render(request, "school/form_page.html", {"title": "Mark Submission", "subtitle": "Enter score and feedback.", "fields": fields})


@permission_required("library.manage")
def library(request):
    q = (request.GET.get("q") or "").strip()
    rows = library_book_rows(q)
    return render_rows_page(
        request,
        "Library",
        rows,
        ["title", "author", "isbn", "category", "total_copies", "available_copies", "issued_count", "overdue_count", "fine_per_day", "status", "stock_status"],
        "Books, textbook loans, returns, overdue counts, and fines.",
        actions=[
            {"label": "New Book", "href": "/library/new", "icon": "bi-plus-circle"},
            {"label": "Issue Textbook", "href": "/textbook-loans/new", "icon": "bi-book-half"},
        ],
        row_actions=[
            {"label": "Edit", "href": "/library/{book_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/library/{book_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this library book?"},
        ],
        total=len(rows),
        page=1,
        per_page=max(len(rows), 10),
    )


def library_book_form_fields(row=None):
    row = row or {}
    return [
        {"name": "title", "label": "Title", "value": row.get("title", ""), "required": True, "col_class": "col-md-6"},
        {"name": "author", "label": "Author", "value": row.get("author", ""), "col_class": "col-md-6"},
        {"name": "isbn", "label": "ISBN", "value": row.get("isbn", ""), "col_class": "col-md-4"},
        {"name": "category", "label": "Category", "value": row.get("category", ""), "col_class": "col-md-4"},
        {"name": "total_copies", "label": "Total Copies", "type": "number", "value": row.get("total_copies", 1), "required": True, "col_class": "col-md-4"},
        {"name": "fine_per_day", "label": "Fine Per Day", "type": "number", "value": row.get("fine_per_day", 0), "col_class": "col-md-4"},
        {"name": "status", "label": "Status", "widget": "select", "options": ["Active", "Inactive", "Archived"], "value": row.get("status") or "Active", "col_class": "col-md-4"},
    ]


def posted_library_book_data(request, book_id=None, current_row=None):
    title = (request.POST.get("title") or "").strip()
    if not title:
        raise ValueError("Book title is required.")
    total_copies = clean_int(request.POST.get("total_copies"), "Total copies")
    if total_copies < 0:
        raise ValueError("Total copies cannot be negative.")
    active_count = 0
    if book_id:
        active_count = active_textbook_loan_count(book_id=book_id, title=(current_row or {}).get("title")) + active_library_issue_count(book_id)
        if total_copies < active_count:
            raise ValueError(f"Total copies cannot be below {active_count}, because {active_count} copy/copies are currently issued.")
    return {
        "title": title,
        "author": (request.POST.get("author") or "").strip(),
        "isbn": (request.POST.get("isbn") or "").strip(),
        "category": (request.POST.get("category") or "").strip(),
        "total_copies": total_copies,
        "available_copies": max(total_copies - active_count, 0),
        "fine_per_day": request.POST.get("fine_per_day") or "0",
        "status": request.POST.get("status") or "Active",
    }


@permission_required("library.manage")
def library_new(request):
    fields = library_book_form_fields({"total_copies": 1, "fine_per_day": 0, "status": "Active"})
    if request.method == "POST":
        try:
            data = posted_library_book_data(request)
            book_id = insert_record(request, "library_books", data)
            if book_id:
                sync_book_availability(book_id)
            messages.success(request, "Library book saved.")
            return redirect("/library")
        except Exception as exc:
            messages.error(request, f"Could not save library book: {exc}")
            fields = library_book_form_fields(request.POST)
    return render(request, "school/form_page.html", {"title": "New Library Book", "subtitle": "Register a book and its real copy count.", "fields": fields, "settings": school_settings()})


@permission_required("library.manage")
def library_edit(request, book_id):
    row = one_row("SELECT * FROM library_books WHERE book_id = %s", [book_id])
    if not row:
        messages.error(request, "Library book was not found.")
        return redirect("/library")
    fields = library_book_form_fields(row)
    if request.method == "POST":
        try:
            data = posted_library_book_data(request, book_id=book_id, current_row=row)
            update_record(request, "library_books", "book_id", book_id, data)
            sync_book_availability(book_id)
            messages.success(request, "Library book updated.")
            return redirect("/library")
        except Exception as exc:
            messages.error(request, f"Could not update library book: {exc}")
            fields = library_book_form_fields({**row, **request.POST})
    return render(request, "school/form_page.html", {"title": "Edit Library Book", "subtitle": row.get("title"), "fields": fields, "settings": school_settings()})


@permission_required("library.manage")
def library_delete(request, book_id):
    book = one_row("SELECT * FROM library_books WHERE book_id = %s", [book_id])
    if not book:
        messages.error(request, "Library book was not found.")
        return redirect("/library")
    active_count = active_textbook_loan_count(book_id=book_id, title=book.get("title")) + active_library_issue_count(book_id)
    if active_count:
        messages.error(request, f"Cannot delete '{book['title']}' because {active_count} copy/copies are still issued.")
        return redirect("/library")
    return delete_record(request, "Library Book", "library_books", "book_id", book_id, "/library")


@permission_required("library.manage")
def return_library_book(request, issue_id):
    issue = one_row("SELECT * FROM library_issues WHERE issue_id = %s", [issue_id])
    if not issue:
        messages.error(request, "Library issue was not found.")
        return redirect("/library")
    update_record(request, "library_issues", "issue_id", issue_id, {"status": "Returned", "return_date": today_text()})
    sync_book_availability(issue.get("book_id"))
    messages.success(request, "Library book marked as returned and stock updated.")
    return redirect("/library")


def save_uploaded_note_file(uploaded_file):
    import os
    import uuid
    from datetime import datetime
    
    base_dir = "uploads"
    target_dir = os.path.join(base_dir, "notes")
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    ext = os.path.splitext(uploaded_file.name)[1]
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{ext}"
    target_path = os.path.join(target_dir, unique_name)
    
    with open(target_path, "wb+") as destination:
        for chunk in uploaded_file.chunks():
            destination.write(chunk)
            
    return os.path.join("notes", unique_name), uploaded_file.name


@permission_required("elearning.manage")
def e_learning_note_new(request):
    from school_system_django.native import school_settings, dict_rows, insert_record, legacy_user_id, now_text
    
    settings = school_settings()
    grades = ["Form 1", "Form 2", "Form 3", "Form 4", "Form 5", "Form 6"]
    subjects = dict_rows("SELECT subject_id, subject_code, subject_name, grade FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")
    years = [2026, 2025, 2024]
    
    from accounts.permissions import normalized_role, ROLE_TEACHER, assigned_subject_ids_for_teacher, check_teacher_assignment_access
    role = normalized_role(request.user)
    if role == ROLE_TEACHER:
        assigned_sub_ids = assigned_subject_ids_for_teacher(request.user)
        subjects = [s for s in subjects if s["subject_id"] in assigned_sub_ids]
        
    if request.method == "POST":
        grade = request.POST.get("grade")
        class_stream = request.POST.get("class_stream")
        subject_id = request.POST.get("subject_id")
        
        if role == ROLE_TEACHER:
            if not check_teacher_assignment_access(request.user, grade, class_stream, subject_id):
                messages.error(request, f"You do not have permission to upload notes for {grade} - {class_stream} in this subject.")
                return redirect(request.path)
                
        title = request.POST.get("title")
        term = request.POST.get("term")
        year = request.POST.get("year")
        description = request.POST.get("description") or ""
        
        file_path = None
        original_filename = None
        
        if request.FILES.get("file"):
            try:
                file_path, original_filename = save_uploaded_note_file(request.FILES["file"])
            except Exception as exc:
                messages.error(request, f"Failed to upload file: {exc}")
                
        data = {
            "title": title,
            "grade": grade,
            "class_stream": class_stream,
            "subject_id": int(subject_id) if subject_id else None,
            "term": term,
            "year": int(year),
            "description": description,
            "file_path": file_path,
            "original_filename": original_filename,
            "uploaded_by": legacy_user_id(request),
            "uploaded_at": now_text(),
        }
        
        try:
            insert_record(request, "e_learning_notes", data)
            messages.success(request, "Study note uploaded successfully.")
            return redirect("/e-learning")
        except Exception as exc:
            messages.error(request, f"Could not upload note: {exc}")
            
    context = {
        "title": "Upload Study Note",
        "grades": grades,
        "subjects": subjects,
        "years": years,
        "settings": settings,
    }
    return render(request, "academics/note_form.html", context)


@permission_required("elearning.manage")
def e_learning_note_delete(request, note_id):
    note = one_row("SELECT * FROM e_learning_notes WHERE note_id = %s", [note_id])
    if note:
        from accounts.permissions import check_teacher_assignment_access
        if not check_teacher_assignment_access(request.user, note["grade"], note["class_stream"], note["subject_id"], note["uploaded_by"]):
            messages.error(request, "You do not have permission to delete this study note.")
            return redirect("/e-learning")
    if note and note.get("file_path"):
        try:
            import os
            path = os.path.join("uploads", note["file_path"])
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass
    return delete_record(request, "Study Note", "e_learning_notes", "note_id", note_id, "/e-learning")

# Create your views here.
