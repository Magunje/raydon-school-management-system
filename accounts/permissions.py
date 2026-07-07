from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


ROLE_SUPER_ADMIN = "Super Admin"
ROLE_ADMIN = "Administrator"
ROLE_HEAD = "Headmaster"
ROLE_HEAD_ALT = "Headmaster / Headmistress"
ROLE_DEPUTY_HEAD = "Deputy Head"
ROLE_HOD = "HOD"
ROLE_BURSAR = "Bursar / Accounts Clerk"
ROLE_ACCOUNTANT = "Accountant"
ROLE_REGISTRAR = "Registrar / Office Clerk"
ROLE_CLERK = "Clerk"
ROLE_TEACHER = "Teacher"
ROLE_LIBRARIAN = "Librarian"
ROLE_TRANSPORT = "Transport Staff"
ROLE_HOSTEL = "Hostel Staff"
ROLE_NURSE = "Nurse"
ROLE_PARENT = "Parent"
ROLE_STUDENT = "Student"

ADMIN_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN}
HEAD_ROLES = {ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD}
ACADEMIC_LEADERSHIP_ROLES = HEAD_ROLES | {ROLE_HOD}
FINANCE_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_BURSAR, ROLE_ACCOUNTANT}
ARCHIVE_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_BURSAR}
PAYROLL_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_BURSAR, ROLE_ACCOUNTANT}
ACADEMIC_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_HOD, ROLE_TEACHER}
REGISTRAR_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_REGISTRAR, ROLE_CLERK}
LIBRARY_ROLES = {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_LIBRARIAN}
STUDENT_SUPPORT_ROLES = {ROLE_TRANSPORT, ROLE_HOSTEL, ROLE_NURSE}
STAFF_ROLES = (
    ADMIN_ROLES
    | HEAD_ROLES
    | {ROLE_HOD, ROLE_BURSAR, ROLE_ACCOUNTANT, ROLE_REGISTRAR, ROLE_CLERK, ROLE_TEACHER, ROLE_LIBRARIAN}
    | STUDENT_SUPPORT_ROLES
)
OPERATIONS_ROLES = STAFF_ROLES


PERMISSIONS = {
    "dashboard.view": OPERATIONS_ROLES | FINANCE_ROLES | {ROLE_STUDENT, ROLE_PARENT},
    "users.manage": ADMIN_ROLES,
    "saas.manage": {ROLE_SUPER_ADMIN},
    "settings.manage": ADMIN_ROLES,
    "audit.view": ADMIN_ROLES,
    "backups.manage": ADMIN_ROLES,
    "students.view": OPERATIONS_ROLES | {ROLE_BURSAR, ROLE_ACCOUNTANT},
    "students.manage": REGISTRAR_ROLES | {ROLE_BURSAR, ROLE_ACCOUNTANT},
    "students.archive.view": ARCHIVE_ROLES,
    "guardians.manage": REGISTRAR_ROLES | {ROLE_BURSAR, ROLE_ACCOUNTANT},
    "staff.view": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD},
    "classes.view": ACADEMIC_ROLES,
    "classes.manage": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_HOD},
    "subject_allocations.manage": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_HOD},
    "timetable.view": ACADEMIC_ROLES,
    "timetable.manage": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_HOD},
    "attendance.manage": ACADEMIC_ROLES,
    "fees.view": FINANCE_ROLES,
    "statements.view": FINANCE_ROLES | {ROLE_REGISTRAR},
    "fees.manage": FINANCE_ROLES,
    "payments.record": {ROLE_BURSAR, ROLE_ACCOUNTANT},
    "receipts.edit": ADMIN_ROLES,
    "receipts.delete": {ROLE_SUPER_ADMIN},
    "reports.view": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_BURSAR, ROLE_ACCOUNTANT, ROLE_REGISTRAR},
    "expenses.manage": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_BURSAR, ROLE_ACCOUNTANT},
    "master_receipts.manage": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT},
    "inventory.manage": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_BURSAR, ROLE_ACCOUNTANT, ROLE_LIBRARIAN},
    "pos.manage": {ROLE_BURSAR},
    "results.manage": ACADEMIC_ROLES,
    "results.publish": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT},
    "notifications.manage": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_REGISTRAR, ROLE_CLERK},
    "elearning.manage": ACADEMIC_ROLES,
    "library.manage": LIBRARY_ROLES,
    "payroll.view": PAYROLL_ROLES,
    "payroll.process": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_BURSAR, ROLE_ACCOUNTANT},
    "payroll.approve": {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT},
}


