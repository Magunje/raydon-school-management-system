import hashlib
import re
import secrets

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone

from .models import (
    APICredential,
    CustomRole,
    LoginHistory,
    PasswordPolicy,
    PermissionDefinition,
    RolePermission,
    SecurityIncident,
    SecurityNotification,
    SystemAdminAuditLog,
    UserSecurityProfile,
    UserSessionRecord,
)


def next_incident_number():
    year = timezone.now().year
    prefix = f"SEC-{year}-"
    latest = SecurityIncident.objects.filter(incident_number__startswith=prefix).order_by("-incident_number").first()
    if not latest:
        return f"{prefix}000001"
    try:
        number = int(latest.incident_number.split("-")[-1]) + 1
    except ValueError:
        number = 1
    return f"{prefix}{number:06d}"


def log_admin_action(action, user=None, tenant=None, object_reference=None, previous_value=None, new_value=None, reason=None, request=None):
    return SystemAdminAuditLog.objects.create(
        action=action,
        user=user if getattr(user, "is_authenticated", False) else None,
        tenant=tenant,
        object_reference=object_reference,
        previous_value=previous_value,
        new_value=new_value,
        reason=reason,
        ip_address=_request_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT") if request else None,
    )


def _request_ip(request):
    if not request:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def create_user_with_security_profile(username, email, password, full_name, role=None, tenant=None, phone_number=None, created_by=None):
    User = get_user_model()
    if User.objects.filter(username__iexact=username).exists():
        raise ValidationError("Username must be unique.")
    if UserSecurityProfile.objects.filter(email_address__iexact=email).exists() or User.objects.filter(email__iexact=email).exists():
        raise ValidationError("Email address must be unique.")
    user = User.objects.create_user(username=username, email=email, password=password)
    profile = UserSecurityProfile.objects.create(
        user=user,
        tenant=tenant,
        full_name=full_name,
        email_address=email,
        phone_number=phone_number,
        password_changed_at=timezone.now(),
    )
    if role:
        profile.custom_roles.add(role)
    log_admin_action("User creation", user=created_by, tenant=tenant, object_reference=username, new_value={"email": email, "full_name": full_name})
    return user, profile


def clone_role(role, new_name, new_code, user=None):
    clone = CustomRole.objects.create(
        name=new_name,
        code=new_code,
        description=role.description,
        scope=role.scope,
        tenant=role.tenant,
        parent_role=role,
        created_by=user,
    )
    for role_permission in role.role_permissions.select_related("permission"):
        RolePermission.objects.create(
            role=clone,
            permission=role_permission.permission,
            granted=role_permission.granted,
            assigned_by=user,
        )
    log_admin_action("Role cloned", user=user, tenant=role.tenant, object_reference=role.code, new_value={"clone": new_code})
    return clone


def assign_permission(role, permission_code, user=None):
    permission = PermissionDefinition.objects.get(code=permission_code)
    assignment, _ = RolePermission.objects.update_or_create(
        role=role,
        permission=permission,
        defaults={"granted": True, "assigned_by": user},
    )
    log_admin_action("Permission assigned", user=user, tenant=role.tenant, object_reference=role.code, new_value={"permission": permission_code})
    return assignment


def validate_password_against_policy(password, policy=None):
    policy = policy or PasswordPolicy.objects.filter(is_active=True).order_by("id").first()
    if not policy:
        return []
    errors = []
    if len(password or "") < policy.minimum_length:
        errors.append(f"Password must be at least {policy.minimum_length} characters.")
    if policy.require_uppercase and not re.search(r"[A-Z]", password or ""):
        errors.append("Password must include an uppercase character.")
    if policy.require_lowercase and not re.search(r"[a-z]", password or ""):
        errors.append("Password must include a lowercase character.")
    if policy.require_number and not re.search(r"\d", password or ""):
        errors.append("Password must include a number.")
    if policy.require_special_character and not re.search(r"[^A-Za-z0-9]", password or ""):
        errors.append("Password must include a special character.")
    return errors


