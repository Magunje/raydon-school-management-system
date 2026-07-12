from functools import wraps

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from accounts.portal_access import (
    clear_portal_session_state,
    is_school_admin_user,
    is_staff_portal_user,
    safe_next_url,
    set_active_portal,
    staff_portal_required,
)
from accounts.permissions import permission_required
from accounts.services import ensure_existing_staff_admission_numbers
from school_system_django.native import delete_record, render_detail_page, render_record_form_page, render_table_page
from .services import api_payload, staff_dashboard_context


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


def portal_login(request):
    if request.user.is_authenticated and is_staff_portal_user(request.user):
        set_active_portal(request, "staff_portal")
        return redirect("staff_portal:dashboard")

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if is_school_admin_user(user) or not is_staff_portal_user(user):
            form.add_error(None, "This account is not allowed to use the Staff Portal.")
        else:
            auth_login(request, user)
            clear_portal_session_state(request)
            set_active_portal(request, "staff_portal")
            messages.success(request, "Signed in successfully.")
            next_url = safe_next_url(request, request.GET.get("next"), "/staff-portal/", reverse("staff_portal:dashboard"))
            return redirect(next_url)

    response = render(request, "staff_portal/login.html", {"form": form})
    response["Cache-Control"] = "no-store"
    return response


def portal_logout(request):
    clear_portal_session_state(request)
    auth_logout(request)
    messages.success(request, "Signed out of the Staff Portal.")
    return redirect("staff_portal:login")


@staff_portal_required
def portal(request):
    return render(request, "staff/portal_dashboard.html", staff_dashboard_context(request))


@staff_portal_required
def portal_profile(request):
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
