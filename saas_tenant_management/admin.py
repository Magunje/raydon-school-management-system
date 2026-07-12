from django.contrib import admin
from saas_tenant_management.models import SchoolTenant, TenantModule, TenantSubscription


@admin.register(SchoolTenant)
class SchoolTenantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "school_code",
        "subdomain",
        "custom_domain",
        "production_domain",
        "local_testing_port",
        "plan_type",
        "is_active",
        "is_suspended",
        "telephone",
        "created_at",
    )
    list_filter = ("plan_type", "is_active", "is_suspended", "is_trial", "created_at")
    search_fields = ("name", "school_code", "subdomain", "custom_domain", "production_domain", "telephone")
    ordering = ("-created_at",)
    
    fieldsets = (
        ("School Information", {
            "fields": (
                "name",
                "school_code",
                "email_address",
                "telephone",
                "address",
                "logo",
            )
        }),
        ("Domain Routing", {
            "fields": (
                "subdomain",
                "custom_domain",
                "production_domain",
                "local_testing_port",
            )
        }),
        ("Subscription", {
            "fields": (
                "plan_type",
                "subscription_plan",
                "max_students",
                "max_users",
                "subscription_start",
                "subscription_end",
                "trial_end",
                "is_trial",
                "is_active",
                "is_suspended",
                "active",
            )
        }),
        ("Tenant Database", {
            "fields": (
                "database_name",
                "database_user",
                "database_password",
                "tenant_database_identifier",
            )
        }),
    )


@admin.register(TenantModule)
class TenantModuleAdmin(admin.ModelAdmin):
    list_display = ("tenant", "module_name", "enabled", "updated_at")
    list_filter = ("enabled", "module_name")
    search_fields = ("tenant__name", "tenant__school_code", "module_name")


@admin.register(TenantSubscription)
class TenantSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("subscription_number", "tenant", "plan", "status", "payment_status", "amount", "currency", "expiry_date")
    list_filter = ("status", "payment_status", "currency", "expiry_date")
    search_fields = ("subscription_number", "tenant__name", "tenant__school_code")
