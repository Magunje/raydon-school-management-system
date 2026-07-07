import json
import os
import uuid
from datetime import date, datetime
from decimal import Decimal

from saas_tenant_management.models import get_current_tenant
from school_system_django.native import (
    active_pupils_for_class,
    compact_class_label,
    dict_rows,
    one_row,
    resolve_legacy_class_record,
    school_settings,
    table_columns,
    table_exists,
    today_text,
)
from students.services import school_finish_date, student_age_text


ACTIVE_STUDENT_STATUSES = {"", "Active"}
BLOCKED_STUDENT_STATUSES = {"Inactive", "Transferred", "Withdrawn", "Suspended", "Permanent Archive", "Archived"}
LOGIN_MAX_ATTEMPTS = 5


def tenant_session_key(request):
    tenant = getattr(request, "tenant", None) or get_current_tenant()
    return str(getattr(tenant, "tenant_id", "") or "")


def rows_if_tables(tables, sql, params=None):
    if any(not table_exists(table) for table in tables):
        return []
    return dict_rows(sql, params or [])


def row_if_tables(tables, sql, params=None):
    rows = rows_if_tables(tables, sql, params)
    return rows[0] if rows else None


def decimal_json(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: decimal_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decimal_json(item) for item in value]
    return value


def json_dumps(value):
    return json.dumps(decimal_json(value))


def student_status_is_active(pupil):
    status = str((pupil or {}).get("status") or "Active").strip()
    return status in ACTIVE_STUDENT_STATUSES and status not in BLOCKED_STUDENT_STATUSES


def clear_student_session(request):
    for key in ("student_pupil_id", "student_admission_no", "student_tenant_id"):
        request.session.pop(key, None)


def set_student_session(request, pupil):
    request.session.cycle_key()
    request.session["student_pupil_id"] = pupil["pupil_id"]
    request.session["student_admission_no"] = pupil.get("admission_no") or ""
    request.session["student_tenant_id"] = tenant_session_key(request)


def current_student(request):
    if request.session.get("student_tenant_id") != tenant_session_key(request):
        clear_student_session(request)
        return None

    pupil_id = request.session.get("student_pupil_id")
    admission_no = request.session.get("student_admission_no")
    if not table_exists("pupils") or (not pupil_id and not admission_no):
        return None

    if pupil_id:
        pupil = one_row("SELECT * FROM pupils WHERE pupil_id = %s", [pupil_id])
    else:
        pupil = one_row("SELECT * FROM pupils WHERE UPPER(admission_no) = %s", [str(admission_no or "").upper()])

    if not pupil or not student_status_is_active(pupil):
        clear_student_session(request)
        return None
    return pupil


def student_lookup_for_login(identifier):
    if not table_exists("pupils"):
        return None
    lookup = str(identifier or "").strip().upper()
    if not lookup:
        return None

    columns = table_columns("pupils")
    clauses = ["UPPER(admission_no) = %s"]
    params = [lookup]
    for column in ("national_id", "email", "student_email", "username"):
        if column in columns:
            clauses.append(f"UPPER(COALESCE({column}, '')) = %s")
            params.append(lookup)

    if table_exists("users") and "admission_no" in table_columns("users"):
        user = one_row(
            """
            SELECT admission_no
            FROM users
            WHERE status = 'Active'
              AND role = 'Student'
              AND (UPPER(username) = %s OR UPPER(COALESCE(admission_no, '')) = %s)
            LIMIT 1
            """,
            [lookup, lookup],
        )
        if user and user.get("admission_no"):
            clauses.append("UPPER(admission_no) = %s")
            params.append(str(user["admission_no"]).upper())

    return one_row(
        f"SELECT * FROM pupils WHERE {' OR '.join(clauses)} LIMIT 1",
        params,
    )


def class_label(pupil):
    return compact_class_label(
        grade=pupil.get("grade"),
        stream=pupil.get("class_stream"),
        grade_id=pupil.get("grade_id"),
    )


def student_class_id(pupil):
    if pupil.get("class_id"):
        return pupil["class_id"]
    settings = school_settings()
    class_rec = resolve_legacy_class_record(
        grade=pupil.get("grade"),
        stream=pupil.get("class_stream"),
        grade_id=pupil.get("grade_id"),
        academic_year=settings.get("current_year") or today_text()[:4],
    )
    return class_rec["class_id"] if class_rec else None


