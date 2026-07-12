from decimal import Decimal
import datetime
import os
import re
import secrets
import string
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, connections, transaction
from django.utils import timezone
import psycopg

from academic_structure.models import AcademicTerm, AcademicYear
from saas_tenant_management.models import (
    COMPULSORY_MODULES,
    MODULE_DEPENDENCIES,
    ModuleDefinition,
    SaaSAuditLog,
    SchoolBrandingProfile,
    SchoolTenant,
    SubscriptionInvoice,
    SubscriptionPayment,
    SubscriptionPlan,
    TenantModule,
    TenantModuleActivation,
    TenantSubscription,
    TenantUsageSnapshot,
    subscription_allows_module,
)
from saas_tenant_management.domains import build_full_hostname, normalize_custom_domain, normalize_subdomain_label


DEFAULT_TENANT_MODULES = [
    ("student_registration", "Student Registration"),
    ("fees_management", "Fees Management"),
    ("results_center", "Results Center"),
    ("timetable", "Timetable"),
    ("attendance", "Attendance"),
    ("library", "Library"),
    ("hostel", "Hostel"),
    ("payroll", "Payroll"),
    ("human_resources", "HR"),
    ("inventory_management", "Inventory"),
    ("transport", "Transport"),
    ("reports", "Reports"),
]

CORE_MODULE_CODES = {"student_registration", "fees_management", "reports"}


def parse_bool(value, default=False):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def next_saas_number(prefix, model):
    return f"{prefix}-{model.objects.count() + 1:05d}"


def log_saas_action(action, tenant=None, reference_number=None, user=None, previous_value=None, new_value=None, reason=None):
    return SaaSAuditLog.objects.create(
        action=action,
        tenant=tenant,
        reference_number=reference_number,
        user=user,
        previous_value=previous_value,
        new_value=new_value,
        reason=reason,
    )


def seed_default_modules():
    definitions = {
        "student_registration": ("Student Registration", True, False),
        "student_records": ("Student Records", True, False),
        "fees_management": ("Fees Management", True, False),
        "payment_reconciliation": ("Payment and Reconciliation", True, False),
        "reports_analytics": ("Reports and Analytics", True, False),
        "attendance": ("Attendance Management", False, False),
        "timetable": ("Timetable Management", False, False),
        "examinations": ("Examination Management", False, False),
        "parent_portal": ("Parent Portal", False, False),
        "student_portal": ("Student Portal", False, False),
        "library": ("Library Management", False, False),
        "hostel": ("Hostel Management", False, False),
        "transport": ("Transport Management", False, False),
        "medical": ("Medical Management", False, False),
        "discipline": ("Discipline Management", False, False),
        "counselling": ("Guidance and Counselling", False, False),
        "inventory_management": ("Inventory Management", False, False),
        "assets": ("Asset Management", False, False),
        "procurement": ("Procurement Management", False, False),
        "accounting": ("Accounting", False, False),
        "human_resources": ("Human Resources Management", False, True),
        "payroll": ("Payroll Management", False, True),
        "advanced_business_intelligence": ("Advanced Business Intelligence", False, True),
        "api_integrations": ("API Integrations", False, True),
        "custom_branding": ("Custom Branding Features", False, True),
    }
    modules = {}
    for code, (name, compulsory, premium) in definitions.items():
        module, _ = ModuleDefinition.objects.get_or_create(
            code=code,
            defaults={"name": name, "compulsory": compulsory, "premium": premium},
        )
        modules[code] = module

    for module_code, dependency_codes in MODULE_DEPENDENCIES.items():
        module = modules.get(module_code)
        if module:
            module.dependencies.set([modules[code] for code in dependency_codes if code in modules])
    return modules


def safe_identifier(value, prefix="tenant"):
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", value or "").strip("_").lower()
    value = re.sub(r"_+", "_", value)
    if not value:
        value = secrets.token_hex(4)
    if value[0].isdigit():
        value = f"{prefix}_{value}"
    return f"{prefix}_{value}"[:55]


def generate_temporary_password(length=14):
    alphabet = string.ascii_letters + string.digits + "!@#$%?"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
        ):
            return password


def default_database_settings():
    return settings.DATABASES["default"].copy()


def tenant_database_settings(tenant):
    config = default_database_settings()
    config.update(
        {
            "NAME": tenant.database_name,
            "USER": tenant.database_user or config.get("USER", ""),
            "PASSWORD": tenant.get_database_password() or config.get("PASSWORD", ""),
            "HOST": config.get("HOST", ""),
            "PORT": config.get("PORT", ""),
        }
    )
    return config


