from contextlib import contextmanager
from pathlib import Path
import tempfile

from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.template.loader import get_template
from django.test import Client
from django.urls import reverse

from academic_structure.services import current_calendar
from fees.services import current_period
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
    help = "Run safe production smoke tests for a tenant."

    def add_arguments(self, parser):
        parser.add_argument("--tenant", required=True, help="Tenant subdomain or production domain.")

    def handle(self, *args, **options):
        tenant_ref = options["tenant"]
        tenant = (
            SchoolTenant.objects.filter(subdomain=tenant_ref).first()
            or SchoolTenant.objects.filter(production_domain=tenant_ref).first()
            or SchoolTenant.objects.filter(custom_domain=tenant_ref).first()
        )
        if tenant is None:
            raise CommandError(f"Tenant not found: {tenant_ref}")

        failures = []
        results = []
        results.append(("tenant_found", True, tenant.production_domain or tenant.subdomain))

        with tenant_default_database(tenant):
            results.append(("database_reachable", True, connections["default"].settings_dict.get("NAME")))
            failures.extend(self._check_migrations(results))
            failures.extend(self._check_calendar(results))
            failures.extend(self._check_templates(results))
            failures.extend(self._check_urls(results))
            failures.extend(self._check_static(results))
            failures.extend(self._check_media(results))
            failures.extend(self._check_dependencies(results))

        failures.extend(self._check_routes(results, tenant))

        for name, ok, detail in results:
            status = "OK" if ok else "FAIL"
            self.stdout.write(f"[{status}] {name}: {detail}")

        if failures:
            raise CommandError(f"Smoke test failed: {', '.join(failures)}")

    def _check_migrations(self, results):
        executor = MigrationExecutor(connections["default"])
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        ok = not plan
        results.append(("migrations_applied", ok, "up-to-date" if ok else f"{len(plan)} unapplied migration(s)"))
        return [] if ok else ["migrations_applied"]

    def _check_calendar(self, results):
        snapshot = current_calendar(force_sync=True)
        term, year = current_period()
        ok = bool(snapshot.display_term and year)
        results.append(("current_term_resolved", ok, f"{term} · {year} ({snapshot.status})"))
        return [] if ok else ["current_term_resolved"]

    def _check_templates(self, results):
        required = [
            "student_portal/login.html",
            "staff_portal/login.html",
            "accounts/dashboard.html",
        ]
        missing = []
        for template_name in required:
            try:
                get_template(template_name)
            except Exception:
                missing.append(template_name)
        ok = not missing
        results.append(("templates_found", ok, ", ".join(required if ok else missing)))
        return [] if ok else ["templates_found"]

    def _check_urls(self, results):
        required = [
            reverse("student_portal:login"),
            reverse("staff_portal:login"),
            reverse("school_admin:dashboard"),
        ]
        results.append(("url_reversal", True, ", ".join(required)))
        return []

    def _check_static(self, results):
        manifest = Path("/app/staticfiles/staticfiles.json")
        ok = manifest.exists()
        results.append(("static_manifest", ok, str(manifest)))
        return [] if ok else ["static_manifest"]

    def _check_media(self, results):
        media_root = Path("/app/uploads")
        media_root.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(dir=media_root, prefix="smoke-", suffix=".tmp", delete=False) as handle:
                temp_path = Path(handle.name)
            temp_path.unlink(missing_ok=True)
            ok = True
            detail = str(media_root)
        except Exception as exc:
            ok = False
            detail = str(exc)
        results.append(("media_write_permission", ok, detail))
        return [] if ok else ["media_write_permission"]

    def _check_routes(self, results, tenant):
        client = Client(
            HTTP_HOST=tenant.production_domain or f"{tenant.subdomain}.raydonsystems.co.zw",
            secure=True,
            HTTP_X_FORWARDED_PROTO="https",
        )
        student_response = client.get(reverse("student_portal:login"))
        staff_response = client.get(reverse("staff_portal:login"))
        results.append(("student_login_route", student_response.status_code == 200, str(student_response.status_code)))
        results.append(("staff_login_route", staff_response.status_code == 200, str(staff_response.status_code)))
        return [] if student_response.status_code == 200 and staff_response.status_code == 200 else ["student_login_route", "staff_login_route"]

    def _check_dependencies(self, results):
        try:
            import qrcode  # noqa: F401
            import reportlab  # noqa: F401
            ok = True
            detail = "reportlab,qrcode"
        except Exception as exc:
            ok = False
            detail = str(exc)
        results.append(("payment_pdf_dependencies", ok, detail))
        return [] if ok else ["payment_pdf_dependencies"]
