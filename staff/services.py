from datetime import date, datetime
from decimal import Decimal
import json

from accounts.permissions import assigned_classes_for_teacher, normalized_role, user_has_permission
from school_system_django.native import (
    active_pupils_for_class,
    dict_rows,
    hydrate_class_labels,
    legacy_user_id,
    one_row,
    school_settings,
    table_exists,
    today_text,
)


STAFF_MODULES = [
    {"key": "students", "label": "Students", "href": "/pupils", "icon": "bi-mortarboard", "permission": "students.view"},
    {"key": "attendance", "label": "Attendance", "href": "/attendance", "icon": "bi-calendar-check", "permission": "attendance.manage"},
    {"key": "results", "label": "Results", "href": "/results", "icon": "bi-clipboard-data", "permission": "results.manage"},
    {"key": "elearning", "label": "E-Learning", "href": "/e-learning", "icon": "bi-cloud-arrow-up", "permission": "elearning.manage"},
    {"key": "timetable", "label": "Timetable", "href": "/timetables/grid", "icon": "bi-calendar3", "permission": "timetable.view"},
    {"key": "finance", "label": "Finance", "href": "/payments", "icon": "bi-receipt", "permission": "fees.view"},
    {"key": "portal_payments", "label": "Portal Payments", "href": "/portal-payment-requests", "icon": "bi-bank", "permission": "fees.manage"},
    {"key": "library", "label": "Library", "href": "/library", "icon": "bi-bookshelf", "permission": "library.manage"},
    {"key": "communications", "label": "Announcements", "href": "/notifications/announcements/", "icon": "bi-megaphone", "permission": "notifications.manage"},
    {"key": "staff", "label": "Staff", "href": "/teachers", "icon": "bi-person-badge", "permission": "staff.view"},
    {"key": "reports", "label": "Reports", "href": "/reports", "icon": "bi-file-earmark-text", "permission": "reports.view"},
]