def normalize_school_code(value):
    return str(value or "").strip().upper()


def normalize_tenant_payload(data):
    school_code = normalize_school_code(data.get("school_code"))
    raw_subdomain = data.get("subdomain") or school_code.lower()
    subdomain = normalize_subdomain_label(raw_subdomain) or school_code.lower()
    custom_domain = normalize_custom_domain(data.get("custom_domain"))
    production_domain = build_full_hostname(subdomain)
    modules = data.get("modules") or []
    if isinstance(modules, str):
        modules = [modules]
    modules = sorted({str(module).strip() for module in modules if str(module).strip()} | CORE_MODULE_CODES)
    return {
        "school_name": (data.get("school_name") or data.get("name") or "").strip(),
        "school_code": school_code,
        "school_email": (data.get("school_email") or data.get("email") or "").strip(),
        "school_phone": (data.get("school_phone") or data.get("phone") or "").strip(),
        "school_address": (data.get("school_address") or data.get("address") or "").strip(),
        "subdomain": subdomain,
        "custom_domain": custom_domain,
        "production_domain": production_domain,
        "testing_port": data.get("testing_port") or None,
        "plan_type": (data.get("plan_type") or "STANDARD").strip().upper(),
        "modules": modules,
        "subscription_start": data.get("subscription_start") or timezone.localdate(),
        "subscription_end": data.get("subscription_end"),
        "trial_end": data.get("trial_end"),
        "trial_period": int(data.get("trial_period") or 14),
        "is_trial": parse_bool(data.get("is_trial"), True),
        "max_students": int(data.get("max_students") or 500),
        "max_users": int(data.get("max_users") or 25),
        "amount": Decimal(str(data.get("amount") or "0")),
        "currency": (data.get("currency") or "USD").strip().upper(),
        "billing_cycle": (data.get("billing_cycle") or "MONTHLY").strip().upper(),
        "database_name": data.get("database_name"),
        "database_user": data.get("database_user"),
        "database_password": data.get("database_password"),
    }


def tenant_conflicts(*, school_code, subdomain, custom_domain=None, exclude_tenant_id=None):
    queryset = SchoolTenant.objects.all()
    if exclude_tenant_id:
        queryset = queryset.exclude(tenant_id=exclude_tenant_id)
    conflicts = []
    if school_code and queryset.filter(school_code__iexact=school_code).exists():
        conflicts.append(f"School code {school_code} is already in use.")
    if subdomain and queryset.filter(subdomain__iexact=subdomain).exists():
        conflicts.append(f"Subdomain {subdomain} is already assigned.")
    if custom_domain and queryset.filter(custom_domain__iexact=custom_domain).exists():
        conflicts.append(f"Custom domain {custom_domain} is already assigned.")
    return conflicts


def check_tenant_availability(*, school_code, subdomain, custom_domain=None, exclude_tenant_id=None):
    normalized_subdomain = normalize_subdomain_label(subdomain)
    normalized_custom_domain = normalize_custom_domain(custom_domain)
    conflicts = tenant_conflicts(
        school_code=normalize_school_code(school_code),
        subdomain=normalized_subdomain,
        custom_domain=normalized_custom_domain,
        exclude_tenant_id=exclude_tenant_id,
    )
    conflict_text = " ".join(conflicts)
    return {
        "school_code_available": f"School code {normalize_school_code(school_code)} is already in use." not in conflict_text,
        "subdomain_available": f"Subdomain {normalized_subdomain} is already assigned." not in conflict_text,
        "custom_domain_available": (not normalized_custom_domain) or (f"Custom domain {normalized_custom_domain} is already assigned." not in conflict_text),
        "normalized_subdomain": normalized_subdomain,
        "normalized_custom_domain": normalized_custom_domain,
        "full_hostname": build_full_hostname(normalized_subdomain),
        "conflicts": conflicts,
    }


def install_tenant_connection(tenant):
    alias = f"tenant_{tenant.tenant_id.hex}"
    connections.databases[alias] = tenant_database_settings(tenant)
    return alias