def record_login_attempt(username, user=None, success=False, ip_address=None, device=None, browser=None, failure_reason=None, geolocation=None):
    status = "SUCCESS" if success else "FAILED"
    profile = getattr(user, "security_profile", None) if user else None
    if profile:
        if success:
            profile.failed_login_count = 0
            profile.last_login_ip = ip_address
            profile.last_login_device = device
            if profile.status == "LOCKED" and profile.locked_until and profile.locked_until <= timezone.now():
                profile.status = "ACTIVE"
        else:
            profile.failed_login_count += 1
            policy = PasswordPolicy.objects.filter(is_active=True).order_by("id").first()
            max_attempts = policy.max_failed_attempts if policy else 5
            lockout_minutes = policy.lockout_minutes if policy else 30
            if profile.failed_login_count >= max_attempts:
                profile.status = "LOCKED"
                profile.locked_until = timezone.now() + timezone.timedelta(minutes=lockout_minutes)
                status = "LOCKED"
                SecurityNotification.objects.create(
                    user=profile.user,
                    notification_type="FAILED_LOGIN",
                    title="Account locked",
                    message="Your account was locked after repeated failed login attempts.",
                )
        profile.save()
    history = LoginHistory.objects.create(
        user=user,
        username=username,
        status=status,
        ip_address=ip_address,
        device=device,
        browser=browser,
        geolocation=geolocation,
        failure_reason=failure_reason,
    )
    if status in {"LOCKED", "SUSPICIOUS"}:
        create_security_incident("FAILED_LOGIN_MONITORING", "HIGH", f"Login attempt status: {status}", user=user, ip_address=ip_address)
    return history


def terminate_session(session_record, user=None, reason=None):
    session_record.status = "TERMINATED"
    session_record.terminated_at = timezone.now()
    session_record.save(update_fields=["status", "terminated_at"])
    log_admin_action("Session termination", user=user, object_reference=session_record.session_key, reason=reason)
    return session_record


def create_session_record(user, session_key, ip_address=None, user_agent=None, device_fingerprint=None, remember_me=False):
    return UserSessionRecord.objects.create(
        user=user,
        session_key=session_key,
        ip_address=ip_address,
        user_agent=user_agent,
        device_fingerprint=device_fingerprint,
        remember_me=remember_me,
    )


def suspend_user(user_to_suspend, suspended_by=None, reason=None):
    profile = user_to_suspend.security_profile
    previous = {"status": profile.status}
    profile.status = "SUSPENDED"
    profile.suspended_reason = reason
    profile.save()
    SecurityNotification.objects.create(
        user=user_to_suspend,
        notification_type="ACCOUNT_SUSPENSION",
        title="Account suspended",
        message=reason or "Your account has been suspended.",
    )
    log_admin_action("Account suspension", user=suspended_by, tenant=profile.tenant, object_reference=user_to_suspend.username, previous_value=previous, new_value={"status": profile.status}, reason=reason)
    return profile


def reinstate_user(user_to_reinstate, reinstated_by=None, reason=None):
    profile = user_to_reinstate.security_profile
    previous = {"status": profile.status}
    profile.status = "ACTIVE"
    profile.failed_login_count = 0
    profile.locked_until = None
    profile.reinstated_at = timezone.now()
    profile.save()
    log_admin_action("Account reinstatement", user=reinstated_by, tenant=profile.tenant, object_reference=user_to_reinstate.username, previous_value=previous, new_value={"status": profile.status}, reason=reason)
    return profile


def create_security_incident(incident_type, severity, description, user=None, tenant=None, ip_address=None):
    incident = SecurityIncident.objects.create(
        incident_number=next_incident_number(),
        incident_type=incident_type,
        severity=severity,
        description=description,
        user=user,
        tenant=tenant,
        ip_address=ip_address,
    )
    if user:
        SecurityNotification.objects.create(
            user=user,
            notification_type="SECURITY_INCIDENT",
            title=f"Security incident: {incident_type}",
            message=description,
        )
    log_admin_action("Security incident", user=user, tenant=tenant, object_reference=incident.incident_number, new_value={"severity": severity, "type": incident_type})
    return incident


def create_api_credential(name, owner, permissions=None, tenant=None, expires_at=None, rate_limit_per_minute=60):
    raw_key = f"rsk_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    credential = APICredential.objects.create(
        name=name,
        owner=owner,
        tenant=tenant,
        key_prefix=raw_key[:12],
        key_hash=key_hash,
        permissions=permissions or [],
        expires_at=expires_at,
        rate_limit_per_minute=rate_limit_per_minute,
    )
    log_admin_action("API key creation", user=owner, tenant=tenant, object_reference=name, new_value={"permissions": permissions or []})
    return credential, raw_key


def security_dashboard_summary():
    return {
        "total_users": UserSecurityProfile.objects.count(),
        "active_users": UserSecurityProfile.objects.filter(status="ACTIVE").count(),
        "locked_accounts": UserSecurityProfile.objects.filter(status="LOCKED").count(),
        "failed_login_attempts": LoginHistory.objects.filter(status__in=["FAILED", "LOCKED"]).count(),
        "security_alerts": SecurityIncident.objects.exclude(status__in=["RESOLVED", "DISMISSED"]).count(),
        "recent_activity": list(LoginHistory.objects.values("username", "status", "created_at").order_by("-created_at")[:10]),
        "users_by_status": list(UserSecurityProfile.objects.values("status").annotate(count=Count("id")).order_by("status")),
    }
