from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings as django_settings
from django.db import connection
from django.http import FileResponse
from django.shortcuts import redirect, render
from pathlib import Path
import shutil

from accounts.permissions import permission_required
from school_system_django.native import audit_action, dict_rows, insert_record, legacy_user_id, now_text, one_row, render_record_form_page, render_table_page


SAAS_PORTAL_HOSTS = {"saas.localhost", "saas.raydonsystem.com", "admin.localhost"}


def is_saas_portal_request(request):
    if not hasattr(request, "tenant") or request.tenant is not None:
        return False
    host_header = request.get_host().split(":")[0].lower()
    return host_header in SAAS_PORTAL_HOSTS


def ensure_saas_platform_settings_table():
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS saas_platform_settings (
                setting_id INTEGER PRIMARY KEY,
                platform_name TEXT NOT NULL DEFAULT 'Unified School SaaS Portal',
                admin_console_label TEXT NOT NULL DEFAULT 'SaaS Admin Console',
                support_email TEXT DEFAULT '',
                support_phone TEXT DEFAULT '',
                billing_contact_email TEXT DEFAULT '',
                default_subscription_plan TEXT NOT NULL DEFAULT 'BASIC',
                default_trial_days INTEGER NOT NULL DEFAULT 14,
                backup_retention_days INTEGER NOT NULL DEFAULT 30,
                tenant_domain_suffix TEXT DEFAULT '.localhost',
                tenant_auto_provisioning INTEGER NOT NULL DEFAULT 1,
                allow_public_signup INTEGER NOT NULL DEFAULT 0,
                maintenance_mode INTEGER NOT NULL DEFAULT 0,
                platform_notes TEXT DEFAULT '',
                updated_at TEXT DEFAULT ''
            )
            """
        )
        cursor.execute("SELECT COUNT(*) FROM saas_platform_settings WHERE setting_id = %s", [1])
        exists = cursor.fetchone()[0]
        if not exists:
            cursor.execute(
                """
                INSERT INTO saas_platform_settings (
                    setting_id,
                    platform_name,
                    admin_console_label,
                    default_subscription_plan,
                    default_trial_days,
                    backup_retention_days,
                    tenant_domain_suffix,
                    tenant_auto_provisioning,
                    allow_public_signup,
                    maintenance_mode,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    1,
                    "Unified School SaaS Portal",
                    "SaaS Admin Console",
                    "BASIC",
                    14,
                    30,
                    ".localhost",
                    1,
                    0,
                    0,
                    now_text(),
                ],
            )


def get_saas_platform_settings():
    ensure_saas_platform_settings_table()
    return one_row("SELECT * FROM saas_platform_settings WHERE setting_id = 1") or {}


def coerce_int(value, default, minimum=0):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return max(result, minimum)


def saas_platform_stats():
    try:
        from saas_tenant_management.models import SchoolTenant

        tenants = list(SchoolTenant.objects.all().order_by("name"))
        total = len(tenants)
        active = sum(1 for tenant in tenants if tenant.active)
        return {
            "total_schools": total,
            "active_schools": active,
            "suspended_schools": total - active,
            "basic_schools": sum(1 for tenant in tenants if tenant.subscription_plan == "BASIC"),
            "premium_schools": sum(1 for tenant in tenants if tenant.subscription_plan == "PREMIUM"),
            "elite_schools": sum(1 for tenant in tenants if tenant.subscription_plan == "ELITE"),
            "schools": tenants[:8],
        }
    except Exception:
        return {
            "total_schools": 0,
            "active_schools": 0,
            "suspended_schools": 0,
            "basic_schools": 0,
            "premium_schools": 0,
            "elite_schools": 0,
            "schools": [],
        }


