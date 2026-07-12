import json

from django.core.management.base import BaseCommand, CommandError

from saas_tenant_management.models import SchoolTenant
from saas_tenant_management.services import check_tenant_availability, normalize_tenant_payload


class Command(BaseCommand):
    help = "Audit tenant records for duplicate domains, malformed subdomains, and failed provisioning."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--fix-safe", action="store_true")
        parser.add_argument("--tenant")
        parser.add_argument("--report")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        fix_safe = options["fix_safe"]
        tenant_ref = options.get("tenant")
        queryset = SchoolTenant.objects.all().order_by("created_at")
        if tenant_ref:
            queryset = queryset.filter(school_code=tenant_ref) | queryset.filter(subdomain=tenant_ref)
        report = []
        for tenant in queryset:
            normalized = normalize_tenant_payload(
                {
                    "school_name": tenant.name,
                    "school_code": tenant.school_code,
                    "school_email": tenant.email_address,
                    "school_phone": tenant.telephone,
                    "school_address": tenant.address,
                    "subdomain": tenant.subdomain,
                    "custom_domain": tenant.custom_domain,
                    "plan_type": tenant.plan_type,
                    "subscription_start": tenant.subscription_start,
                    "subscription_end": tenant.subscription_end,
                    "trial_end": tenant.trial_end,
                    "modules": list(tenant.tenant_modules.filter(enabled=True).values_list("module_name", flat=True)),
                }
            )
            issues = []
            changes = {}
            if tenant.subdomain != normalized["subdomain"]:
                issues.append("subdomain_normalization")
                changes["subdomain"] = normalized["subdomain"]
            if tenant.custom_domain != normalized["custom_domain"]:
                issues.append("custom_domain_normalization")
                changes["custom_domain"] = normalized["custom_domain"]
            availability = check_tenant_availability(
                school_code=normalized["school_code"],
                subdomain=normalized["subdomain"],
                custom_domain=normalized["custom_domain"],
                exclude_tenant_id=tenant.tenant_id,
            )
            if availability["conflicts"]:
                issues.extend(availability["conflicts"])
            if tenant.provisioning_status == "FAILED":
                issues.append("failed_provisioning_visible")
            row = {"tenant": tenant.school_code, "subdomain": tenant.subdomain, "status": tenant.provisioning_status, "issues": issues, "changes": changes}
            report.append(row)
            if fix_safe and changes and not dry_run:
                for field, value in changes.items():
                    setattr(tenant, field, value)
                tenant.save()
        if options.get("report"):
            with open(options["report"], "w", encoding="utf-8") as handle:
                json.dump(report, handle, indent=2)
        for row in report:
            self.stdout.write(json.dumps(row))
        if not report:
            raise CommandError("No tenants found for the requested filter.")

