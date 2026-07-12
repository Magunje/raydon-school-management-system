import datetime
import json

from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone

from saas_tenant_management.models import SchoolTenant, TenantModule
from saas_tenant_management.services import (
    DEFAULT_TENANT_MODULES,
    check_tenant_availability,
    create_tenant_record,
    create_tenant_super_admin,
    generate_temporary_password,
    install_tenant_connection,
    log_saas_action,
    normalize_tenant_payload,
    renew_subscription,
    retry_tenant_provisioning,
    sync_tenant_modules,
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
    status_filter = request.GET.get("status", "").strip().upper()
    plan_filter = request.GET.get("plan", "").strip().upper()
    trial_filter = request.GET.get("trial", "").strip().lower()
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
    if status_filter:
        if status_filter == "EXPIRED":
            tenants = tenants.filter(subscription_end__lt=timezone.localdate())
        else:
            tenants = tenants.filter(provisioning_status=status_filter)
    if plan_filter:
        tenants = tenants.filter(plan_type=plan_filter)
    if trial_filter in {"true", "false"}:
        tenants = tenants.filter(is_trial=(trial_filter == "true"))
    return tenants


def tenant_stats():
    today = timezone.localdate()
    tenants = SchoolTenant.objects.all()
    return {
        "total_tenants": tenants.count(),
        "active_tenants": tenants.filter(provisioning_status="ACTIVE", is_suspended=False).count(),
        "pending_tenants": tenants.filter(provisioning_status="PENDING").count(),
        "provisioning_tenants": tenants.filter(provisioning_status="PROVISIONING").count(),
        "failed_tenants": tenants.filter(provisioning_status="FAILED").count(),
        "suspended_tenants": tenants.filter(provisioning_status="SUSPENDED").count(),
        "starter_tenants": tenants.filter(plan_type="STARTER").count(),
        "standard_tenants": tenants.filter(plan_type="STANDARD").count(),
        "premium_tenants": tenants.filter(plan_type="PREMIUM").count(),
        "enterprise_tenants": tenants.filter(plan_type="ENTERPRISE").count(),
        "expired_subscriptions": tenants.filter(subscription_end__lt=today).count(),
        "expiring_soon": tenants.filter(subscription_end__gte=today, subscription_end__lte=today + datetime.timedelta(days=30)).count(),
        "trial_accounts": tenants.filter(is_trial=True).count(),
    }


def serialize_tenant(tenant, include_modules=True):
    latest_subscription = tenant.subscriptions.order_by("-created_at").first()
    subscription_status = "Expired" if tenant.subscription_end and tenant.subscription_end < timezone.localdate() else tenant.provisioning_status
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
        "full_hostname": tenant.full_hostname,
        "custom_domain": tenant.custom_domain,
        "testing_port": tenant.local_testing_port,
        "production_domain": tenant.production_domain,
        "database_name": tenant.database_name or tenant.tenant_database_identifier,
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
        "updated_at": tenant.updated_at.isoformat(),
        "provisioning_status": tenant.provisioning_status,
        "provisioning_error": tenant.provisioning_error or "",
        "provisioning_started_at": tenant.provisioning_started_at.isoformat() if tenant.provisioning_started_at else "",
        "provisioning_completed_at": tenant.provisioning_completed_at.isoformat() if tenant.provisioning_completed_at else "",
        "status_label": subscription_status,
        "school_portal_url": f"https://{tenant.custom_domain or tenant.full_hostname}" if (tenant.custom_domain or tenant.full_hostname) else "",
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
        "selected_status": request.GET.get("status", ""),
        "selected_plan": request.GET.get("plan", ""),
        "selected_trial": request.GET.get("trial", ""),
        "today": timezone.localdate(),
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
@require_http_methods(["GET"])
def api_check_tenant_availability(request):
    if not is_saas_admin(request.user):
        return json_forbidden("School admins cannot access the SaaS Admin Console.")
    result = check_tenant_availability(
        school_code=request.GET.get("school_code"),
        subdomain=request.GET.get("subdomain"),
        custom_domain=request.GET.get("custom_domain"),
    )
    return JsonResponse({"ok": True, **result})


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
            "is_trial": payload.get("is_trial", "true"),
            "subscription_start": parse_date(payload.get("subscription_start")) or datetime.date.today(),
            "subscription_end": parse_date(payload.get("subscription_end")),
            "trial_end": parse_date(payload.get("trial_end")),
            "max_students": payload.get("max_students") or 500,
            "max_users": payload.get("max_users") or 25,
            "amount": payload.get("amount") or "0",
            "currency": payload.get("currency") or "USD",
            "billing_cycle": payload.get("billing_cycle") or "MONTHLY",
            "modules": payload.getlist("modules") if hasattr(payload, "getlist") else payload.get("modules"),
        }
        result = create_tenant_record(
            data,
            logo=request.FILES.get("school_logo"),
            user=request.user,
            provision=True,
        )
        status_code = 201 if result["tenant"].provisioning_status == "ACTIVE" else 202
        return JsonResponse(
            {
                "ok": result["tenant"].provisioning_status == "ACTIVE",
                "tenant": serialize_tenant(result["tenant"]),
                "admin": result["admin"],
                "provisioning": result["provisioning"],
                "message": "Tenant created successfully." if result["tenant"].provisioning_status == "ACTIVE" else "Tenant record created, but provisioning failed. Retry provisioning from the tenant table.",
            },
            status=status_code,
        )
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ValidationError) and hasattr(exc, "message_dict"):
            error = next(iter(exc.message_dict.values()))[0]
        else:
            error = str(exc)
        return JsonResponse({"ok": False, "error": error}, status=400)


