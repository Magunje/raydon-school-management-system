import hashlib
import secrets

from django.contrib import messages
from datetime import datetime, timedelta

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .portal_access import clear_portal_session_state, is_school_admin_user, safe_next_url, set_active_portal
from .permissions import is_staff_portal_role, normalized_role, permission_required, user_has_permission
from .password_validation import validate_password_strength
from fees.services import dashboard_metrics, ensure_current_term_bills_for_active_students
from students.services import run_yearly_student_progression
from school_system_django.native import audit_action, delete_record, dict_rows, insert_record, now_text, one_row, render_detail_page, render_table_page, school_settings, today_text
from .services import (
    admission_no_for_user_save,
    ensure_existing_staff_admission_numbers,
    has_staff_admission_column,
    is_staff_role,
    next_staff_admission_no,
)


USER_FORM_FIELDS = [
    {"name": "admission_no", "label": "Admission Number", "readonly": True, "help_text": "Generated automatically for staff in AS001 sequence."},
    {"name": "username", "label": "Username"},
    {"name": "full_name", "label": "Full name"},
    {"name": "role", "label": "Role", "widget": "select", "options": ["Super Admin", "Administrator", "Headmaster", "Headmaster / Headmistress", "Deputy Head", "HOD", "Bursar / Accounts Clerk", "Accountant", "Registrar / Office Clerk", "Clerk", "Teacher", "Librarian", "Transport Staff", "Hostel Staff", "Nurse", "Parent", "Student"]},
    {"name": "status", "label": "Status", "widget": "select", "options": ["Active", "Inactive"]},
    {"name": "password", "label": "Password", "help_text": "At least 8 characters, including letters and numbers."},
]


def role_options_for(user, current_role=None):
    options = list(USER_FORM_FIELDS[3]["options"])
    if normalized_role(user) != "Super Admin":
        if current_role == "Super Admin":
            return ["Super Admin"]
        options = [role for role in options if role != "Super Admin"]
    return options


