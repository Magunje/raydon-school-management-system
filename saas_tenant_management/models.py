from django.db import models
import uuid
import os
import contextvars
from django.core.exceptions import ValidationError

# ContextVar for thread/async-safe request tenant tracking
_current_tenant = contextvars.ContextVar("current_tenant", default=None)

def get_current_tenant():
    return _current_tenant.get()

def set_current_tenant(tenant):
    _current_tenant.set(tenant)

def clear_current_tenant():
    _current_tenant.set(None)


def tenant_media_path(instance, filename):
    """
    Dynamically routes uploaded assets into a sub-folder named 
    after the active school's unique ID/Tenant instance.
    """
    if hasattr(instance, 'tenant_id'):
        tenant_folder = str(instance.tenant_id)
    elif hasattr(instance, 'tenant'):
        tenant_folder = str(instance.tenant.tenant_id)
    else:
        tenant_folder = 'global_assets'
        
    return os.path.join('tenants', tenant_folder, filename)


class SchoolTenant(models.Model):
    SUBSCRIPTION_TIERS = [
        ("STARTER", "Starter Package"),
        ("STANDARD", "Standard Package"),
        ("ENTERPRISE", "Enterprise Package"),
        ("CUSTOM", "Custom Package"),
        ("BASIC", "Basic School Plan"),
        ("PREMIUM", "Premium Enterprise Plan"),
        ("ELITE", "Elite Unified Plan"),
    ]

    tenant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, default="RAYDON HIGH SCHOOL")
    school_code = models.CharField(max_length=50, unique=True, null=True, blank=True)
    registration_number = models.CharField(max_length=80, blank=True, null=True)
    ministry_number = models.CharField(max_length=80, blank=True, null=True)
    school_type = models.CharField(max_length=80, blank=True, null=True)
    province = models.CharField(max_length=120, blank=True, null=True)
    district = models.CharField(max_length=120, blank=True, null=True)
    email_address = models.EmailField(blank=True, null=True)
    active = models.BooleanField(default=True)
    
    # Routing fields for your multi-tenant environments
    local_testing_port = models.IntegerField(unique=True, null=True, blank=True)
    production_domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # File handling linking to your dynamic path script
    logo = models.ImageField(upload_to=tenant_media_path, null=True, blank=True)
    address = models.TextField(default="Harare, Zimbabwe")
    telephone = models.CharField(max_length=50, default="+263771000000")
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_TIERS, default="BASIC")
    tenant_database_identifier = models.CharField(max_length=120, blank=True, null=True)
    report_header = models.CharField(max_length=255, blank=True, null=True)
    electronic_stamp = models.CharField(max_length=120, default="Electronic School Stamp")
    colour_theme = models.CharField(max_length=30, default="#0f766e")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "saas_school_tenants"
        verbose_name = "School Tenant"
        verbose_name_plural = "School Tenants"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if not self.local_testing_port and not self.production_domain:
            raise ValidationError("Either a local testing port or a production domain name must be explicitly configured.")

    def has_premium_module(self, module_code):
        return tenant_allows_module(self, module_code)

    def has_module(self, module_code):
        return tenant_allows_module(self, module_code)


COMPULSORY_MODULES = {
    "student_registration",
    "student_records",
    "fees_management",
    "payment_reconciliation",
    "reports_analytics",
}

PREMIUM_MODULES = {
    "human_resources",
    "payroll",
    "advanced_business_intelligence",
    "api_integrations",
    "custom_branding",
}

MODULE_DEPENDENCIES = {
    "payroll": {"human_resources"},
    "library_fines": {"fees_management"},
    "transport_fees": {"fees_management"},
    "asset_depreciation": {"accounting"},
}


def subscription_allows_module(subscription_plan, module_code):
    if module_code not in PREMIUM_MODULES:
        return True
    return subscription_plan in {"PREMIUM", "ELITE", "ENTERPRISE", "CUSTOM"}


def tenant_allows_module(tenant, module_code):
    if module_code in COMPULSORY_MODULES:
        return True
    if not subscription_allows_module(tenant.subscription_plan, module_code):
        return False
    try:
        activation = tenant.module_activations.filter(module__code=module_code).first()
    except Exception:
        return subscription_allows_module(tenant.subscription_plan, module_code)
    if activation:
        return activation.status in {"ACTIVE", "TRIAL"}
    return True


class SubscriptionPlan(models.Model):
    PLAN_CHOICES = [
        ("STARTER", "Starter Package"),
        ("STANDARD", "Standard Package"),
        ("ENTERPRISE", "Enterprise Package"),
        ("CUSTOM", "Custom Package"),
        ("BASIC", "Basic School Plan"),
        ("PREMIUM", "Premium Enterprise Plan"),
        ("ELITE", "Elite Unified Plan"),
    ]

    code = models.CharField(max_length=30, choices=PLAN_CHOICES, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True, null=True)
    monthly_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    quarterly_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    annual_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    trial_days = models.PositiveIntegerField(default=14)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "saas_subscription_plans"
        ordering = ["monthly_price", "name"]

    def __str__(self):
        return self.name


