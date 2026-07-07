from django.contrib import admin
from saas_tenant_management.models import SchoolTenant


@admin.register(SchoolTenant)
class SchoolTenantAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "production_domain",
        "local_testing_port",
        "subscription_plan",
        "active",
        "telephone",
        "created_at",
    )
    list_filter = ("subscription_plan", "active", "created_at")
    search_fields = ("name", "production_domain", "telephone")
    ordering = ("-created_at",)
    
    fieldsets = (
        ("Master School Configurations", {
            "fields": (
                "name",
                "production_domain",
                "local_testing_port",
                "active",
                "subscription_plan",
            )
        }),
        ("Branding & Files", {
            "fields": (
                "logo",
            )
        }),
        ("Contact & Location Information", {
            "fields": (
                "address",
                "telephone",
            )
        }),
    )
