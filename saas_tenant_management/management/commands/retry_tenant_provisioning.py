from django.core.management.base import BaseCommand, CommandError

from saas_tenant_management.models import SchoolTenant
from saas_tenant_management.services import retry_tenant_provisioning


class Command(BaseCommand):
    help = "Retry provisioning for a tenant."

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
        result = retry_tenant_provisioning(tenant)
        self.stdout.write(f"{tenant.school_code}: {tenant.provisioning_status} {result['database_name']}")