def json_default(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def json_dumps(payload):
    return json.dumps(payload, default=json_default)


def is_staff_portal_user(user):
    role = normalized_role(user)
    return bool(role and role not in {"Student", "Parent"})


def _count(sql, params=None):
    try:
        row = one_row(sql, params or [])
        return int(row.get("total") or 0) if row else 0
    except Exception:
        return 0


def _rows(sql, params=None):
    try:
        return dict_rows(sql, params or [])
    except Exception:
        return []


def _in_clause(values):
    values = [int(value) for value in values or []]
    if not values:
        return "1 = 0", []
    return ", ".join(["%s"] * len(values)), values


def visible_staff_modules(user):
    return [module for module in STAFF_MODULES if user_has_permission(user, module["permission"])]


def staff_identity(user):
    profile = getattr(user, "profile", None)
    legacy_id = getattr(profile, "legacy_user_id", None)
    legacy_user = one_row("SELECT * FROM users WHERE user_id = %s", [legacy_id]) if legacy_id and table_exists("users") else {}
    teacher_profile = (
        one_row("SELECT * FROM teacher_profiles WHERE user_id = %s", [legacy_id])
        if legacy_id and table_exists("teacher_profiles")
        else {}
    )
    return {
        "username": getattr(user, "username", ""),
        "full_name": getattr(profile, "full_name", "") or getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", ""),
        "role": normalized_role(user),
        "status": getattr(profile, "status", "") or legacy_user.get("status") or "",
        "legacy_user_id": legacy_id,
        "staff_number": legacy_user.get("admission_no") or "",
        "email": teacher_profile.get("email") or "",
        "phone_number": teacher_profile.get("phone_number") or "",
        "qualifications": teacher_profile.get("qualifications") or "",
        "workload_notes": teacher_profile.get("workload_notes") or "",
    }


def assigned_class_rows(user):
    class_ids = assigned_classes_for_teacher(user)
    if not class_ids:
        return []
    placeholders, params = _in_clause(class_ids)
    rows = _rows(
        f"""
        SELECT c.class_id, c.class_name, c.grade_id, c.academic_year, c.class_teacher, g.grade_name
        FROM classes c
        LEFT JOIN grades g ON g.grade_id = c.grade_id
        WHERE c.class_id IN ({placeholders})
        ORDER BY c.academic_year DESC, c.class_name
        """,
        params,
    )
    rows = hydrate_class_labels(rows)
    for row in rows:
        try:
            row["student_count"] = len(active_pupils_for_class(row, row.get("grade_name") or "", select_fields="pupil_id"))
        except Exception:
            row["student_count"] = 0
    return rows


def assigned_subject_rows(user):
    role = normalized_role(user)
    if role in {"Super Admin", "Administrator", "Headmaster", "Headmaster / Headmistress", "Deputy Head", "HOD"}:
        return _rows("SELECT subject_id, subject_code, subject_name, grade FROM subjects WHERE status = 'Active' ORDER BY display_order, subject_name")
    profile = getattr(user, "profile", None)
    if not profile:
        return []
    return _rows(
        """
        SELECT DISTINCT s.subject_id, s.subject_code, s.subject_name, s.grade
        FROM timetable_subjectallocation tsa
        JOIN subjects s ON s.subject_id = tsa.subject_id
        WHERE tsa.teacher_id = %s AND s.status = 'Active'
        ORDER BY s.display_order, s.subject_name
        """,
        [profile.id],
    )


def _class_filter_for_user(user, pupil_alias="p"):
    role = normalized_role(user)
    if role != "Teacher":
        return "", []
    class_ids = assigned_classes_for_teacher(user)
    if not class_ids:
        return "1 = 0", []
    placeholders, params = _in_clause(class_ids)
    return f"{pupil_alias}.class_id IN ({placeholders})", params


def staff_counts(user):
    today = today_text()
    class_rows = assigned_class_rows(user)
    class_ids = [row["class_id"] for row in class_rows]
    class_placeholders, class_params = _in_clause(class_ids)

    student_where, student_params = _class_filter_for_user(user, "p")
    active_student_sql = "SELECT COUNT(*) AS total FROM pupils p WHERE COALESCE(p.status, 'Active') = 'Active'"
    if student_where:
        active_student_sql += f" AND {student_where}"

    attendance_sql = "SELECT COUNT(*) AS total FROM attendance_records ar WHERE ar.attendance_date = %s"
    attendance_params = [today]
    if normalized_role(user) == "Teacher":
        if class_ids:
            attendance_sql += f" AND ar.class_id IN ({class_placeholders})"
            attendance_params.extend(class_params)
        else:
            attendance_sql += " AND 1 = 0"

    result_sql = """
        SELECT COUNT(*) AS total
        FROM result_sheets r
        JOIN pupils p ON p.pupil_id = r.pupil_id
        WHERE COALESCE(r.status, '') != 'Published'
    """
    result_params = []
    if student_where:
        result_sql += f" AND {student_where}"
        result_params.extend(student_params)

    published_result_sql = result_sql.replace("COALESCE(r.status, '') != 'Published'", "r.status = 'Published'")
    published_result_params = list(result_params)

    assignment_sql, assignment_params = _assignment_count_query(user)

    return {
        "active_students": _count(active_student_sql, student_params),
        "assigned_classes": len(class_rows),
        "assigned_subjects": len(assigned_subject_rows(user)),
        "attendance_today": _count(attendance_sql, attendance_params),
        "pending_results": _count(result_sql, result_params),
        "published_results": _count(published_result_sql, published_result_params),
        "assignments": _count(assignment_sql, assignment_params),
        "submissions": _submission_count(user),
        "pending_portal_payments": _count("SELECT COUNT(*) AS total FROM online_payment_requests WHERE status IN ('Pending', 'Pending Verification')"),
        "books_issued": _count("SELECT COUNT(*) AS total FROM library_issues WHERE COALESCE(status, '') != 'Returned'"),
        "overdue_textbooks": _count("SELECT COUNT(*) AS total FROM textbook_loans WHERE COALESCE(status, '') != 'Returned' AND return_date < %s", [today]),
        "staff": _count("SELECT COUNT(*) AS total FROM users WHERE role NOT IN ('Student', 'Parent')"),
    }


def _assignment_count_query(user):
    where, params = _teacher_assignment_where(user, "a")
    if not where:
        return "SELECT COUNT(*) AS total FROM e_learning_assignments", []
    return f"SELECT COUNT(*) AS total FROM e_learning_assignments a WHERE {where}", params


def _teacher_assignment_where(user, alias="a"):
    if normalized_role(user) != "Teacher":
        return "", []
    profile = getattr(user, "profile", None)
    legacy_id = getattr(profile, "legacy_user_id", None) if profile else None
    if not profile:
        return "1 = 0", []
    return (
        f"""
        {alias}.uploaded_by = %s OR EXISTS (
            SELECT 1
            FROM timetable_subjectallocation sa
            JOIN classes c ON c.class_id = sa.class_id
            JOIN grades g ON g.grade_id = c.grade_id
            WHERE sa.teacher_id = %s
              AND g.grade_name = {alias}.grade
              AND (c.class_name = {alias}.class_stream OR {alias}.class_stream = 'All Streams')
              AND sa.subject_id = {alias}.subject_id
        )
        """,
        [legacy_id, profile.id],
    )


def _submission_count(user):
    where, params = _teacher_assignment_where(user, "a")
    sql = """
        SELECT COUNT(*) AS total
        FROM e_learning_submissions sub
        JOIN e_learning_assignments a ON a.assignment_id = sub.assignment_id
        WHERE sub.status = 'Submitted'
    """
    if where:
        sql += f" AND ({where})"
    return _count(sql, params)


def timetable_today(user):
    settings = school_settings()
    current_year = settings.get("current_year") or date.today().year
    day_name = date.today().strftime("%A")
    role = normalized_role(user)
    params = [current_year, day_name]
    where = "WHERE academic_year = %s AND day_name = %s"
    if role == "Teacher":
        class_ids = assigned_classes_for_teacher(user)
        full_name = staff_identity(user)["full_name"]
        if class_ids:
            placeholders, class_params = _in_clause(class_ids)
            where += f" AND (class_id IN ({placeholders}) OR UPPER(COALESCE(teacher_name, '')) = %s)"
            params.extend(class_params)
            params.append(full_name.upper().strip())
        else:
            where += " AND UPPER(COALESCE(teacher_name, '')) = %s"
            params.append(full_name.upper().strip())
    return _rows(
        f"""
        SELECT timetable_id, class_id, subject_name, teacher_name, room_name, period_no, start_time, end_time
        FROM class_timetable_entries
        {where}
        ORDER BY period_no
        LIMIT 10
        """,
        params,
    )


def recent_results(user):
    student_where, params = _class_filter_for_user(user, "p")
    where = ""
    if student_where:
        where = f"WHERE {student_where}"
    return _rows(
        f"""
        SELECT r.result_id, r.term, r.year, r.status, r.average_mark, p.admission_no, p.first_name, p.surname
        FROM result_sheets r
        JOIN pupils p ON p.pupil_id = r.pupil_id
        {where}
        ORDER BY r.updated_at DESC, r.result_id DESC
        LIMIT 8
        """,
        params,
    )


def recent_announcements():
    if table_exists("website_announcements"):
        return _rows(
            """
            SELECT title, audience, published_at, status
            FROM website_announcements
            ORDER BY announcement_id DESC
            LIMIT 5
            """
        )
    if table_exists("communication_log"):
        return _rows(
            """
            SELECT subject AS title, audience, created_at AS published_at, status
            FROM communication_log
            ORDER BY communication_id DESC
            LIMIT 5
            """
        )
    return []


def finance_summary(user):
    if not user_has_permission(user, "fees.view"):
        return {}
    try:
        from fees.services import dashboard_metrics

        return dashboard_metrics()
    except Exception:
        return {}


def staff_dashboard_context(request):
    user = request.user
    identity = staff_identity(user)
    return {
        "identity": identity,
        "modules": visible_staff_modules(user),
        "counts": staff_counts(user),
        "classes": assigned_class_rows(user),
        "subjects": assigned_subject_rows(user)[:12],
        "timetable_today": timetable_today(user),
        "recent_results": recent_results(user),
        "announcements": recent_announcements(),
        "finance_dashboard": finance_summary(user),
        "can_manage_announcements": user_has_permission(user, "notifications.manage"),
        "settings": school_settings(),
    }


def api_payload(request, module):
    context = staff_dashboard_context(request)
    module = (module or "dashboard").lower()
    if module == "dashboard":
        return {"ok": True, "dashboard": context}
    if module == "profile":
        return {"ok": True, "profile": context["identity"]}
    if module == "classes":
        return {"ok": True, "classes": context["classes"]}
    if module == "subjects":
        return {"ok": True, "subjects": assigned_subject_rows(request.user)}
    if module == "attendance":
        return {"ok": True, "attendance_today": context["counts"]["attendance_today"], "classes": context["classes"]}
    if module == "results":
        return {"ok": True, "pending": context["counts"]["pending_results"], "recent": context["recent_results"]}
    if module == "finance":
        if not user_has_permission(request.user, "fees.view"):
            return {"ok": False, "error": "permission_denied", "status": 403}
        return {"ok": True, "finance": context["finance_dashboard"]}
    if module == "library":
        if not user_has_permission(request.user, "library.manage"):
            return {"ok": False, "error": "permission_denied", "status": 403}
        return {"ok": True, "books_issued": context["counts"]["books_issued"], "overdue_textbooks": context["counts"]["overdue_textbooks"]}
    if module == "timetable":
        return {"ok": True, "today": context["timetable_today"]}
    if module == "announcements":
        return {"ok": True, "announcements": context["announcements"]}
    return {"ok": False, "error": "unknown_module", "status": 404}