def classmate_count(pupil):
    class_id = student_class_id(pupil)
    if not class_id:
        return 0
    selected_class = one_row("SELECT * FROM classes WHERE class_id = %s", [class_id])
    if not selected_class:
        return 0
    grade_row = one_row("SELECT grade_name FROM grades WHERE grade_id = %s", [selected_class.get("grade_id")])
    return len(active_pupils_for_class(selected_class, (grade_row or {}).get("grade_name") or "", "pupil_id"))


def attendance_summary(pupil_id):
    row = row_if_tables(
        ["attendance_records"],
        """
        SELECT
            COUNT(*) AS total_days,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_days,
            SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) AS late_days,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_days,
            SUM(CASE WHEN status IN ('Excused', 'Excused Absence') THEN 1 ELSE 0 END) AS excused_days
        FROM attendance_records
        WHERE pupil_id = %s
        """,
        [pupil_id],
    ) or {}
    total = int(row.get("total_days") or 0)
    present = int(row.get("present_days") or 0)
    late = int(row.get("late_days") or 0)
    absent = int(row.get("absent_days") or 0)
    excused = int(row.get("excused_days") or 0)
    percentage = ((present + late) / total * 100) if total else 0.0
    return {
        "total_days": total,
        "present_days": present,
        "late_days": late,
        "absent_days": absent,
        "excused_days": excused,
        "percentage": round(percentage, 1),
    }


def attendance_history(pupil_id, limit=120):
    return rows_if_tables(
        ["attendance_records"],
        """
        SELECT attendance_date, status, notes, marked_at, updated_at
        FROM attendance_records
        WHERE pupil_id = %s
        ORDER BY attendance_date DESC, attendance_id DESC
        LIMIT %s
        """,
        [pupil_id, limit],
    )


def portal_payments(pupil_id, limit=10):
    return rows_if_tables(
        ["payments"],
        """
        SELECT payment_id, receipt_no, reference_no, amount_paid, payment_date, payment_method, term, year
        FROM payments
        WHERE pupil_id = %s
        ORDER BY payment_date DESC, payment_id DESC
        LIMIT %s
        """,
        [pupil_id, limit],
    )


def pending_payment_requests(pupil_id, limit=5):
    return rows_if_tables(
        ["online_payment_requests"],
        """
        SELECT request_id, reference_no, amount, method, status, created_at, updated_at
        FROM online_payment_requests
        WHERE pupil_id = %s
        ORDER BY request_id DESC
        LIMIT %s
        """,
        [pupil_id, limit],
    )


def published_results(pupil_id, limit=None):
    limit_sql = "LIMIT %s" if limit else ""
    params = [pupil_id]
    if limit:
        params.append(limit)
    return rows_if_tables(
        ["result_sheets"],
        f"""
        SELECT result_id, term, year, status, total_marks, average_mark, class_position, grade_position,
               teacher_comment, headmaster_comment, published_at, next_term_fees
        FROM result_sheets
        WHERE pupil_id = %s AND status = 'Published'
        ORDER BY year DESC, term DESC, result_id DESC
        {limit_sql}
        """,
        params,
    )


def latest_result_entries(result_id):
    return rows_if_tables(
        ["result_entries"],
        """
        SELECT s.subject_name, e.mark, e.grade, e.subject_comment
        FROM result_entries e
        LEFT JOIN subjects s ON s.subject_id = e.subject_id
        WHERE e.result_id = %s
        ORDER BY s.display_order, s.subject_name
        """,
        [result_id],
    )


def subject_access_clause(alias, pupil):
    if not table_exists("student_subjects"):
        return "", []
    return (
        f"""
        AND (
            {alias}.subject_id IS NULL
            OR EXISTS (
                SELECT 1
                FROM student_subjects ss
                WHERE ss.pupil_id = %s
                  AND ss.subject_id = {alias}.subject_id
                  AND ss.academic_year = {alias}.year
            )
        )
        """,
        [pupil["pupil_id"]],
    )


def stream_params(pupil):
    return [pupil.get("grade") or "", pupil.get("class_stream") or ""]