MENU_ITEMS = [
    {"label": "Dashboard", "href": "/dashboard", "icon": "bi-grid-1x2", "permission": "dashboard.view"},
    {"label": "Staff Portal", "href": "/staff-portal", "icon": "bi-person-workspace", "permission": "dashboard.view"},
    {"label": "Students", "href": "/pupils", "icon": "bi-mortarboard", "permission": "students.view"},
    {"label": "Register Student", "href": "/pupils/register", "icon": "bi-person-plus", "permission": "students.manage"},
    {"label": "Archive Database", "href": "/completed-students", "icon": "bi-archive", "permission": "students.archive.view"},
    {"label": "Parents", "href": "/guardians", "icon": "bi-people", "permission": "guardians.manage"},
    {"label": "Staff", "href": "/teachers", "icon": "bi-person-badge", "permission": "staff.view"},
    {"label": "Classes", "href": "/classes", "icon": "bi-journal-bookmark", "permission": "classes.view"},
    {"label": "Subjects", "href": "/subjects", "icon": "bi-book", "permission": "classes.view"},
    {"label": "Subject Allocations", "href": "/allocations", "icon": "bi-bookmark-star", "permission": "subject_allocations.manage"},
    {"label": "Timetables", "href": "/timetables", "icon": "bi-calendar3", "permission": "timetable.view"},
    {"label": "Attendance", "href": "/attendance", "icon": "bi-calendar-check", "permission": "attendance.manage"},
    {"label": "Attendance Ledger", "href": "/attendance/ledger", "icon": "bi-calendar-range", "permission": "attendance.manage"},
    {"label": "Results Centre", "href": "/results", "icon": "bi-clipboard-data", "permission": "results.manage"},
    {"label": "Results & Analytics", "href": "/results/centre", "icon": "bi-graph-up-arrow", "permission": "results.manage"},
    {"label": "E-Learning", "href": "/e-learning", "icon": "bi-cloud-arrow-up", "permission": "elearning.manage"},
    {"label": "Announcements", "href": "/notifications/announcements/", "icon": "bi-megaphone", "permission": "notifications.manage"},
    {"label": "Textbooks", "href": "/textbook-loans", "icon": "bi-book-half", "permission": "library.manage"},
    {"label": "Library", "href": "/library", "icon": "bi-bookshelf", "permission": "library.manage"},
    {"label": "Fees Structure", "href": "/fees-structure", "icon": "bi-list-columns", "permission": "fees.manage"},
    {"label": "Payments", "href": "/payments", "icon": "bi-receipt", "permission": "fees.view"},
    {"label": "Record Payment", "href": "/payments/new", "icon": "bi-plus-circle", "permission": "payments.record"},
    {"label": "Portal Payments", "href": "/portal-payment-requests", "icon": "bi-bank", "permission": "fees.manage"},
    {"label": "Statements", "href": "/reports/statement", "icon": "bi-file-text", "permission": "statements.view"},
    {"label": "Reports", "href": "/reports", "icon": "bi-file-earmark-text", "permission": "reports.view"},
    {"label": "Expenses", "href": "/expenses", "icon": "bi-wallet2", "permission": "expenses.manage"},
    {"label": "General Ledger", "href": "/reports/accounting", "icon": "bi-journal-check", "permission": "expenses.manage"},
    {"label": "Master Receipts", "href": "/master-receipts", "icon": "bi-receipt-cutoff", "permission": "master_receipts.manage"},
    {"label": "Inventory", "href": "/inventory", "icon": "bi-box-seam", "permission": "inventory.manage"},
    {"label": "Bursar POS", "href": "/uniform-pos", "icon": "bi-shop", "permission": "pos.manage"},
    {"label": "Payroll", "href": "/payroll/", "icon": "bi-cash-stack", "permission": "payroll.view"},
    {"label": "Users", "href": "/users", "icon": "bi-person-gear", "permission": "users.manage"},
    {"label": "Settings", "href": "/settings", "icon": "bi-gear", "permission": "settings.manage"},
    {"label": "Backups", "href": "/backups", "icon": "bi-database", "permission": "backups.manage"},
    {"label": "Audit Trail", "href": "/audit-trail", "icon": "bi-shield-check", "permission": "audit.view"},
    {"label": "SaaS Tenants", "href": "/admin/saas_tenant_management/schooltenant/", "icon": "bi-building-gear", "permission": "saas.manage"},
    {"label": "Website", "href": "/", "icon": "bi-globe", "permission": "dashboard.view"},
]

STUDENT_MENU_ITEMS = [
    {"label": "Dashboard", "href": "/student-portal", "icon": "bi-grid-1x2"},
    {"label": "My Profile", "href": "/student-portal/profile", "icon": "bi-person"},
    {"label": "Fees Statement", "href": "/student-portal/statement", "icon": "bi-wallet2"},
    {"label": "Pay Fees", "href": "/student-portal/pay", "icon": "bi-bank"},
    {"label": "Results", "href": "/student-portal/results", "icon": "bi-clipboard-data"},
    {"label": "Attendance", "href": "/student-portal/attendance", "icon": "bi-calendar-check"},
    {"label": "Timetable", "href": "/student-portal/timetable", "icon": "bi-calendar3"},
    {"label": "Textbooks", "href": "/student-portal/textbooks", "icon": "bi-book-half"},
    {"label": "E-Learning", "href": "/student-portal/e-learning", "icon": "bi-cloud-arrow-down"},
]