def saas_settings(request):
    platform_settings = get_saas_platform_settings()
    if request.method == "POST":
        default_plan = request.POST.get("default_subscription_plan") or "BASIC"
        if default_plan not in {"BASIC", "PREMIUM", "ELITE"}:
            default_plan = "BASIC"
        payload = {
            "platform_name": (request.POST.get("platform_name") or "").strip() or "Unified School SaaS Portal",
            "admin_console_label": (request.POST.get("admin_console_label") or "").strip() or "SaaS Admin Console",
            "support_email": (request.POST.get("support_email") or "").strip(),
            "support_phone": (request.POST.get("support_phone") or "").strip(),
            "billing_contact_email": (request.POST.get("billing_contact_email") or "").strip(),
            "default_subscription_plan": default_plan,
            "default_trial_days": coerce_int(request.POST.get("default_trial_days"), 14),
            "backup_retention_days": coerce_int(request.POST.get("backup_retention_days"), 30),
            "tenant_domain_suffix": (request.POST.get("tenant_domain_suffix") or "").strip() or ".localhost",
            "tenant_auto_provisioning": 1 if request.POST.get("tenant_auto_provisioning") else 0,
            "allow_public_signup": 1 if request.POST.get("allow_public_signup") else 0,
            "maintenance_mode": 1 if request.POST.get("maintenance_mode") else 0,
            "platform_notes": (request.POST.get("platform_notes") or "").strip(),
            "updated_at": now_text(),
        }
        names = list(payload)
        assignments = ", ".join(f"{name} = %s" for name in names)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE saas_platform_settings SET {assignments} WHERE setting_id = %s",
                [payload[name] for name in names] + [1],
            )
        audit_action(request, "Update SaaS platform settings", "Updated master SaaS console settings")
        messages.success(request, "SaaS platform settings updated.")
        return redirect("/settings")

    db_config = django_settings.DATABASES["default"]
    diagnostics = {
        "portal_host": request.get_host(),
        "database_engine": db_config.get("ENGINE", "").rsplit(".", 1)[-1],
        "database_name": Path(str(db_config.get("NAME", ""))).name,
        "debug_mode": django_settings.DEBUG,
        "allowed_hosts": ", ".join(getattr(django_settings, "ALLOWED_HOSTS", [])) or "-",
    }
    return render(
        request,
        "settings_app/saas_settings.html",
        {
            "title": "SaaS Platform Settings",
            "subtitle": "Master portal identity, tenant defaults, safety switches, and routing diagnostics.",
            "platform_settings": platform_settings,
            "saas_stats": saas_platform_stats(),
            "diagnostics": diagnostics,
            "recent_audit": dict_rows("SELECT username, action, details, created_at FROM audit_log ORDER BY audit_id DESC LIMIT 5"),
        },
    )


@permission_required("settings.manage")
def settings(request):
    if is_saas_portal_request(request):
        return saas_settings(request)

    fields = [
        "school_name",
        "school_address",
        "school_phone",
        "school_email",
        "school_logo",
        "school_motto",
        "school_website",
        "headmaster_name",
        "school_stamp",
        "current_term",
        "current_year",
        "receipt_prefix",
        "whatsapp_sender_number",
        "whatsapp_phone_number_id",
        "whatsapp_access_token",
        "whatsapp_api_version",
        "last_promotion_year",
        "cashbook_opening_balance",
    ]
    row = one_row("SELECT setting_id FROM school_settings WHERE setting_id = 1")
    response = render_record_form_page(
        request,
        "School Settings",
        "school_settings",
        fields,
        pk_column="setting_id",
        pk_value=1 if row else None,
        subtitle="School profile, term, year, receipt prefix, and integration settings.",
        redirect_to="/settings",
        extra_defaults={"setting_id": 1} if not row else None,
    )
    if request.method == "POST" and 300 <= getattr(response, "status_code", 200) < 400:
        try:
            from students.services import run_yearly_student_progression

            progression = run_yearly_student_progression()
            if progression.get("promoted") or progression.get("completed"):
                messages.success(request, f"Yearly progression completed: {progression['promoted']} promoted, {progression['completed']} archived as completed.")
        except Exception as exc:
            messages.warning(request, f"Yearly student progression could not run: {exc}")
        try:
            from fees.services import ensure_current_term_bills_for_active_students

            stats = ensure_current_term_bills_for_active_students()
            if stats.get("created"):
                messages.success(request, f"Auto term billing created {stats['created']} bill(s) for {stats['term']} {stats['year']}.")
            if stats.get("missing_fee_structure"):
                messages.info(request, f"{stats['missing_fee_structure']} active student(s) have no matching fee structure for {stats['term']} {stats['year']}.")
        except Exception as exc:
            messages.warning(request, f"Auto term billing could not run: {exc}")
    return response


