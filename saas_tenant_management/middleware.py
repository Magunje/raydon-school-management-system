import os
import shutil
import sqlite3
import sys
from django.conf import settings
from django.db import connections
from django.http import HttpResponse, HttpResponseNotFound
from saas_tenant_management.models import SchoolTenant, set_current_tenant, clear_current_tenant
from saas_tenant_management.schema import ensure_sqlite_tenant_schema

MASTER_DB_PATH = None
IS_TESTING = 'test' in sys.argv or 'test_coverage' in sys.argv
_SCHEMA_CHECKED_PATHS = set()


def reset_master_connection():
    if IS_TESTING or MASTER_DB_PATH is None:
        return
    connections['default'].close()
    connections['default'].settings_dict['NAME'] = MASTER_DB_PATH


def ensure_runtime_schema(db_path):
    if IS_TESTING or not db_path or db_path in _SCHEMA_CHECKED_PATHS:
        return
    ensure_sqlite_tenant_schema(db_path)
    _SCHEMA_CHECKED_PATHS.add(db_path)


def ensure_tenant_db(tenant, db_path):
    if os.path.exists(db_path):
        ensure_runtime_schema(db_path)
        return

    # Create the parent directory if needed
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Copy the master database file as the base structure
    shutil.copy2(MASTER_DB_PATH, db_path)

    # Clean application data from the newly copied tenant database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    tables_to_clear = [
        "pupils", "guardians", "teacher_profiles", 
        "teacher_attendance_records", "attendance_records",
        "fees_structure", "payments", "payment_allocations",
        "receipts", "master_receipts", "expenses",
        "online_payment_requests", "term_bills",
        "balance_adjustments", "result_sheets", "result_entries",
        "class_timetable_entries", "e_learning_notes",
        "e_learning_assignments", "e_learning_submissions",
        "audit_log", "database_backups_log", "academic_year"
    ]
    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except Exception:
            pass

    # Clear non-admin users so the database is blank, but preserve default admin
    try:
        cursor.execute("DELETE FROM users WHERE username != 'admin'")
    except Exception:
        pass

    # Update school name and contact info inside the tenant database settings
    try:
        cursor.execute("UPDATE school_settings SET school_name = ? WHERE setting_id = 1", (tenant.name,))
    except Exception:
        pass

    conn.commit()
    conn.close()
    ensure_runtime_schema(db_path)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        global MASTER_DB_PATH
        if MASTER_DB_PATH is None:
            MASTER_DB_PATH = settings.DATABASES['default']['NAME']

    def __call__(self, request):
        reset_master_connection()
        # Extract host header and split into domain and port
        host_header = request.get_host()
        parts = host_header.split(":")
        host_domain = parts[0].lower()
        host_port = int(parts[1]) if len(parts) > 1 else None

        # Check if this is the master SaaS administration portal domain
        if host_domain in ["saas.localhost", "saas.raydonsystem.com", "admin.localhost"]:
            set_current_tenant(None)
            request.tenant = None
            # Switch back to Master database if we are running in file mode
            reset_master_connection()
            return self.get_response(request)

        try:
            matched_tenant = None

            # 1. Local development subdomain mode: if visiting subdomain.localhost (e.g. raydonhigh.localhost:8006)
            if host_domain.endswith(".localhost"):
                subdomain = host_domain[:-10]  # Strip ".localhost"
                from django.db.models import Q
                matched_tenant = SchoolTenant.objects.filter(
                    Q(production_domain__startswith=subdomain + ".") |
                    Q(production_domain=host_domain)
                ).first()

            # 2. Local development port mode fallback: if accessing localhost:8007
            if not matched_tenant and host_domain in ["localhost", "127.0.0.1", "testserver"]:
                if host_port:
                    matched_tenant = SchoolTenant.objects.filter(local_testing_port=host_port).first()
                else:
                    matched_tenant = SchoolTenant.objects.filter(active=True).first()

            # 3. Production mode matching: match production_domain
            if not matched_tenant:
                matched_tenant = SchoolTenant.objects.filter(production_domain=host_domain).first()

            if not matched_tenant:
                if IS_TESTING and SchoolTenant.objects.count() == 0:
                    set_current_tenant(None)
                    request.tenant = None
                    reset_master_connection()
                    return self.get_response(request)
                return HttpResponseNotFound(
                    "<h3>404 Tenant Not Found</h3><p>The requested school tenant domain/port is not registered on this system.</p>"
                )

            if not matched_tenant.active:
                return HttpResponse(
                    "<h3>Tenant Inactive</h3><p>This school tenant subscription has been suspended or deactivated.</p>",
                    status=403
                )

            # Bind tenant to request and thread context
            request.tenant = matched_tenant
            set_current_tenant(matched_tenant)

            # Switch connection to tenant-specific database file if we are not running unit tests in memory
            if not IS_TESTING:
                # Clean name for safe filename
                safe_name = "".join(c for c in matched_tenant.name if c.isalnum() or c in ("_", "-")).strip().replace(" ", "_").lower()
                db_filename = f"tenant_{safe_name}_{matched_tenant.tenant_id.hex[:8]}.db"
                
                # Determine tenant db path inside scratch directory relative to BASE_DIR or workspace
                scratch_dir = os.path.join(settings.BASE_DIR, "scratch")
                db_path = os.path.join(scratch_dir, db_filename)
                
                # Ensure the isolated database file is copied and seeded
                ensure_tenant_db(matched_tenant, db_path)
                
                # Close the master database connection and switch to the tenant database
                connections['default'].close()
                connections['default'].settings_dict['NAME'] = db_path

        except Exception as e:
            clear_current_tenant()
            reset_master_connection()
            raise e

        try:
            return self.get_response(request)
        finally:
            clear_current_tenant()
            reset_master_connection()