def normalized_role(user):
    if not user or not user.is_authenticated:
        return ""
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "status", "") and profile.status != "Active":
        return ""
    if user.is_superuser:
        return ROLE_SUPER_ADMIN
    return getattr(profile, "role", "") or ""


def is_staff_portal_role(role):
    return role in STAFF_ROLES or role == ROLE_SUPER_ADMIN


def role_has_permission(role, permission):
    if role == ROLE_SUPER_ADMIN:
        return True
    return role in PERMISSIONS.get(permission, set())


def user_has_permission(user, permission):
    return role_has_permission(normalized_role(user), permission)


def visible_menu(user):
    role = normalized_role(user)
    from saas_tenant_management.models import get_current_tenant
    current_tenant = get_current_tenant()
    
    items = []
    for item in MENU_ITEMS:
        # SaaS Tenants option is only visible on the master portal domain
        if item["label"] == "SaaS Tenants" and current_tenant is not None:
            continue
        if role_has_permission(role, item["permission"]):
            items.append(item)
    return items


def audit_denied(request, permission):
    try:
        from school_system_django.native import audit_action

        audit_action(request, "Unauthorized access", f"Denied {permission} at {request.path}")
    except Exception:
        pass


def permission_required(permission):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if user_has_permission(request.user, permission):
                return view_func(request, *args, **kwargs)
            audit_denied(request, permission)
            messages.error(request, "Your role is not allowed to open that page.")
            return redirect("accounts:dashboard")

        return wrapped

    return decorator


def assigned_classes_for_teacher(user):
    from school_system_django.native import dict_rows
    
    role = normalized_role(user)
    if role in {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_HOD}:
        rows = dict_rows("SELECT class_id FROM classes")
        return [r["class_id"] for r in rows]
        
    profile = getattr(user, "profile", None)
    if not profile:
        return []
        
    profile_id = profile.id
    full_name = profile.full_name or ""
    
    params = [profile_id]
    query = "SELECT class_id FROM classes WHERE class_teacher_id = %s"
    if full_name:
        query += " OR UPPER(class_teacher) = %s"
        params.append(full_name.upper().strip())
        
    rows_teacher = dict_rows(query, params)
    class_ids = {r["class_id"] for r in rows_teacher}
    
    # Also add classes where the teacher has subject allocations
    rows_allocated = dict_rows("SELECT DISTINCT class_id FROM timetable_subjectallocation WHERE teacher_id = %s", [profile_id])
    for r in rows_allocated:
        class_ids.add(r["class_id"])
            
    return list(class_ids)


def assigned_subject_ids_for_teacher(user, class_id=None):
    from school_system_django.native import dict_rows
    
    role = normalized_role(user)
    if role in {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_HOD}:
        rows = dict_rows("SELECT subject_id FROM subjects WHERE status = 'Active'")
        return {r["subject_id"] for r in rows}
        
    profile = getattr(user, "profile", None)
    if not profile:
        return set()
        
    profile_id = profile.id
    if class_id:
        rows = dict_rows("SELECT DISTINCT subject_id FROM timetable_subjectallocation WHERE teacher_id = %s AND class_id = %s", [profile_id, class_id])
    else:
        rows = dict_rows("SELECT DISTINCT subject_id FROM timetable_subjectallocation WHERE teacher_id = %s", [profile_id])
        
    return {r["subject_id"] for r in rows}


def check_teacher_assignment_access(user, grade, class_stream, subject_id, uploaded_by=None):
    role = normalized_role(user)
    if role in {ROLE_SUPER_ADMIN, ROLE_ADMIN, ROLE_HEAD, ROLE_HEAD_ALT, ROLE_DEPUTY_HEAD, ROLE_HOD}:
        return True
        
    profile = getattr(user, "profile", None)
    if not profile:
        return False
        
    # Check if the user uploaded it
    if uploaded_by is not None:
        legacy_id = getattr(profile, "legacy_user_id", None) or profile.id
        if int(uploaded_by) == int(legacy_id):
            return True
            
    # Check allocation
    from school_system_django.native import one_row
    
    # First find class matching the grade and stream
    c = one_row(
        """
        SELECT c.class_id FROM classes c
        JOIN grades g ON g.grade_id = c.grade_id
        WHERE g.grade_name = %s AND (c.class_name = %s OR %s = 'All Streams')
        LIMIT 1
        """,
        [grade, class_stream, class_stream]
    )
    if not c:
        return False
        
    class_id = c["class_id"]
    # Check if a subject allocation exists for this teacher, class, and subject
    alloc = one_row(
        "SELECT 1 FROM timetable_subjectallocation WHERE teacher_id = %s AND class_id = %s AND subject_id = %s LIMIT 1",
        [profile.id, class_id, int(subject_id)]
    )
    return alloc is not None