@login_required
@require_http_methods(["GET"])
def api_tenant_detail(request, tenant_id):
    if not is_saas_admin(request.user):
        return json_forbidden("School admins cannot access tenant details.")
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})


@login_required
@require_http_methods(["PUT", "PATCH", "POST"])
def api_update_tenant(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    try:
        payload = request_payload(request)
        previous = serialize_tenant(tenant)
        normalized = normalize_tenant_payload(
            {
                "school_name": payload.get("school_name", tenant.name),
                "school_code": payload.get("school_code", tenant.school_code),
                "school_email": payload.get("school_email", tenant.email_address),
                "school_phone": payload.get("school_phone", tenant.telephone),
                "school_address": payload.get("school_address", tenant.address),
                "subdomain": payload.get("subdomain", tenant.subdomain),
                "custom_domain": payload.get("custom_domain", tenant.custom_domain),
                "testing_port": payload.get("testing_port", tenant.local_testing_port),
                "plan_type": payload.get("plan_type", tenant.plan_type),
                "max_students": payload.get("max_students", tenant.max_students),
                "max_users": payload.get("max_users", tenant.max_users),
                "modules": payload.getlist("modules") if hasattr(payload, "getlist") else list(tenant.tenant_modules.filter(enabled=True).values_list("module_name", flat=True)),
                "subscription_start": parse_date(payload.get("subscription_start")) or tenant.subscription_start,
                "subscription_end": parse_date(payload.get("subscription_end")) or tenant.subscription_end,
                "trial_end": parse_date(payload.get("trial_end")) or tenant.trial_end,
                "trial_period": payload.get("trial_period") or 14,
                "is_trial": payload.get("is_trial", tenant.is_trial),
                "currency": payload.get("currency") or "USD",
                "amount": payload.get("amount") or "0",
                "billing_cycle": payload.get("billing_cycle") or "MONTHLY",
            }
        )
        conflicts = check_tenant_availability(
            school_code=normalized["school_code"],
            subdomain=normalized["subdomain"],
            custom_domain=normalized["custom_domain"],
            exclude_tenant_id=tenant.tenant_id,
        )
        if conflicts["conflicts"]:
            raise ValidationError({"availability": conflicts["conflicts"]})
        tenant.name = normalized["school_name"]
        tenant.school_code = normalized["school_code"]
        tenant.email_address = normalized["school_email"] or None
        tenant.telephone = normalized["school_phone"] or tenant.telephone
        tenant.address = normalized["school_address"] or tenant.address
        tenant.subdomain = normalized["subdomain"]
        tenant.custom_domain = normalized["custom_domain"]
        tenant.local_testing_port = normalized["testing_port"]
        tenant.plan_type = normalized["plan_type"]
        tenant.max_students = normalized["max_students"]
        tenant.max_users = normalized["max_users"]
        tenant.is_trial = normalized["is_trial"]
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
            sync_tenant_modules(tenant, modules, user=request.user)
        log_saas_action("Tenant update", tenant=tenant, user=request.user, previous_value=previous, new_value=serialize_tenant(tenant))
        return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, ValidationError) and hasattr(exc, "message_dict"):
            error = next(iter(exc.message_dict.values()))[0]
        else:
            error = str(exc)
        return JsonResponse({"ok": False, "error": error}, status=400)


@login_required
@require_http_methods(["DELETE", "POST"])
def api_delete_tenant(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    if tenant.provisioning_status == "ACTIVE":
        return JsonResponse({"ok": False, "error": "Active production tenants cannot be deleted from the SaaS console."}, status=409)
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
    tenant.provisioning_status = "ACTIVE"
    tenant.save(update_fields=["is_active", "is_suspended", "provisioning_status", "active", "updated_at"])
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
    tenant.provisioning_status = "SUSPENDED"
    tenant.save(update_fields=["is_active", "is_suspended", "provisioning_status", "active", "updated_at"])
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


@login_required
@require_POST
def api_retry_tenant_provisioning(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    try:
        result = retry_tenant_provisioning(tenant, user=request.user)
        return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant), "admin": result["admin"]})
    except Exception as exc:
        return JsonResponse({"ok": False, "error": str(exc), "tenant": serialize_tenant(tenant)}, status=500)


@login_required
@require_POST
def api_update_tenant_modules(request, tenant_id):
    if not is_super_admin(request.user):
        return json_forbidden()
    tenant = get_object_or_404(SchoolTenant, tenant_id=tenant_id)
    payload = request_payload(request)
    modules = payload.getlist("modules") if hasattr(payload, "getlist") else payload.get("modules", [])
    sync_tenant_modules(tenant, modules, user=request.user)
    log_saas_action("Tenant modules updated", tenant=tenant, user=request.user, new_value={"modules": modules})
    return JsonResponse({"ok": True, "tenant": serialize_tenant(tenant)})
