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
        ("BASIC", "Basic School Plan"),
        ("PREMIUM", "Premium Enterprise Plan"),
        ("ELITE", "Elite Unified Plan"),
    ]

    tenant_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, default="RAYDON HIGH SCHOOL")
    active = models.BooleanField(default=True)
    
    # Routing fields for your multi-tenant environments
    local_testing_port = models.IntegerField(unique=True, null=True, blank=True)
    production_domain = models.CharField(max_length=255, unique=True, null=True, blank=True)
    
    # File handling linking to your dynamic path script
    logo = models.ImageField(upload_to=tenant_media_path, null=True, blank=True)
    address = models.TextField(default="Harare, Zimbabwe")
    telephone = models.CharField(max_length=50, default="+263771000000")
    subscription_plan = models.CharField(max_length=20, choices=SUBSCRIPTION_TIERS, default="BASIC")

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