def provision_postgresql_database(tenant, database_password):
    default = default_database_settings()
    if not default.get("ENGINE", "").endswith("postgresql"):
        return {"created": False, "reason": "The current environment is not using PostgreSQL."}

    admin_user = default.get("USER")
    admin_password = default.get("PASSWORD")
    host = default.get("HOST") or "localhost"
    port = default.get("PORT") or 5432
    maintenance_db = os.environ.get("POSTGRES_MAINTENANCE_DB", "postgres")
    admin_conninfo = {
        "dbname": maintenance_db,
        "user": admin_user,
        "password": admin_password,
        "host": host,
        "port": port,
        "autocommit": True,
    }

    with psycopg.connect(**admin_conninfo) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [tenant.database_user])
            if cursor.fetchone() is None:
                cursor.execute(
                    "SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', %s, %s)",
                    [tenant.database_user, database_password],
                )
                cursor.execute(cursor.fetchone()[0])
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", [tenant.database_name])
            if cursor.fetchone() is None:
                cursor.execute(
                    "SELECT format('CREATE DATABASE %I OWNER %I ENCODING ''UTF8''', %s, %s)",
                    [tenant.database_name, tenant.database_user],
                )
                cursor.execute(cursor.fetchone()[0])
    return {"created": True}


def create_tenant_media_folder(tenant):
    folder = settings.MEDIA_ROOT / "tenants" / str(tenant.tenant_id)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def seed_tenant_school_settings(tenant, database_alias):
    with connections[database_alias].cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS school_settings (
                setting_id integer PRIMARY KEY,
                school_name varchar(180) NOT NULL,
                school_address text,
                school_phone varchar(80),
                school_logo varchar(255),
                current_term varchar(40) NOT NULL,
                current_year integer NOT NULL,
                receipt_prefix varchar(20) DEFAULT 'RCP',
                school_email varchar(255),
                school_motto text,
                school_website varchar(255),
                headmaster_name varchar(180),
                school_stamp varchar(255)
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO school_settings (
                setting_id, school_name, school_address, school_phone, school_logo,
                current_term, current_year, receipt_prefix, school_email
            )
            VALUES (1, %s, %s, %s, %s, 'Term 1', %s, 'RCP', %s)
            ON CONFLICT (setting_id) DO UPDATE SET
                school_name = EXCLUDED.school_name,
                school_address = EXCLUDED.school_address,
                school_phone = EXCLUDED.school_phone,
                school_logo = EXCLUDED.school_logo,
                school_email = EXCLUDED.school_email
            """,
            [
                tenant.name,
                tenant.address,
                tenant.telephone,
                tenant.logo.name if tenant.logo else None,
                timezone.localdate().year,
                tenant.email_address,
            ],
        )

def seed_tenant_academic_calendar(database_alias, year=None):
    year = int(year or timezone.localdate().year)
    defaults = {
        2026: [
            (1, "Term 1", datetime.date(2026, 1, 13), datetime.date(2026, 4, 1)),
            (2, "Term 2", datetime.date(2026, 5, 12), datetime.date(2026, 8, 6)),
            (3, "Term 3", datetime.date(2026, 9, 8), datetime.date(2026, 12, 8)),
        ]
    }
    terms = defaults.get(year)
    if not terms:
        return
    academic_year, _ = AcademicYear.objects.using(database_alias).get_or_create(
        year=year,
        defaults={
            "name": str(year),
            "start_date": terms[0][2],
            "end_date": terms[-1][3],
            "is_active": False,
            "is_current": False,
            "status": "upcoming",
        },
    )
    for number, name, start_date, end_date in terms:
        AcademicTerm.objects.using(database_alias).get_or_create(
            academic_year=academic_year,
            term_number=number,
            defaults={
                "name": name,
                "start_date": start_date,
                "end_date": end_date,
                "is_active": False,
                "is_current": False,
                "status": "upcoming",
            },
        )


def run_tenant_migrations(tenant):
    alias = install_tenant_connection(tenant)
    call_command("migrate", database=alias, interactive=False, verbosity=0)
    return alias


def ensure_subscription_plan(plan_code):
    plan_name = dict(SchoolTenant.PLAN_TYPES).get(plan_code, "Standard")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code=plan_code,
        defaults={"name": f"{plan_name} Plan", "trial_days": 14},
    )
    return plan


def _validated_schedule(normalized):
    subscription_start = normalized["subscription_start"]
    subscription_end = normalized["subscription_end"] or (subscription_start + datetime.timedelta(days=365))
    trial_end = normalized["trial_end"]
    if not trial_end and normalized["trial_period"]:
        trial_end = subscription_start + datetime.timedelta(days=normalized["trial_period"])
    if subscription_end <= subscription_start:
        raise ValidationError({"subscription_end": "Subscription end date must be after the start date."})
    if trial_end and trial_end < subscription_start:
        raise ValidationError({"trial_end": "Trial end date cannot be before the subscription start date."})
    normalized["subscription_end"] = subscription_end
    normalized["trial_end"] = trial_end
    return normalized


def _validate_tenant_creation_payload(normalized):
    errors = {}
    if not normalized["school_name"]:
        errors["school_name"] = "School name is required."
    if not normalized["school_code"]:
        errors["school_code"] = "School code is required."
    if not normalized["subdomain"]:
        errors["subdomain"] = "Subdomain is required."
    if errors:
        raise ValidationError(errors)
    conflicts = tenant_conflicts(
        school_code=normalized["school_code"],
        subdomain=normalized["subdomain"],
        custom_domain=normalized["custom_domain"],
    )
    if conflicts:
        raise ValidationError({"availability": conflicts})


def sync_tenant_modules(tenant, module_names, *, subscription=None, user=None):
    seed_default_modules()
    requested = sorted(set(module_names or []) | CORE_MODULE_CODES)
    TenantModule.objects.filter(tenant=tenant).exclude(module_name__in=requested).update(enabled=False)
    for module_name in requested:
        TenantModule.objects.update_or_create(
            tenant=tenant,
            module_name=module_name,
            defaults={"enabled": True},
        )
        try:
            activate_module(tenant, module_name, subscription=subscription, user=user)
        except ModuleDefinition.DoesNotExist:
            continue
    for disabled in TenantModule.objects.filter(tenant=tenant, enabled=False):
        try:
            deactivate_module(tenant, disabled.module_name, user=user, reason="Module disabled in tenant sync")
        except Exception:
            continue


def mark_tenant_provisioning(tenant, status, *, error=None):
    tenant.provisioning_status = status
    tenant.provisioning_error = error
    if status == "PROVISIONING":
        tenant.provisioning_started_at = timezone.now()
    if status == "ACTIVE":
        tenant.provisioning_completed_at = timezone.now()
        tenant.is_active = True
        tenant.is_suspended = False
    if status == "FAILED":
        tenant.is_active = False
    tenant.save(update_fields=[
        "provisioning_status",
        "provisioning_error",
        "provisioning_started_at",
        "provisioning_completed_at",
        "is_active",
        "is_suspended",
        "active",
        "updated_at",
    ])


def perform_tenant_provisioning(tenant, *, database_password=None, user=None):
    database_password = database_password or tenant.get_database_password() or generate_temporary_password(20)
    provision_result = provision_postgresql_database(tenant, database_password)
    database_alias = run_tenant_migrations(tenant)
    seed_tenant_school_settings(tenant, database_alias)
    seed_tenant_academic_calendar(database_alias, timezone.localdate().year)
    admin_credentials = create_tenant_super_admin(tenant, database_alias)
    return {
        "created": True,
        "database_alias": database_alias,
        "database_name": tenant.database_name,
        "database_user": tenant.database_user,
        "postgres": provision_result,
        "admin": admin_credentials,
    }


def create_tenant_record(data, logo=None, user=None, provision=True):
    normalized = _validated_schedule(normalize_tenant_payload(data))
    _validate_tenant_creation_payload(normalized)

    database_name = normalized.get("database_name") or safe_identifier(normalized["school_code"] or normalized["subdomain"], "school")
    database_user = normalized.get("database_user") or safe_identifier(normalized["school_code"] or normalized["subdomain"], "usr")
    database_password = normalized.get("database_password") or generate_temporary_password(20)

    with transaction.atomic():
        tenant = SchoolTenant(
            name=normalized["school_name"],
            school_code=normalized["school_code"],
            email_address=normalized["school_email"] or None,
            telephone=normalized["school_phone"] or "+263000000000",
            address=normalized["school_address"] or "Zimbabwe",
            logo=logo,
            subdomain=normalized["subdomain"],
            custom_domain=normalized["custom_domain"],
            local_testing_port=normalized["testing_port"],
            production_domain=normalized["production_domain"],
            database_name=database_name,
            database_user=database_user,
            plan_type=normalized["plan_type"],
            max_students=normalized["max_students"],
            max_users=normalized["max_users"],
            subscription_start=normalized["subscription_start"],
            subscription_end=normalized["subscription_end"],
            trial_end=normalized["trial_end"],
            is_trial=normalized["is_trial"],
            is_active=False,
            is_suspended=False,
            provisioning_status="PENDING",
        )
        tenant.set_database_password(database_password)
        tenant.full_clean()
        tenant.save()

        plan = ensure_subscription_plan(normalized["plan_type"])
        subscription = TenantSubscription.objects.create(
            subscription_number=next_saas_number("SUB", TenantSubscription),
            tenant=tenant,
            plan=plan,
            start_date=normalized["subscription_start"],
            expiry_date=normalized["subscription_end"],
            billing_cycle=normalized["billing_cycle"],
            status="TRIAL" if tenant.is_trial else "ACTIVE",
            amount=normalized["amount"],
            currency=normalized["currency"],
            payment_status="TRIAL" if tenant.is_trial else "PENDING",
            next_billing_date=normalized["subscription_end"],
        )
        SchoolBrandingProfile.objects.get_or_create(tenant=tenant)
        sync_tenant_modules(tenant, normalized["modules"], subscription=subscription, user=user)

    admin_credentials = None
    provision_result = {"created": False, "reason": "Provisioning skipped."}
    if provision:
        try:
            mark_tenant_provisioning(tenant, "PROVISIONING")
            create_tenant_media_folder(tenant)
            provision_result = perform_tenant_provisioning(tenant, database_password=database_password, user=user)
            admin_credentials = provision_result["admin"]
            mark_tenant_provisioning(tenant, "ACTIVE", error=None)
            log_saas_action("Tenant provisioning completed", tenant=tenant, user=user, new_value={"status": tenant.provisioning_status})
        except Exception as exc:
            mark_tenant_provisioning(tenant, "FAILED", error=str(exc))
            log_saas_action("Tenant provisioning failed", tenant=tenant, user=user, new_value={"error": str(exc)})
            provision_result = {"created": False, "error": str(exc)}
    else:
        log_saas_action("Tenant provisioning skipped", tenant=tenant, user=user, new_value={"status": tenant.provisioning_status})

    log_saas_action(
        "Tenant creation",
        tenant=tenant,
        user=user,
        new_value={
            "school_code": tenant.school_code,
            "database_name": tenant.database_name,
            "modules": normalized["modules"],
            "provisioning": provision_result,
        },
    )
    return {"tenant": tenant, "subscription": subscription, "admin": admin_credentials, "provisioning": provision_result}


def retry_tenant_provisioning(tenant, *, user=None):
    if tenant.provisioning_status == "ACTIVE":
        raise ValidationError("Tenant is already active.")
    try:
        mark_tenant_provisioning(tenant, "PROVISIONING", error=None)
        create_tenant_media_folder(tenant)
        result = perform_tenant_provisioning(tenant, user=user)
        mark_tenant_provisioning(tenant, "ACTIVE", error=None)
        log_saas_action("Tenant provisioning completed", tenant=tenant, user=user, new_value={"status": tenant.provisioning_status})
        return result
    except Exception as exc:
        mark_tenant_provisioning(tenant, "FAILED", error=str(exc))
        log_saas_action("Tenant provisioning failed", tenant=tenant, user=user, new_value={"error": str(exc)})
        raise


def create_school_subscription(tenant, plan, start_date, expiry_date, modules=None, billing_cycle="MONTHLY", status="TRIAL", user=None):
    modules = set(modules or [])
    modules.update(COMPULSORY_MODULES)
    with transaction.atomic():
        subscription = TenantSubscription.objects.create(
            subscription_number=next_saas_number("SUB", TenantSubscription),
            tenant=tenant,
            plan=plan,
            start_date=start_date,
            expiry_date=expiry_date,
            billing_cycle=billing_cycle,
            status=status,
        )
        tenant.subscription_plan = plan.code
        tenant.plan_type = plan.code if plan.code in dict(SchoolTenant.PLAN_TYPES) else tenant.plan_type
        tenant.save(update_fields=["subscription_plan", "plan_type"])
        seed_default_modules()
        for module_code in modules:
            activate_module(tenant, module_code, subscription=subscription, user=user)
        SchoolBrandingProfile.objects.get_or_create(tenant=tenant)
        log_saas_action(
            "Subscription creation",
            tenant=tenant,
            reference_number=subscription.subscription_number,
            user=user,
            new_value={"plan": plan.code, "status": status, "modules": sorted(modules)},
        )
        return subscription


def activate_module(tenant, module_code, subscription=None, status="ACTIVE", user=None):
    module = ModuleDefinition.objects.get(code=module_code)
    if module.premium and not subscription_allows_module(tenant.subscription_plan, module_code):
        raise ValidationError("Premium modules require additional licensing.")
    dependencies = set(module.dependencies.values_list("code", flat=True)) | MODULE_DEPENDENCIES.get(module_code, set())
    for dependency_code in dependencies:
        activate_module(tenant, dependency_code, subscription=subscription, status=status, user=user)
    activation, _ = TenantModuleActivation.objects.update_or_create(
        tenant=tenant,
        module=module,
        defaults={"subscription": subscription, "status": status},
    )
    log_saas_action(
        "Module activation",
        tenant=tenant,
        reference_number=module_code,
        user=user,
        new_value={"status": status},
    )
    return activation


def deactivate_module(tenant, module_code, user=None, reason=None):
    if module_code in COMPULSORY_MODULES:
        raise ValidationError("Compulsory modules cannot be disabled.")
    module = ModuleDefinition.objects.get(code=module_code)
    activation, _ = TenantModuleActivation.objects.get_or_create(
        tenant=tenant,
        module=module,
        defaults={"status": "DISABLED"},
    )
    previous = {"status": activation.status}
    activation.status = "DISABLED"
    activation.save(update_fields=["status"])
    log_saas_action(
        "Module deactivation",
        tenant=tenant,
        reference_number=module_code,
        user=user,
        previous_value=previous,
        new_value={"status": "DISABLED"},
        reason=reason,
    )
    return activation


def renew_subscription(subscription, new_expiry_date, user=None):
    old_status = subscription.status
    subscription.expiry_date = new_expiry_date
    subscription.status = "ACTIVE"
    subscription.save(update_fields=["expiry_date", "status"])
    log_saas_action(
        "Subscription renewal",
        tenant=subscription.tenant,
        reference_number=subscription.subscription_number,
        user=user,
        previous_value={"status": old_status},
        new_value={"status": subscription.status, "expiry_date": str(new_expiry_date)},
    )
    return subscription


def create_subscription_invoice(subscription, invoice_date, due_date, amount):
    invoice = SubscriptionInvoice.objects.create(
        invoice_number=next_saas_number("SINV", SubscriptionInvoice),
        subscription=subscription,
        invoice_date=invoice_date,
        due_date=due_date,
        amount=amount,
    )
    return invoice


def record_subscription_payment(invoice, payment_date, amount, payment_method, reference_number=None):
    payment = SubscriptionPayment.objects.create(
        payment_number=next_saas_number("SPAY", SubscriptionPayment),
        invoice=invoice,
        payment_date=payment_date,
        amount=amount,
        payment_method=payment_method,
        reference_number=reference_number,
    )
    invoice.paid_amount += amount
    invoice.status = "PAID" if invoice.paid_amount >= invoice.amount else "PART_PAID"
    invoice.save(update_fields=["paid_amount", "status"])
    log_saas_action(
        "Subscription payment",
        tenant=invoice.subscription.tenant,
        reference_number=payment.payment_number,
        new_value={"amount": str(amount), "status": invoice.status},
    )
    return payment


def capture_usage_snapshot(tenant, user_count=0, student_count=0, storage_usage_mb=Decimal("0.00"), database_size_mb=Decimal("0.00"), api_usage_count=0, login_activity_count=0, snapshot_date=None):
    snapshot_date = snapshot_date or timezone.localdate()
    active_module_count = tenant.module_activations.filter(status__in=["ACTIVE", "TRIAL"]).count()
    snapshot, _ = TenantUsageSnapshot.objects.update_or_create(
        tenant=tenant,
        snapshot_date=snapshot_date,
        defaults={
            "user_count": user_count,
            "student_count": student_count,
            "storage_usage_mb": storage_usage_mb,
            "database_size_mb": database_size_mb,
            "active_module_count": active_module_count,
            "api_usage_count": api_usage_count,
            "login_activity_count": login_activity_count,
        },
    )
    return snapshot
def create_tenant_super_admin(tenant, database_alias, temporary_password=None):
    User = get_user_model()
    temporary_password = temporary_password or generate_temporary_password()
    domain = tenant.custom_domain or tenant.production_domain or tenant.subdomain_domain or "school.local"
    domain = domain.replace("www.", "")
    email = f"admin@{domain}"
    username = email

    user, created = User.objects.db_manager(database_alias).get_or_create(
        username=username,
        defaults={"email": email, "is_staff": True, "is_superuser": True},
    )
    user.email = email
    user.is_staff = True
    user.is_superuser = True
    user.set_password(temporary_password)
    user.save(using=database_alias)
    return {"username": username, "email": email, "temporary_password": temporary_password, "created": created}
