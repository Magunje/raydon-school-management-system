from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from saas_tenant_management.models import SchoolTenant

@login_required
def tenant_list(request):
    tenants = SchoolTenant.objects.all()
    
    # Telemetry
    total_tenants = tenants.count()
    active_tenants = tenants.filter(active=True).count()
    premium_tenants = tenants.filter(subscription_plan__in=["PREMIUM", "ELITE", "ENTERPRISE"]).count()
    starter_tenants = tenants.filter(subscription_plan="STARTER").count()
    
    context = {
        "tenants": tenants,
        "total_tenants": total_tenants,
        "active_tenants": active_tenants,
        "premium_tenants": premium_tenants,
        "starter_tenants": starter_tenants,
    }
    return render(request, "saas_tenant_management/tenant_list.html", context)
