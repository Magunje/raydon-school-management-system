from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from system_administration.models import UserSecurityProfile, CustomRole, PermissionDefinition

@login_required
def security_list(request):
    profiles = UserSecurityProfile.objects.all()
    roles = CustomRole.objects.all()
    permissions = PermissionDefinition.objects.all()
    
    # Telemetry
    total_profiles = profiles.count()
    active_roles = roles.filter(is_active=True).count()
    assigned_permissions = permissions.filter(is_active=True).count()
    locked_accounts = profiles.filter(status="LOCKED").count()
    
    context = {
        "profiles": profiles,
        "roles": roles,
        "permissions": permissions,
        "total_profiles": total_profiles,
        "active_roles": active_roles,
        "assigned_permissions": assigned_permissions,
        "locked_accounts": locked_accounts,
    }
    return render(request, "system_administration/profile_list.html", context)