def home(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    return redirect("accounts:login")


def login_view(request):
    if request.user.is_authenticated and is_school_admin_user(request.user):
        set_active_portal(request, "school_admin")
        return redirect("school_admin:dashboard")

    lockout_key = "staff_login_lockout_until"
    failed_key = "staff_login_failed_attempts"
    identifier_key = "staff_login_identifier"
    locked_until = request.session.get(lockout_key)
    now = timezone.now()
    lockout_until_dt = None
    if locked_until:
        try:
            lockout_until_dt = datetime.fromisoformat(locked_until)
            if timezone.is_naive(lockout_until_dt):
                lockout_until_dt = timezone.make_aware(lockout_until_dt, timezone.get_current_timezone())
        except (TypeError, ValueError):
            lockout_until_dt = None
    if lockout_until_dt and lockout_until_dt <= now:
        request.session.pop(lockout_key, None)
        request.session.pop(failed_key, None)
        request.session.pop(identifier_key, None)
        lockout_until_dt = None

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == "POST":
        identifier = (request.POST.get("username") or "").strip().lower()
        if lockout_until_dt and lockout_until_dt > now:
            minutes = max(1, int((lockout_until_dt - now).total_seconds() // 60) + 1)
            form.add_error(None, f"Too many failed attempts. Try again in {minutes} minute(s).")
            audit_action(request, "Failed staff login locked", f"Blocked staff login for {identifier or 'unknown'}")
        elif form.is_valid():
            user = form.get_user()
            role = normalized_role(user)
            if not is_staff_portal_role(role):
                form.add_error(None, "This account is not allowed to use the staff portal.")
                audit_action(request, "Denied staff login", f"{user.username} attempted staff portal login with role {role or '-'}")
            else:
                auth_login(request, user)
                clear_portal_session_state(request)
                set_active_portal(request, "school_admin")
                request.session.pop(lockout_key, None)
                request.session.pop(failed_key, None)
                request.session.pop(identifier_key, None)
                audit_action(request, "Login", f"{user.username} signed in")
                messages.success(request, "Signed in successfully.")
                next_target = request.GET.get("next")
                if next_target and next_target.startswith(("/student-portal/", "/staff-portal/")):
                    next_target = None
                next_url = safe_next_url(request, next_target, "/", reverse("school_admin:dashboard"))
                return redirect(next_url)
        else:
            previous_identifier = request.session.get(identifier_key)
            failed_count = int(request.session.get(failed_key, 0) or 0)
            failed_count = failed_count + 1 if previous_identifier == identifier else 1
            request.session[identifier_key] = identifier
            request.session[failed_key] = failed_count
            audit_action(request, "Failed staff login", f"Failed staff login for {identifier or 'unknown'}")
            if failed_count >= 5:
                until = now + timedelta(minutes=15)
                request.session[lockout_key] = until.isoformat()
                form.add_error(None, "Too many failed attempts. This login is locked for 15 minutes.")

    return render(request, "accounts/login.html", {"form": form})


def logout_view(request):
    if request.user.is_authenticated:
        audit_action(request, "Logout", f"{request.user.username} signed out")
    clear_portal_session_state(request)
    auth_logout(request)
    messages.success(request, "Signed out successfully.")
    return redirect("school_admin:login")


@login_required
def dashboard(request):
    role = normalized_role(request.user)
    
    is_saas_portal = False
    if hasattr(request, "tenant") and request.tenant is None:
        is_saas_portal = True

    if is_saas_portal:
        from saas_tenant_management.models import SchoolTenant
        saas_stats = {
            "total_schools": SchoolTenant.objects.count(),
            "active_schools": SchoolTenant.objects.filter(active=True).count(),
            "basic_schools": SchoolTenant.objects.filter(subscription_plan="BASIC").count(),
            "premium_schools": SchoolTenant.objects.filter(subscription_plan="PREMIUM").count(),
            "elite_schools": SchoolTenant.objects.filter(subscription_plan="ELITE").count(),
            "backups": count_sql("SELECT COUNT(*) AS total FROM database_backups_log"),
            "recent_audit": safe_rows("SELECT username, action, details, created_at FROM audit_log ORDER BY audit_id DESC LIMIT 5"),
            "schools": SchoolTenant.objects.all().order_by("name"),
        }
        return render(
            request,
            "accounts/dashboard.html",
            {
                "base_template": "saas_admin/base.html",
                "is_saas_portal": True,
                "dashboard_role": "SaaS Platform Administrator",
                "saas_stats": saas_stats,
            },
        )

    settings = school_settings()
    auto_billing_stats = {}
    if user_has_permission(request.user, "students.archive.view"):
        try:
            progression_stats = run_yearly_student_progression()
            if progression_stats.get("promoted") or progression_stats.get("completed"):
                messages.success(
                    request,
                    f"Yearly progression completed: {progression_stats['promoted']} promoted, {progression_stats['completed']} moved to Pending ZIMSEC Analysis, {progression_stats.get('archived', 0)} archived.",
                )
        except Exception as exc:
            messages.warning(request, f"Yearly student progression could not run: {exc}")
    if user_has_permission(request.user, "fees.manage"):
        try:
            auto_billing_stats = ensure_current_term_bills_for_active_students()
            if auto_billing_stats.get("created"):
                messages.success(
                    request,
                    f"Auto term billing created {auto_billing_stats['created']} bill(s) for {auto_billing_stats['term']} {auto_billing_stats['year']}.",
                )
        except Exception as exc:
            messages.warning(request, f"Auto term billing could not run: {exc}")
    fees_dashboard = {}
    if user_has_permission(request.user, "fees.view"):
        try:
            fees_dashboard = dashboard_metrics()
        except Exception:
            fees_dashboard = {}
    operations = dashboard_operations()
    staff_portal = {}
    try:
        from staff.services import staff_dashboard_context

        staff_portal = staff_dashboard_context(request)
        staff_counts = staff_portal.get("counts", {})
        if role == "Teacher":
            operations.update(
                {
                    "total_students": staff_counts.get("active_students", 0),
                    "attendance_today": staff_counts.get("attendance_today", 0),
                    "results_pending": staff_counts.get("pending_results", 0),
                    "published_results": staff_counts.get("published_results", 0),
                    "assignments": staff_counts.get("assignments", 0),
                    "submissions": staff_counts.get("submissions", 0),
                }
            )
    except Exception:
        staff_portal = {}
    payroll_stats = {}
    try:
        from payroll.models import EmployeePayrollProfile, PayrollPeriod, PayrollRun

        latest_period = PayrollPeriod.objects.order_by("-year", "-month").first()
        payroll_stats = {
            "active_profiles": EmployeePayrollProfile.objects.filter(employment_status="Active").count(),
            "periods": PayrollPeriod.objects.count(),
            "latest_period": latest_period,
            "latest_net": PayrollRun.objects.filter(period=latest_period).aggregate(total=Sum("net_salary"))["total"] if latest_period else 0,
        }
    except Exception:
        payroll_stats = {"active_profiles": 0, "periods": 0, "latest_period": None, "latest_net": 0}

    return render(
        request,
        "accounts/dashboard.html",
        {
            "base_template": "school_admin/base.html",
            "dashboard_role": role,
            "settings": settings,
            "operations": operations,
            "payroll_stats": payroll_stats,
            "fees_dashboard": fees_dashboard,
            "show_finance": user_has_permission(request.user, "fees.view"),
            "show_payroll": user_has_permission(request.user, "payroll.view"),
            "show_admin": user_has_permission(request.user, "users.manage"),
            "show_academics": user_has_permission(request.user, "results.manage"),
            "show_library": user_has_permission(request.user, "library.manage"),
            "auto_billing_stats": auto_billing_stats,
            "staff_portal": staff_portal,
        },
    )


def count_sql(sql, params=None):
    try:
        row = one_row(sql, params or [])
        return int(row["total"] or 0) if row else 0
    except Exception:
        return 0


def safe_rows(sql, params=None):
    try:
        return dict_rows(sql, params or [])
    except Exception:
        return []


def dashboard_operations():
    today = today_text()
    return {
        "total_students": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE COALESCE(status, 'Active') = 'Active'"),
        "o_level_students": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE COALESCE(status, 'Active') = 'Active' AND grade_id BETWEEN 1 AND 4"),
        "a_level_students": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE COALESCE(status, 'Active') = 'Active' AND grade_id BETWEEN 5 AND 6"),
        "pending_o_level_zimsec": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE status = 'Pending ZIMSEC Analysis' AND (grade_id = 7 OR grade LIKE '%Completed O%' OR grade LIKE '%O Level%')"),
        "pending_a_level_zimsec": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE status = 'Pending ZIMSEC Analysis' AND (grade_id = 8 OR grade LIKE '%Completed A%' OR grade LIKE '%A Level%')"),
        "archived_o_level": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE status = 'Permanently Archived' AND (grade_id = 7 OR grade LIKE '%Completed O%' OR grade LIKE '%O Level%')"),
        "archived_a_level": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE status = 'Permanently Archived' AND (grade_id = 8 OR grade LIKE '%Completed A%' OR grade LIKE '%A Level%')"),
        "reactivated_a_level": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE status_reason LIKE '%Reactivated for A Level%'"),
        "retained_students": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE COALESCE(status, '') != 'Active'"),
        "new_admissions": count_sql("SELECT COUNT(*) AS total FROM pupils WHERE admission_date = %s", [today]),
        "guardians": count_sql("SELECT COUNT(*) AS total FROM guardians"),
        "staff": count_sql("SELECT COUNT(*) AS total FROM users WHERE role NOT IN ('Student', 'Parent')"),
        "teacher_profiles": count_sql("SELECT COUNT(*) AS total FROM teacher_profiles"),
        "attendance_today": count_sql("SELECT COUNT(*) AS total FROM attendance_records WHERE attendance_date = %s", [today]),
        "teacher_attendance_today": count_sql("SELECT COUNT(*) AS total FROM teacher_attendance_records WHERE attendance_date = %s", [today]),
        "results_pending": count_sql("SELECT COUNT(*) AS total FROM result_sheets WHERE COALESCE(status, '') != 'Published'"),
        "published_results": count_sql("SELECT COUNT(*) AS total FROM result_sheets WHERE status = 'Published'"),
        "assignments": count_sql("SELECT COUNT(*) AS total FROM e_learning_assignments"),
        "submissions": count_sql("SELECT COUNT(*) AS total FROM e_learning_submissions WHERE status = 'Submitted'"),
        "books_issued": count_sql("SELECT COUNT(*) AS total FROM library_issues WHERE status != 'Returned'"),
        "textbooks_issued": count_sql("SELECT COUNT(*) AS total FROM textbook_loans WHERE status != 'Returned'"),
        "overdue_textbooks": count_sql("SELECT COUNT(*) AS total FROM textbook_loans WHERE status != 'Returned' AND return_date < %s", [today]),
        "inventory_items": count_sql("SELECT COUNT(*) AS total FROM inventory_items"),
        "low_stock": count_sql("SELECT COUNT(*) AS total FROM inventory_items WHERE quantity <= reorder_level"),
        "pending_bank": count_sql("SELECT COUNT(*) AS total FROM online_payment_requests WHERE status IN ('Pending', 'Pending Verification')"),
        "audit_entries": count_sql("SELECT COUNT(*) AS total FROM audit_log"),
        "backups": count_sql("SELECT COUNT(*) AS total FROM database_backups_log"),
        "recent_audit": safe_rows("SELECT username, action, details, created_at FROM audit_log ORDER BY audit_id DESC LIMIT 5"),
    }


@permission_required("users.manage")
def users(request):
    ensure_existing_staff_admission_numbers()
    return render_table_page(
        request,
        "User Accounts",
        "users",
        ["admission_no", "full_name", "username", "role", "status", "created_at"],
        "Django user and role management.",
        order_by="user_id DESC",
        search_columns=["admission_no", "full_name", "username", "role"],
        pk_column="user_id",
        create_href="/users/new",
        create_label="New User",
        row_actions=[
            {"label": "View", "href": "/users/{user_id}", "icon": "bi-eye", "class": "btn-outline-primary"},
            {"label": "Edit", "href": "/users/{user_id}/edit", "icon": "bi-pencil", "class": "btn-outline-secondary"},
            {"label": "Delete", "href": "/users/{user_id}/delete", "icon": "bi-trash", "class": "btn-outline-danger", "method": "post", "confirm": "Delete this user?"},
        ],
    )


@permission_required("users.manage")
def edit_user(request, user_id):
    return user_form(request, user_id)


def legacy_password_hash(password):
    salt = secrets.token_hex(8)
    n, r, p = 32768, 8, 1
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("utf-8"), n=n, r=r, p=p, dklen=64, maxmem=64 * 1024 * 1024)
    return f"scrypt:{n}:{r}:{p}${salt}${derived.hex()}"


@permission_required("users.manage")
def user_detail(request, user_id):
    return render_detail_page(request, "User Account", "users", "user_id", user_id)


@permission_required("users.manage")
def new_user(request):
    return user_form(request)


def sync_django_user(legacy_user_id):
    from django.contrib.auth import get_user_model
    from .models import UserProfile

    row = one_row("SELECT * FROM users WHERE user_id = %s", [legacy_user_id])
    if not row:
        return
    UserModel = get_user_model()
    user, _created = UserModel.objects.get_or_create(username=row["username"])
    user.is_active = row.get("status") == "Active"
    user.is_staff = row.get("role") in {"Super Admin", "Administrator", "Headmaster", "Headmaster / Headmistress"}
    user.is_superuser = row.get("role") == "Super Admin"
    user.set_unusable_password()
    if row.get("full_name"):
        parts = row["full_name"].split(" ", 1)
        user.first_name = parts[0][:150]
        user.last_name = parts[1][:150] if len(parts) > 1 else ""
    user.save()
    UserProfile.objects.update_or_create(
        user=user,
        defaults={"legacy_user_id": legacy_user_id, "full_name": row.get("full_name") or row["username"], "role": row.get("role") or "Teacher", "status": row.get("status") or "Active"},
    )


@permission_required("users.manage")
def user_form(request, user_id=None):
    ensure_existing_staff_admission_numbers()
    row = one_row("SELECT * FROM users WHERE user_id = %s", [user_id]) if user_id else {}
    if user_id and not row:
        messages.error(request, "User was not found.")
        return redirect("/users")
    current_operator_role = normalized_role(request.user)
    if row.get("role") == "Super Admin" and current_operator_role != "Super Admin":
        messages.error(request, "Only Super Admin can edit a Super Admin account.")
        return redirect("/users")
    fields = []
    for field in USER_FORM_FIELDS:
        if field["name"] == "admission_no" and not has_staff_admission_column():
            continue
        item = dict(field)
        if item["name"] == "role":
            item["options"] = role_options_for(request.user, row.get("role"))
        if item["name"] == "admission_no" and not user_id:
            item["value"] = next_staff_admission_no()
        elif item["name"] != "password":
            item["value"] = row.get(item["name"], "")
        elif user_id:
            item["placeholder"] = "Leave blank to keep current password"
        fields.append(item)
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = (request.POST.get("password") or "").strip()
        if not username:
            messages.error(request, "Username is required.")
        elif not user_id and not password:
            messages.error(request, "Password is required for a new user.")
        else:
            data = {
                "username": username,
                "full_name": request.POST.get("full_name") or username,
                "role": request.POST.get("role") or "Teacher",
                "status": request.POST.get("status") or "Active",
            }
            if data["role"] == "Super Admin" and current_operator_role != "Super Admin":
                messages.error(request, "Only Super Admin can create or assign the Super Admin role.")
                return render(request, "school/form_page.html", {"title": "Edit User" if user_id else "New User", "subtitle": "Role and login access.", "fields": fields})
            if row.get("role") == "Super Admin" and data["role"] != "Super Admin" and current_operator_role != "Super Admin":
                messages.error(request, "Only Super Admin can change a Super Admin role.")
                return render(request, "school/form_page.html", {"title": "Edit User" if user_id else "New User", "subtitle": "Role and login access.", "fields": fields})
            staff_admission_no = admission_no_for_user_save(row, data["role"])
            if has_staff_admission_column():
                data["admission_no"] = staff_admission_no if is_staff_role(data["role"]) else None
            try:
                if password:
                    validate_password_strength(password)
                    data["password_hash"] = legacy_password_hash(password)
                if user_id:
                    assignments = ", ".join(f"{column} = %s" for column in data)
                    with connection.cursor() as cursor:
                        cursor.execute(f"UPDATE users SET {assignments} WHERE user_id = %s", list(data.values()) + [user_id])
                    sync_django_user(user_id)
                    messages.success(request, "User updated.")
                    return redirect(f"/users/{user_id}")
                data["created_at"] = now_text()
                new_id = insert_record(request, "users", data)
                if not new_id:
                    created = one_row("SELECT user_id FROM users WHERE username = %s", [username])
                    new_id = created["user_id"] if created else None
                if new_id:
                    sync_django_user(new_id)
                messages.success(request, "User created.")
                return redirect("/users")
            except Exception as exc:
                messages.error(request, f"Could not save user: {exc}")
    return render(request, "school/form_page.html", {"title": "Edit User" if user_id else "New User", "subtitle": "Role and login access.", "fields": fields})


@permission_required("users.manage")
def delete_user(request, user_id):
    row = one_row("SELECT role FROM users WHERE user_id = %s", [user_id])
    if row and row.get("role") == "Super Admin" and normalized_role(request.user) != "Super Admin":
        messages.error(request, "Only Super Admin can delete a Super Admin account.")
        return redirect("/users")
    return delete_record(request, "User", "users", "user_id", user_id, "/users")


@login_required
def change_password(request):
    from django.shortcuts import render, redirect
    from django.contrib import messages
    from accounts.backends import LegacyUserBackend
    from school_system_django.native import connection
    
    profile = getattr(request.user, "profile", None)
    if not profile or profile.legacy_user_id is None:
        messages.error(request, "Only staff accounts can change password on this portal.")
        return redirect("/dashboard")
        
    legacy_user_id = profile.legacy_user_id
    
    if request.method == "POST":
        current_password = request.POST.get("current_password")
        new_password = request.POST.get("new_password")
        confirm_password = request.POST.get("confirm_password")
        
        if not current_password or not new_password or not confirm_password:
            messages.error(request, "All password fields are required.")
        elif new_password != confirm_password:
            messages.error(request, "New password and confirmation do not match.")
        else:
            row = one_row("SELECT password_hash FROM users WHERE user_id = %s", [legacy_user_id])
            if not row:
                messages.error(request, "User record not found.")
            else:
                backend = LegacyUserBackend()
                if not backend.check_legacy_password(row["password_hash"], current_password):
                    messages.error(request, "Incorrect current password.")
                else:
                    try:
                        validate_password_strength(new_password)
                        new_hash = legacy_password_hash(new_password)
                        with connection.cursor() as cursor:
                            cursor.execute("UPDATE users SET password_hash = %s WHERE user_id = %s", [new_hash, legacy_user_id])
                        messages.success(request, "Password updated successfully.")
                        return redirect("/dashboard")
                    except Exception as e:
                        messages.error(request, f"Failed to update password: {e}")
                        
    return render(
        request,
        "accounts/change_password.html",
        {
            "title": "Change Password",
            "settings": school_settings(),
        }
    )


# Create your views here.