@permission_required("audit.view")
def audit(request):
    return render_table_page(
        request,
        "Audit Trail",
        "audit_log",
        ["audit_id", "username", "user_role", "action", "details", "created_at"],
        "Security and activity log.",
        order_by="audit_id DESC",
        search_columns=["username", "action", "details"],
        pk_column="audit_id",
        row_actions=[],
    )


@permission_required("backups.manage")
def backups(request):
    if request.path.endswith("/create"):
        return create_backup(request)
    return render_table_page(
        request,
        "Database Backups",
        "database_backups_log",
        ["backup_id", "backup_name", "backup_path", "file_size", "created_at"],
        "Database backup history.",
        order_by="created_at DESC",
        search_columns=["backup_name", "backup_path"],
        pk_column="backup_id",
        actions=[{"label": "Create Backup", "href": "/backups/create", "icon": "bi-database-add"}],
        row_actions=[
            {"label": "Download", "href": "/backups/{backup_id}/download", "icon": "bi-download", "class": "btn-outline-primary"},
        ],
    )


@permission_required("settings.manage")
def offline_sync(request):
    return render_table_page(
        request,
        "Offline Sync",
        "offline_sync_events",
        ["event_id", "event_type", "entity_table", "entity_id", "status", "attempts", "queued_at"],
        "Offline queue and sync events.",
        order_by="queued_at DESC",
        search_columns=["event_type", "entity_table", "status"],
        pk_column="event_id",
        row_actions=[
            {"label": "Retry", "href": "/offline-sync/{event_id}/retry", "icon": "bi-arrow-clockwise", "class": "btn-outline-success", "method": "post", "confirm": "Queue this sync event again?"},
        ],
    )


@permission_required("backups.manage")
def create_backup(request):
    import os
    import subprocess
    db_config = django_settings.DATABASES["default"]
    engine = db_config.get("ENGINE", "")
    
    backup_dir = django_settings.BASE_DIR / "database_backups"
    backup_dir.mkdir(exist_ok=True)
    
    if "postgresql" in engine:
        backup_name = f"school-system-backup-{now_text().replace(':', '').replace(' ', '-')}.sql"
        target = backup_dir / backup_name
        
        db_name = db_config["NAME"]
        db_user = db_config["USER"]
        db_password = db_config["PASSWORD"]
        db_host = db_config["HOST"]
        db_port = db_config["PORT"]
        
        pg_dump_path = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
        if not Path(pg_dump_path).exists():
            pg_dump_path = "pg_dump"
            
        env = os.environ.copy()
        if db_password:
            env["PGPASSWORD"] = db_password
            
        cmd = [
            pg_dump_path,
            "-h", db_host or "localhost",
            "-p", db_port or "5432",
            "-U", db_user or "postgres",
            "-F", "c",
            "-b",
            "-v",
            "-f", str(target),
            db_name
        ]
        try:
            subprocess.run(cmd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as exc:
            messages.error(request, f"Could not create PostgreSQL backup: {exc}")
            return redirect("/backups")
    else:
        backup_name = f"school-system-backup-{now_text().replace(':', '').replace(' ', '-')}.db"
        target = backup_dir / backup_name
        db_name = db_config["NAME"]
        source = Path(db_name)
        if not source.exists():
            messages.error(request, "Database file could not be found for backup.")
            return redirect("/backups")
        shutil.copy2(source, target)
        
    insert_record(
        request,
        "database_backups_log",
        {
            "backup_name": backup_name,
            "backup_path": str(target),
            "file_size": target.stat().st_size if target.exists() else 0,
            "created_by": legacy_user_id(request),
            "created_at": now_text(),
        },
    )
    messages.success(request, "Database backup created.")
    return redirect("/backups")


@permission_required("backups.manage")
def download_backup(request, backup_id):
    row = one_row("SELECT * FROM database_backups_log WHERE backup_id = %s", [backup_id])
    path = Path(row["backup_path"]) if row else None
    if not path or not path.exists():
        messages.error(request, "Backup file could not be found.")
        return redirect("/backups")
    return FileResponse(open(path, "rb"), as_attachment=True, filename=row["backup_name"])


@permission_required("settings.manage")
def retry_sync(request, event_id):
    from school_system_django.native import update_record_fields

    return update_record_fields(request, "offline_sync_events", "event_id", event_id, {"status": "Queued", "attempts": 0}, "Sync event queued again.", "/offline-sync")

# Create your views here.
