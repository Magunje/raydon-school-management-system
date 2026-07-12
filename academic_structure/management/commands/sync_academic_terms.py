from contextlib import contextmanager

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.utils.dateparse import parse_date

from academic_structure.services import sync_current_term
from saas_tenant_management.models import SchoolTenant
from saas_tenant_management.services import tenant_database_settings


@contextmanager
def tenant_default_database(tenant):
    default = connections["default"]
    original = default.settings_dict.copy()
    default.close()
    default.settings_dict.update(tenant_database_settings(tenant))
    try:
        yield
    finally:
        default.close()
        default.settings_dict.update(original)


class Command(BaseCommand):
    help = "Synchronise academic years and terms for one tenant or all tenants."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", help="Tenant subdomain or production domain, for example raydonhigh.")
        parser.add_argument("--all-tenants", action="store_true", help="Synchronise every active tenant.")
        parser.add_argument("--date", help="Override the effective date in YYYY-MM-DD format.")
        parser.add_argument("--dry-run", action="store_true", help="Report the resolved term without persisting changes.")

    def handle(self, *args, **options):
        tenant_ref = options.get("tenant")
        all_tenants = options.get("all_tenants")
        dry_run = options.get("dry_run")
        target_date = self._parse_date(options.get("date"))

        if bool(tenant_ref) == bool(all_tenants):
            raise CommandError("Specify exactly one of --tenant or --all-tenants.")

        tenants = self._tenants_for_run(tenant_ref, all_tenants)
        for tenant in tenants:
            with tenant_default_database(tenant):
                snapshot = sync_current_term(tenant=tenant, date=target_date, dry_run=dry_run)
            next_term = snapshot.next_term
            next_label = f"{next_term.name} opens {next_term.start_date}" if next_term else "none"
            self.stdout.write(
                f"{tenant.subdomain or tenant.production_domain}: {snapshot.display_term} · {snapshot.display_year} "
                f"[status={snapshot.status}, next={next_label}, dry_run={dry_run}]"
            )

    def _parse_date(self, value):
        if not value:
            return None
        parsed = parse_date(value)
        if parsed is None:
            raise CommandError("--date must be in YYYY-MM-DD format.")
        return parsed

    def _tenants_for_run(self, tenant_ref, all_tenants):
        if all_tenants:
            tenants = list(SchoolTenant.objects.filter(active=True, is_active=True, is_suspended=False).order_by("name"))
            if not tenants:
                raise CommandError("No active tenants found.")
            return tenants

        tenant = (
            SchoolTenant.objects.filter(subdomain=tenant_ref).first()
            or SchoolTenant.objects.filter(production_domain=tenant_ref).first()
            or SchoolTenant.objects.filter(custom_domain=tenant_ref).first()
        )
        if tenant is None:
            raise CommandError(f"Tenant not found: {tenant_ref}")
        return [tenant]

