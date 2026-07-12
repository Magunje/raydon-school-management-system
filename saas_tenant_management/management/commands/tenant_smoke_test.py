from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.test import Client
from django.urls import reverse

from saas_tenant_management.management.commands._tenant_utils import tenant_database_alias
from saas_tenant_management.models import SchoolTenant


class Command(BaseCommand):
    help = "Run a tenant smoke test."

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
        alias = tenant_database_alias(tenant)
        media_root = Path("/app/uploads") / "tenants" / str(tenant.tenant_id)
        media_ok = media_root.exists()
        client = Client(HTTP_HOST=tenant.production_domain, secure=True, HTTP_X_FORWARDED_PROTO="https")
        checks = {
            "tenant_record": bool(tenant.pk),
            "domain": bool(tenant.production_domain),
            "database_alias": bool(alias),
            "modules": tenant.tenant_modules.filter(enabled=True).exists(),
            "media": media_ok,
            "student_login": client.get(reverse("student_portal:login")).status_code == 200,
            "staff_login": client.get(reverse("staff_portal:login")).status_code == 200,
            "dashboard_route": client.get(reverse("school_admin:dashboard")).status_code in {200, 302},
        }
        failed = [name for name, ok in checks.items() if not ok]
        for name, ok in checks.items():
            self.stdout.write(f"[{'OK' if ok else 'FAIL'}] {name}")
        if failed:
            raise CommandError(", ".join(failed))
