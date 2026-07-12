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


def create_tenant_record(data, logo=None, user=None, provision=True):
    school_code = (data.get("school_code") or "").upper().strip()
    subdomain = (data.get("subdomain") or school_code.lower()).strip().lower()
    plan_type = data.get("plan_type") or "STANDARD"
    subscription_start = data.get("subscription_start") or timezone.localdate()
    subscription_end = data.get("subscription_end")
    trial_end = data.get("trial_end")
    trial_days = int(data.get("trial_period") or 14)
    if not trial_end and trial_days:
        trial_end = subscription_start + datetime.timedelta(days=trial_days)
    if not subscription_end:
        subscription_end = subscription_start + datetime.timedelta(days=365)

    database_name = data.get("database_name") or safe_identifier(school_code or subdomain, "school")
    database_user = data.get("database_user") or safe_identifier(school_code or subdomain, "usr")
    database_password = data.get("database_password") or generate_temporary_password(20)

    with transaction.atomic():
        tenant = SchoolTenant(
            name=data.get("school_name") or data.get("name"),
            school_code=school_code,
            email_address=data.get("school_email") or data.get("email"),
            telephone=data.get("school_phone") or data.get("phone") or "",
            address=data.get("school_address") or data.get("address") or "",
            logo=logo,
            subdomain=subdomain,
            custom_domain=(data.get("custom_domain") or "").strip().lower() or None,
            local_testing_port=data.get("testing_port") or None,
            production_domain=data.get("production_domain") or None,
            database_name=database_name,
            database_user=database_user,
            plan_type=plan_type,
            max_students=data.get("max_students") or 500,
            max_users=data.get("max_users") or 25,
            subscription_start=subscription_start,
            subscription_end=subscription_end,
            trial_end=trial_end,
            is_trial=bool(data.get("is_trial", True)),
            is_active=True,
            is_suspended=False,
        )
        tenant.set_database_password(database_password)
        tenant.full_clean()
        tenant.save()

        seed_default_modules()
        module_names = data.get("modules") or [code for code, _label in DEFAULT_TENANT_MODULES]
        for module_name in module_names:
            TenantModule.objects.update_or_create(
                tenant=tenant,
                module_name=module_name,
                defaults={"enabled": True},
            )
        plan = ensure_subscription_plan(plan_type)
        subscription = TenantSubscription.objects.create(
            subscription_number=next_saas_number("SUB", TenantSubscription),
            tenant=tenant,
            plan=plan,
            start_date=subscription_start,
            expiry_date=subscription_end,
            status="TRIAL" if tenant.is_trial else "ACTIVE",
            amount=Decimal(str(data.get("amount") or "0")),
            currency=data.get("currency") or "USD",
            payment_status="TRIAL" if tenant.is_trial else "PENDING",
            next_billing_date=subscription_end,
        )
        SchoolBrandingProfile.objects.get_or_create(tenant=tenant)

    create_tenant_media_folder(tenant)
    provision_result = {"created": False, "reason": "Provisioning skipped."}
    admin_credentials = None
    if provision:
        provision_result = provision_postgresql_database(tenant, database_password)
        database_alias = run_tenant_migrations(tenant)
        seed_tenant_school_settings(tenant, database_alias)
        admin_credentials = create_tenant_super_admin(tenant, database_alias)

    log_saas_action(
        "Tenant creation",
        tenant=tenant,
        user=user,
        new_value={
            "school_code": tenant.school_code,
            "database_name": tenant.database_name,
            "modules": module_names,
            "provisioning": provision_result,
        },
    )
    return {"tenant": tenant, "subscription": subscription, "admin": admin_credentials, "provisioning": provision_result}


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
