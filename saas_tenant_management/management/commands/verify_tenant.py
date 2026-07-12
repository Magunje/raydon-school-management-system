from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

from saas_tenant_management.management.commands._tenant_utils import tenant_database_alias
from saas_tenant_management.models import SchoolTenant


class Command(BaseCommand):
    help = "Verify tenant database connectivity, migrations, admin user, and modules."

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
        executor = MigrationExecutor(connections[alias])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            raise CommandError(f"Unapplied migrations: {len(plan)}")
        with connections[alias].cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM auth_user")
            admin_users = cursor.fetchone()[0]
        modules = tenant.tenant_modules.filter(enabled=True).count()
        self.stdout.write(f"{tenant.school_code}: admins={admin_users} modules={modules} migrations=ok")
