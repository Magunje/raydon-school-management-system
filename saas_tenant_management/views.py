import json
import datetime

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST

from saas_tenant_management.models import SchoolTenant, TenantModule
from saas_tenant_management.services import (
    DEFAULT_TENANT_MODULES,
    create_tenant_record,
    create_tenant_super_admin,
    generate_temporary_password,
    install_tenant_connection,
    log_saas_action,
    renew_subscription,
)


def is_saas_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = getattr(getattr(user, "profile", None), "role", "")
    return role in {"Super Admin", "SaaS Administrator"}


def is_super_admin(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    role = getattr(getattr(user, "profile", None), "role", "")
    return role == "Super Admin"


def json_forbidden(message="Only Super Admin can perform this action."):
    return JsonResponse({"ok": False, "error": message}, status=403)


def parse_date(value):
    if not value:
        return None
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def request_payload(request):
    if request.content_type and "application/json" in request.content_type:
        return json.loads(request.body.decode("utf-8") or "{}")
    data = request.POST.copy()
    if hasattr(data, "getlist"):
        modules = data.getlist("modules")
        if modules:
            data.setlist("modules", modules)
    return data


def tenant_queryset(request):
    query = request.GET.get("q", "").strip()
    tenants = SchoolTenant.objects.all().order_by("-created_at")
    if query:
        tenants = tenants.filter(
            Q(name__icontains=query)
            | Q(school_code__icontains=query)
            | Q(production_domain__icontains=query)
            | Q(custom_domain__icontains=query)
            | Q(subdomain__icontains=query)
            | Q(local_testing_port__icontains=query)
            | Q(plan_type__icontains=query)
            | Q(subscription_plan__icontains=query)
        )
    return tenants


def tenant_stats():
    today = datetime.date.today()
    tenants = SchoolTenant.objects.all()
    return {
        "total_tenants": tenants.count(),
        "active_tenants": tenants.filter(is_active=True, is_suspended=False).count(),
        "premium_tenants": tenants.filter(plan_type__in=["PREMIUM", "ENTERPRISE"]).count(),
        "starter_tenants": tenants.filter(plan_type="STARTER").count(),
        "expired_subscriptions": tenants.filter(subscription_end__lt=today).count(),
        "trial_accounts": tenants.filter(is_trial=True).count(),
    }


def serialize_tenant(tenant, include_modules=True):
    latest_subscription = tenant.subscriptions.order_by("-created_at").first()
    payload = {
        "id": str(tenant.tenant_id),
        "school_name": tenant.name,
        "school_code": tenant.school_code,
        "school_email": tenant.email_address,
        "school_phone": tenant.telephone,
        "school_address": tenant.address,
        "school_logo": tenant.logo.url if tenant.logo else "",
        "subdomain": tenant.subdomain,
        "subdomain_domain": tenant.subdomain_domain,
        "custom_domain": tenant.custom_domain,
        "testing_port": tenant.local_testing_port,
        "production_domain": tenant.production_domain,
        "database_name": tenant.database_name or tenant.tenant_database_identifier,
        "database_user": tenant.database_user,
        "plan_type": tenant.plan_type,
        "max_students": tenant.max_students,
        "max_users": tenant.max_users,
        "subscription_start": tenant.subscription_start.isoformat() if tenant.subscription_start else "",
        "subscription_end": tenant.subscription_end.isoformat() if tenant.subscription_end else "",
        "trial_end": tenant.trial_end.isoformat() if tenant.trial_end else "",
        "is_trial": tenant.is_trial,
        "is_active": tenant.is_active,
        "is_suspended": tenant.is_suspended,
        "created_at": tenant.created_at.isoformat(),
        "subscription": {
            "status": latest_subscription.status if latest_subscription else "",
            "payment_status": latest_subscription.payment_status if latest_subscription else "",
            "amount": str(latest_subscription.amount) if latest_subscription else "0.00",
            "currency": latest_subscription.currency if latest_subscription else "USD",
            "next_billing_date": latest_subscription.next_billing_date.isoformat() if latest_subscription and latest_subscription.next_billing_date else "",
        },
    }
    if include_modules:
        payload["modules"] = list(tenant.tenant_modules.filter(enabled=True).values_list("module_name", flat=True))
    return payload


@login_required
@user_passes_test(is_saas_admin)
def tenant_list(request):
    tenants = tenant_queryset(request)
    context = {
        "tenants": tenants,
        "stats": tenant_stats(),
        "module_options": DEFAULT_TENANT_MODULES,
        "plan_types": SchoolTenant.PLAN_TYPES,
        "search_query": request.GET.get("q", ""),
        **tenant_stats(),
    }
    return render(request, "saas_tenant_management/tenant_list.html", context)


@login_required
@require_http_methods(["GET"])
def api_tenants(request):
    if not is_saas_admin(request.user):
        return json_forbidden("School admins cannot access the SaaS Admin Console.")
    tenants = [serialize_tenant(tenant, include_modules=False) for tenant in tenant_queryset(request)]
    return JsonResponse({"ok": True, "stats": tenant_stats(), "tenants": tenants})


@login_required
@require_POST
def api_create_tenant(request):
    if not is_super_admin(request.user):
        return json_forbidden()
    try:
        payload = request_payload(request)
        data = {
            "school_name": payload.get("school_name"),
            "school_code": payload.get("school_code"),
            "school_email": payload.get("school_email"),
            "school_phone": payload.get("school_phone"),
            "school_address": payload.get("school_address"),
            "subdomain": payload.get("subdomain"),
            "custom_domain": payload.get("custom_domain"),
            "testing_port": payload.get("testing_port") or None,
            "plan_type": payload.get("plan_type") or "STANDARD",
            "trial_period": payload.get("trial_period") or 14,
            "subscription_start": parse_date(payload.get("subscription_start")) or datetime.date.today(),
            "subscription_end": parse_date(payload.get("subscription_end")),
            "trial_end": parse_date(payload.get("trial_end")),
            "modules": payload.getlist("modules") if hasattr(payload, "getlist") else payload.get("modules"),
        }
        result = create_tenant_record(
            data,
            logo=request.FILES.get("school_logo"),
            user=request.user,
            provision=True,
        )
        return JsonResponse(
            {
                "ok": True,
                "tenant": serialize_tenant(result["tenant"]),
                "admin": result["admin"],
                "provisioning": result["provisioning"],
            },
            status=201,
        )
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@login_required
@require_http_methods(["GET"])
def api_tenant_detail(request, tenant_id):
    if not is_saas_admin(request.user):
        return json_forbidden("School admins cannot access tenant details.")
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})