class ModuleDefinition(models.Model):
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    compulsory = models.BooleanField(default=False)
    premium = models.BooleanField(default=False)
    dependencies = models.ManyToManyField("self", symmetrical=False, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "saas_module_definitions"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TenantSubscription(models.Model):
    STATUS_CHOICES = [
        ("TRIAL", "Trial"),
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("SUSPENDED", "Suspended"),
        ("CANCELLED", "Cancelled"),
    ]
    BILLING_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("QUARTERLY", "Quarterly"),
        ("ANNUAL", "Annual"),
    ]

    subscription_number = models.CharField(max_length=50, unique=True)
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscriptions")
    start_date = models.DateField()
    expiry_date = models.DateField()
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CHOICES, default="MONTHLY")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="TRIAL")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "saas_tenant_subscriptions"
        ordering = ["-created_at"]

    def __str__(self):
        return self.subscription_number


class TenantModuleActivation(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("DISABLED", "Disabled"),
        ("TRIAL", "Trial"),
        ("EXPIRED", "Expired"),
    ]

    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name="module_activations")
    module = models.ForeignKey(ModuleDefinition, on_delete=models.PROTECT, related_name="tenant_activations")
    subscription = models.ForeignKey(TenantSubscription, on_delete=models.CASCADE, related_name="module_activations", null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    activated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "saas_tenant_module_activations"
        unique_together = ("tenant", "module")


class SubscriptionInvoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    subscription = models.ForeignKey(TenantSubscription, on_delete=models.PROTECT, related_name="invoices")
    invoice_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=30, default="OPEN")

    class Meta:
        db_table = "saas_subscription_invoices"
        ordering = ["-invoice_date"]


class SubscriptionPayment(models.Model):
    METHOD_CHOICES = [
        ("CASH", "Cash"),
        ("BANK_TRANSFER", "Bank Transfer"),
        ("MOBILE_MONEY", "Mobile Money"),
        ("ONLINE", "Online Payment"),
    ]

    payment_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(SubscriptionInvoice, on_delete=models.PROTECT, related_name="payments")
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    reference_number = models.CharField(max_length=120, blank=True, null=True)

    class Meta:
        db_table = "saas_subscription_payments"
        ordering = ["-payment_date"]


class TenantUsageSnapshot(models.Model):
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.CASCADE, related_name="usage_snapshots")
    snapshot_date = models.DateField()
    user_count = models.PositiveIntegerField(default=0)
    student_count = models.PositiveIntegerField(default=0)
    storage_usage_mb = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    database_size_mb = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    active_module_count = models.PositiveIntegerField(default=0)
    api_usage_count = models.PositiveIntegerField(default=0)
    login_activity_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "saas_tenant_usage_snapshots"
        unique_together = ("tenant", "snapshot_date")
        ordering = ["-snapshot_date"]


class SchoolBrandingProfile(models.Model):
    tenant = models.OneToOneField(SchoolTenant, on_delete=models.CASCADE, related_name="branding_profile")
    report_header = models.CharField(max_length=255, blank=True, null=True)
    electronic_stamp = models.CharField(max_length=120, default="Electronic School Stamp")
    pdf_branding_notes = models.TextField(blank=True, null=True)
    colour_theme = models.CharField(max_length=30, default="#0f766e")
    white_label_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = "saas_school_branding_profiles"


class SaaSAuditLog(models.Model):
    action = models.CharField(max_length=120)
    tenant = models.ForeignKey(SchoolTenant, on_delete=models.SET_NULL, null=True, blank=True, related_name="saas_audit_logs")
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    user = models.ForeignKey("auth.User", on_delete=models.SET_NULL, null=True, blank=True)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "saas_audit_logs"
        ordering = ["-created_at"]


class TenantQuerySet(models.QuerySet):
    pass


class TenantManager(models.Manager):
    def get_queryset(self):
        tenant = get_current_tenant()
        if tenant:
            return TenantQuerySet(self.model, using=self._db).filter(tenant=tenant)
        return TenantQuerySet(self.model, using=self._db)

    def global_query(self):
        return TenantQuerySet(self.model, using=self._db)


class TenantBaseModel(models.Model):
    tenant = models.ForeignKey(
        SchoolTenant,
        on_delete=models.CASCADE,
        related_name="%(class)s_records"
    )

    objects = TenantManager()

    class Meta:
        abstract = True
