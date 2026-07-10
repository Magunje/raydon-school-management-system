from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

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
    TenantModuleActivation,
    TenantSubscription,
    TenantUsageSnapshot,
    subscription_allows_module,
)


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
        tenant.save(update_fields=["subscription_plan"])
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