def e_learning_context(pupil):
    access_sql, access_params = subject_access_clause("a", pupil)
    assignments = rows_if_tables(
        ["e_learning_assignments"],
        f"""
        SELECT a.assignment_id, a.title, a.term, a.year, a.instructions, a.due_date, a.status,
               a.original_filename, a.max_score, s.subject_name,
               sub.submission_id, sub.status AS submission_status, sub.score, sub.feedback,
               sub.original_filename AS submission_filename, sub.submitted_at, sub.updated_at AS submission_updated_at
        FROM e_learning_assignments a
        LEFT JOIN subjects s ON s.subject_id = a.subject_id
        LEFT JOIN e_learning_submissions sub ON sub.assignment_id = a.assignment_id AND sub.pupil_id = %s
        WHERE a.grade = %s
          AND (a.class_stream = %s OR a.class_stream = 'All Streams' OR a.class_stream IS NULL OR TRIM(a.class_stream) = '')
          {access_sql}
        ORDER BY a.due_date DESC, a.assignment_id DESC
        """,
        [pupil["pupil_id"]] + stream_params(pupil) + access_params,
    )

    note_access_sql, note_access_params = subject_access_clause("n", pupil)
    notes = rows_if_tables(
        ["e_learning_notes"],
        f"""
        SELECT n.note_id, n.title, n.term, n.year, n.description, n.uploaded_at, n.original_filename, s.subject_name
        FROM e_learning_notes n
        LEFT JOIN subjects s ON s.subject_id = n.subject_id
        WHERE n.grade = %s
          AND (n.class_stream = %s OR n.class_stream = 'All Streams' OR n.class_stream IS NULL OR TRIM(n.class_stream) = '')
          {note_access_sql}
        ORDER BY n.uploaded_at DESC, n.note_id DESC
        """,
        stream_params(pupil) + note_access_params,
    )
    due_open = [row for row in assignments if row.get("status") == "Open" and not row.get("submission_status")]
    return {"assignments": assignments, "notes": notes, "due_open": due_open}


def portal_assignment_for_student(pupil, assignment_id):
    access_sql, access_params = subject_access_clause("a", pupil)
    return row_if_tables(
        ["e_learning_assignments"],
        f"""
        SELECT a.*, s.subject_name
        FROM e_learning_assignments a
        LEFT JOIN subjects s ON s.subject_id = a.subject_id
        WHERE a.assignment_id = %s
          AND a.grade = %s
          AND (
              a.class_stream = %s
              OR a.class_stream = 'All Streams'
              OR a.class_stream IS NULL
              OR TRIM(a.class_stream) = ''
          )
          {access_sql}
        """,
        [assignment_id] + stream_params(pupil) + access_params,
    )


def timetable_context(pupil):
    class_id = student_class_id(pupil)
    timetable_entries = rows_if_tables(
        ["class_timetable_entries"],
        """
        SELECT day_name, day_order, period_no, start_time, end_time, subject_name, teacher_name, room_name
        FROM class_timetable_entries
        WHERE class_id = %s
        ORDER BY day_order, period_no
        """,
        [class_id],
    ) if class_id else []

    period_map = {}
    day_map = {}
    cell_map = {}
    for entry in timetable_entries:
        period_no = entry.get("period_no")
        day_order = entry.get("day_order")
        if period_no is not None:
            period_map[period_no] = {"period_no": period_no, "start_time": entry.get("start_time"), "end_time": entry.get("end_time")}
        if day_order is not None:
            day_map[day_order] = {"day_order": day_order, "day_name": entry.get("day_name")}
        cell_map[(day_order, period_no)] = entry

    periods = [period_map[key] for key in sorted(period_map)]
    days_list = [day_map[key] for key in sorted(day_map)]
    timetable_rows = [{"day_name": day["day_name"], "cells": [cell_map.get((day["day_order"], period["period_no"])) for period in periods]} for day in days_list]
    return {
        "class_id": class_id,
        "periods": periods,
        "timetable_rows": timetable_rows,
        "entries": timetable_entries,
    }


def textbook_rows(pupil_id):
    return rows_if_tables(
        ["textbook_loans"],
        """
        SELECT COALESCE(lb.title, tl.book_name) AS book_name, tl.borrowed_date, tl.return_date,
               tl.status, tl.cleared_date, tl.notes
        FROM textbook_loans tl
        LEFT JOIN library_books lb ON lb.book_id = tl.book_id
        WHERE tl.pupil_id = %s
        ORDER BY tl.borrowed_date DESC, tl.loan_id DESC
        """,
        [pupil_id],
    )


