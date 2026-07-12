from school_system_django.native import one_row, school_settings, table_exists
from .decorators import PAYROLL_ROLES, user_full_name, user_role
from .permissions import STUDENT_MENU_ITEMS, user_has_permission, visible_menu


def school_context(request):
    role = user_role(request.user) if hasattr(request, "user") else ""
    
    is_saas_portal = False
    if hasattr(request, "tenant") and request.tenant is None:
        is_saas_portal = True

    if is_saas_portal:
        platform_settings = {}
        if table_exists("saas_platform_settings"):
            platform_settings = one_row("SELECT * FROM saas_platform_settings WHERE setting_id = 1") or {}
        app_title = platform_settings.get("admin_console_label") or "SaaS Admin Console"
        school_name_val = platform_settings.get("platform_name") or "Unified School SaaS Portal"
        current_term_val = ""
        current_year_val = ""
    else:
        settings = school_settings()
        app_title = settings.get("school_name") or "RAYDON HIGH SCHOOL"
        school_name_val = settings.get("school_name") or "RAYDON SCHOOL MANAGEMENT SYSTEM"
        current_term_val = settings.get("current_term") or ""
        current_year_val = settings.get("current_year") or ""

    # Adjust visible menu items to show ONLY platform management links on the SaaS admin portal!
    menu_items = []
    if request.user.is_authenticated:
        raw_items = visible_menu(request.user)
        if is_saas_portal:
            # Only allow platform management links
            saas_labels = {"Dashboard", "SaaS Tenants", "Users", "Settings", "Backups", "Audit Trail", "Website"}
            menu_items = [item for item in raw_items if item["label"] in saas_labels]
        else:
            # On a school tenant, hide the SaaS Tenants menu option
            menu_items = [item for item in raw_items if item["label"] != "SaaS Tenants"]
    
    return {
        "is_saas_portal": is_saas_portal,
        "app_title": app_title,
        "school_name": school_name_val,
        "current_role": role,
        "current_user_name": user_full_name(request.user) if request.user.is_authenticated else "",
        "current_term": current_term_val,
        "current_year": current_year_val,
        "calendar_status": settings.get("calendar_status") if not is_saas_portal else "",
        "next_term": settings.get("next_term") if not is_saas_portal else "",
        "next_term_start_date": settings.get("next_term_start_date") if not is_saas_portal else None,
        "visible_menu_items": menu_items,
        "student_menu_items": STUDENT_MENU_ITEMS,
        "can_manage_payroll": not is_saas_portal and request.user.is_authenticated and user_has_permission(request.user, "payroll.view"),
        "can_manage_users": request.user.is_authenticated and user_has_permission(request.user, "users.manage"),
        "can_manage_settings": request.user.is_authenticated and user_has_permission(request.user, "settings.manage"),
        "can_view_audit": request.user.is_authenticated and user_has_permission(request.user, "audit.view"),
    }
