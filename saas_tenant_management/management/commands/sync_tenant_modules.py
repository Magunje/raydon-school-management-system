from django.core.management.base import BaseCommand, CommandError

from saas_tenant_management.models import SchoolTenant
from saas_tenant_management.services import sync_tenant_modules


class Command(BaseCommand):
    help = "Re-sync enabled module assignments for a tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True)

    def handle(self, *args, **options):
        tenant_ref = options["tenant"]
        tenant = (
            SchoolTenant.objects.filter(school_code=tenant_ref).first()
            or SchoolTenant.objects.filter(subdomain=tenant_ref).first()
        )
        if tenant is None:
            raise CommandError(f"Tenant not found: {tenant_ref}")
        modules = list(tenant.tenant_modules.filter(enabled=True).values_list("module_name", flat=True))
        sync_tenant_modules(tenant, modules)
        self.stdout.write(f"{tenant.school_code}: synced {len(modules)} module(s)")