def overdue_textbook_count(pupil_id):
    row = row_if_tables(
        ["textbook_loans"],
        """
        SELECT COUNT(*) AS total
        FROM textbook_loans
        WHERE pupil_id = %s
          AND COALESCE(status, '') NOT IN ('Returned', 'Cleared', 'Cancelled')
          AND return_date IS NOT NULL
          AND return_date != ''
          AND return_date < %s
        """,
        [pupil_id, today_text()],
    )
    return int(row["total"] or 0) if row else 0


def portal_announcements(limit=5):
    if table_exists("website_announcements"):
        columns = table_columns("website_announcements")
        title_col = "title" if "title" in columns else "headline" if "headline" in columns else None
        body_col = "message" if "message" in columns else "content" if "content" in columns else None
        date_col = "created_at" if "created_at" in columns else "published_at" if "published_at" in columns else None
        if title_col:
            return dict_rows(
                f"""
                SELECT {title_col} AS title, {body_col or title_col} AS body, {date_col or title_col} AS created_at
                FROM website_announcements
                ORDER BY {date_col or title_col} DESC
                LIMIT %s
                """,
                [limit],
            )
    return []


def profile_sections(pupil):
    return [
        {
            "title": "Personal Details",
            "items": [
                ("Admission Number", pupil.get("admission_no")),
                ("Full Name", f"{pupil.get('first_name') or ''} {pupil.get('surname') or ''}".strip()),
                ("Gender", pupil.get("gender")),
                ("Date of Birth", pupil.get("date_of_birth")),
                ("Age", student_age_text(pupil.get("date_of_birth"))),
                ("National ID", pupil.get("national_id")),
                ("Status", pupil.get("status") or "Active"),
            ],
        },
        {
            "title": "Academic Placement",
            "items": [
                ("Class", class_label(pupil)),
                ("Current Term", school_settings().get("current_term")),
                ("Academic Year", school_settings().get("current_year")),
                ("Admission Date", pupil.get("admission_date")),
                ("School Finish Date", school_finish_date(pupil)),
                ("Class Size", classmate_count(pupil)),
            ],
        },
        {
            "title": "Guardian and Care",
            "items": [
                ("Guardian", pupil.get("guardian_name")),
                ("Guardian Phone", pupil.get("guardian_phone")),
                ("Address", pupil.get("address")),
                ("Medical Notes", pupil.get("medical_notes")),
                ("Remarks", pupil.get("remarks")),
            ],
        },
    ]


def dashboard_context(pupil):
    from fees.services import student_financial_summary

    attendance = attendance_summary(pupil["pupil_id"])
    results = published_results(pupil["pupil_id"], limit=6)
    latest_entries = latest_result_entries(results[0]["result_id"]) if results else []
    elearning = e_learning_context(pupil)
    timetable = timetable_context(pupil)
    payments = portal_payments(pupil["pupil_id"], limit=6)
    pending_payments = pending_payment_requests(pupil["pupil_id"], limit=5)
    summary = student_financial_summary(pupil=pupil)
    textbooks = textbook_rows(pupil["pupil_id"])
    overdue = overdue_textbook_count(pupil["pupil_id"])
    today_name = datetime.now().strftime("%A")
    timetable_today = [row for row in timetable["entries"] if row.get("day_name") == today_name]
    return {
        "pupil": pupil,
        "class_label": class_label(pupil),
        "class_size": classmate_count(pupil),
        "attendance": attendance,
        "payments": payments,
        "pending_payments": pending_payments,
        "results": results,
        "latest_result_entries": latest_entries,
        "summary": summary,
        "assignments_due": elearning["due_open"],
        "assignments": elearning["assignments"],
        "notes": elearning["notes"],
        "timetable_today": timetable_today,
        "textbooks": textbooks,
        "overdue_textbooks": overdue,
        "announcements": portal_announcements(),
        "settings": school_settings(),
    }


def tenant_submission_path(filename):
    tenant_key = str(get_current_tenant().tenant_id) if get_current_tenant() else "global"
    ext = os.path.splitext(filename)[1]
    unique_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:10]}{ext}"
    relative = os.path.join("submissions", tenant_key, unique_name)
    return relative, os.path.join("uploads", relative)