@login_required
@require_http_methods(["PUT", "POST"])
def api_update_tenant(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    try:
        payload = request_payload(request)
        previous = serialize_tenant(tenant)
        field_map = {
            "school_name": "name",
            "school_code": "school_code",
            "school_email": "email_address",
            "school_phone": "telephone",
            "school_address": "address",
            "subdomain": "subdomain",
            "custom_domain": "custom_domain",
            "testing_port": "local_testing_port",
            "plan_type": "plan_type",
            "max_students": "max_students",
            "max_users": "max_users",
        }
        for incoming, field in field_map.items():
            if incoming in payload:
                setattr(tenant, field, payload.get(incoming) or None)
        for incoming, field in {
            "subscription_start": "subscription_start",
            "subscription_end": "subscription_end",
            "trial_end": "trial_end",
        }.items():
            if incoming in payload:
                setattr(tenant, field, parse_date(payload.get(incoming)))
        if "school_logo" in request.FILES:
            tenant.logo = request.FILES["school_logo"]
        tenant.full_clean()
        tenant.save()
        if "modules" in payload or (hasattr(payload, "getlist") and payload.getlist("modules")):
            modules = payload.getlist("modules") if hasattr(payload, "getlist") else payload.get("modules", [])
            TenantModule.objects.filter(tenant=tenant).update(enabled=False)
            for module_name in modules:
                TenantModule.objects.update_or_create(
                    tenant=tenant,
                    module_name=module_name,
                    defaults={"enabled": True},
                )
        log_saas_action("Tenant update", tenant=tenant, user=request.user, previous_value=previous, new_value=serialize_tenant(tenant))
        return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)


@login_required
@require_http_methods(["DELETE", "POST"])
def api_delete_tenant(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    previous = serialize_tenant(tenant)
    tenant.delete()
    log_saas_action("Tenant deletion", user=request.user, previous_value=previous)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def api_activate_tenant(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    tenant.is_active = True
    tenant.is_suspended = False
    tenant.save(update_fields=["is_active", "is_suspended", "active", "updated_at"])
    log_saas_action("Tenant activation", tenant=tenant, user=request.user)
    return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})


@login_required
@require_POST
def api_suspend_tenant(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    tenant.is_suspended = True
    tenant.is_active = False
    tenant.save(update_fields=["is_active", "is_suspended", "active", "updated_at"])
    log_saas_action("Tenant suspension", tenant=tenant, user=request.user)
    return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})


@login_required
@require_POST
def api_renew_tenant(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    payload = request_payload(request)
    new_end = parse_date(payload.get("subscription_end")) or (datetime.date.today() + datetime.timedelta(days=365))
    tenant.subscription_end = new_end
    tenant.is_active = True
    tenant.is_suspended = False
    tenant.is_trial = False
    tenant.save(update_fields=["subscription_end", "is_active", "is_suspended", "is_trial", "active", "updated_at"])
    subscription = tenant.subscriptions.order_by("-created_at").first()
    if subscription:
        renew_subscription(subscription, new_end, user=request.user)
    log_saas_action("Tenant subscription renewal", tenant=tenant, user=request.user, new_value={"subscription_end": str(new_end)})
    return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})


@login_required
@require_POST
def api_reset_tenant_password(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    temporary_password = generate_temporary_password()
    alias = install_tenant_connection(tenant)
    admin = create_tenant_super_admin(tenant, alias, temporary_password=temporary_password)
    log_saas_action("Tenant admin password reset", tenant=tenant, user=request.user, reference_number=admin["email"])
    return JsonResponse({"ok": True, "admin": admin})
