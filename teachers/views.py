from django.contrib.auth.decorators import login_required

from accounts.permissions import permission_required
from school_system_django.native import delete_record, render_detail_page, render_record_form_page, render_table_page


TEACHER_PROFILE_FIELDS = ["user_id", "phone_number", "email", "qualifications", "workload_notes"]
TEACHER_ATTENDANCE_FIELDS = ["user_id", "attendance_date", "status", "notes"]


@permission_required("staff.view")
def profiles(request):
    return render_table_page(
        request,
        "Teacher Profiles",
        "teacher_profiles",
        ["profile_id", "user_id", "phone_number", "email", "qualifications", "workload_notes"],
        "Teacher qualifications, contact details, and workload notes.",
        order_by="profile_id DESC",
        search_columns=["phone_number", "email", "qualifications", "workload_notes"],
        pk_column="profile_id",
        create_href="/teachers/new",
        create_label="New Teacher",
        row_actions=[
            {"label": "View", "href": "/teachers/{profile_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/teachers/{profile_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/teachers/{profile_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this teacher profile?"},
        ],
    )


@permission_required("attendance.manage")
def attendance(request):
    return render_table_page(
        request,
        "Teacher Attendance",
        "teacher_attendance_records",
        ["attendance_id", "user_id", "attendance_date", "status", "notes"],
        "Teacher attendance register.",
        order_by="attendance_date DESC",
        search_columns=["status", "notes"],
        pk_column="attendance_id",
        create_href="/teacher-attendance/new",
        create_label="Mark Attendance",
        row_actions=[
            {"label": "Edit", "href": "/teacher-attendance/{attendance_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/teacher-attendance/{attendance_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this teacher attendance record?"},
        ],
    )


@permission_required("staff.view")
def detail(request, profile_id):
    return render_detail_page(request, "Teacher Profile", "teacher_profiles", "profile_id", profile_id)


@permission_required("users.manage")
def new(request):
    return render_record_form_page(request, "New Teacher Profile", "teacher_profiles", TEACHER_PROFILE_FIELDS, redirect_to="/teachers")


@permission_required("users.manage")
def edit(request, profile_id):
    return render_record_form_page(
        request,
        "Edit Teacher Profile",
        "teacher_profiles",
        TEACHER_PROFILE_FIELDS,
        pk_column="profile_id",
        pk_value=profile_id,
        redirect_to=f"/teachers/{profile_id}",
    )


@permission_required("users.manage")
def delete(request, profile_id):
    return delete_record(request, "Teacher Profile", "teacher_profiles", "profile_id", profile_id, "/teachers")


@permission_required("attendance.manage")
def attendance_new(request):
    return render_record_form_page(request, "Mark Teacher Attendance", "teacher_attendance_records", TEACHER_ATTENDANCE_FIELDS, redirect_to="/teacher-attendance")


@permission_required("attendance.manage")
def attendance_edit(request, attendance_id):
    return render_record_form_page(
        request,
        "Edit Teacher Attendance",
        "teacher_attendance_records",
        TEACHER_ATTENDANCE_FIELDS,
        pk_column="attendance_id",
        pk_value=attendance_id,
        redirect_to="/teacher-attendance",
    )


@permission_required("attendance.manage")
def attendance_delete(request, attendance_id):
    return delete_record(request, "Teacher Attendance", "teacher_attendance_records", "attendance_id", attendance_id, "/teacher-attendance")

# Create your views here.
