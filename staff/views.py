from functools import wraps

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render

from accounts.permissions import permission_required
from accounts.services import ensure_existing_staff_admission_numbers
from school_system_django.native import delete_record, render_detail_page, render_record_form_page, render_table_page
from .services import api_payload, is_staff_portal_user, staff_dashboard_context


STAFF_FIELDS = ["username", "full_name", "role", "status"]
STAFF_ATTENDANCE_FIELDS = ["user_id", "attendance_date", "status", "notes"]


@permission_required("staff.view")
def staff(request):
    ensure_existing_staff_admission_numbers()
    return render_table_page(
        request,
        "Staff Profiles",
        "users",
        ["admission_no", "full_name", "username", "role", "status", "created_at"],
        "Staff accounts, roles, and employment records.",
        order_by="full_name",
        search_columns=["admission_no", "full_name", "username", "role"],
        where="COALESCE(role, '') NOT IN ('Parent', 'Student')",
        pk_column="user_id",
        create_href="/users/new",
        create_label="New Staff User",
        row_actions=[
            {"label": "View", "href": "/users/{user_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/users/{user_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/users/{user_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this staff user?"},
        ],
    )


@permission_required("attendance.manage")
def attendance(request):
    return render_table_page(
        request,
        "Staff Attendance",
        "teacher_attendance_records",
        ["attendance_id", "user_id", "attendance_date", "status", "notes", "marked_by"],
        "Daily staff attendance register.",
        order_by="attendance_date DESC",
        search_columns=["status", "notes"],
        pk_column="attendance_id",
        create_href="/teacher-attendance/new",
        create_label="Mark Attendance",
        row_actions=[
            {"label": "Edit", "href": "/teacher-attendance/{attendance_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/teacher-attendance/{attendance_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this attendance record?"},
        ],
    )


@permission_required("dashboard.view")
def portal(request):
    if not is_staff_portal_user(request.user):
        messages.error(request, "This account is not allowed to use the staff portal.")
        return redirect("accounts:dashboard")
    return render(request, "staff/portal_dashboard.html", staff_dashboard_context(request))


@permission_required("dashboard.view")
def portal_profile(request):
    if not is_staff_portal_user(request.user):
        messages.error(request, "This account is not allowed to use the staff portal.")
        return redirect("accounts:dashboard")
    context = staff_dashboard_context(request)
    return render(request, "staff/portal_profile.html", context)


def staff_api_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"ok": False, "error": "authentication_required"}, status=401)
        if not is_staff_portal_user(request.user):
            return JsonResponse({"ok": False, "error": "permission_denied"}, status=403)
        return view_func(request, *args, **kwargs)

    return wrapped


@staff_api_required
def portal_api(request, module):
    payload = api_payload(request, module)
    status = int(payload.pop("status", 200))
    return JsonResponse(payload, status=status)


@permission_required("attendance.manage")
def attendance_new(request):
    return render_record_form_page(request, "Mark Staff Attendance", "teacher_attendance_records", STAFF_ATTENDANCE_FIELDS, redirect_to="/teacher-attendance")


@permission_required("attendance.manage")
def attendance_edit(request, attendance_id):
    return render_record_form_page(
        request,
        "Edit Staff Attendance",
        "teacher_attendance_records",
        STAFF_ATTENDANCE_FIELDS,
        pk_column="attendance_id",
        pk_value=attendance_id,
        redirect_to="/teacher-attendance",
    )


@permission_required("attendance.manage")
def attendance_delete(request, attendance_id):
    return delete_record(request, "Staff Attendance", "teacher_attendance_records", "attendance_id", attendance_id, "/teacher-attendance")

# Create your views here.
