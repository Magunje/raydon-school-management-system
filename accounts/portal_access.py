from functools import wraps

from django.contrib import messages
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from accounts.permissions import (
    ROLE_ACCOUNTANT,
    ROLE_BURSAR,
    ROLE_CLERK,
    ROLE_COUNSELLOR,
    ROLE_DEPUTY_HEAD,
    ROLE_HEAD,
    ROLE_HEAD_ALT,
    ROLE_HOD,
    ROLE_HOSTEL,
    ROLE_HR_OFFICER,
    ROLE_LIBRARIAN,
    ROLE_NURSE,
    ROLE_PAYROLL_OFFICER,
    ROLE_REGISTRAR,
    ROLE_SAAS_ADMIN,
    ROLE_STUDENT,
    ROLE_SUPER_ADMIN,
    ROLE_TEACHER,
    ROLE_TRANSPORT,
    normalized_role,
)


SCHOOL_ADMIN_ROLES = {
    ROLE_SUPER_ADMIN,
    ROLE_HEAD,
    ROLE_HEAD_ALT,
    ROLE_DEPUTY_HEAD,
    ROLE_HOD,
    ROLE_BURSAR,
    ROLE_ACCOUNTANT,
    ROLE_REGISTRAR,
    ROLE_CLERK,
    "Administrator",
}

STAFF_PORTAL_ROLES = {
    ROLE_TEACHER,
    ROLE_LIBRARIAN,
    ROLE_COUNSELLOR,
    ROLE_HR_OFFICER,
    ROLE_PAYROLL_OFFICER,
    ROLE_TRANSPORT,
    ROLE_HOSTEL,
    ROLE_NURSE,
}

STUDENT_PORTAL_SESSION_KEYS = {
    "active_portal",
    "selected_role",
    "staff_profile_id",
    "student_profile_id",
    "tenant_id",
    "student_pupil_id",
    "student_admission_no",
    "student_tenant_id",
}


def clear_portal_session_state(request):
    for key in STUDENT_PORTAL_SESSION_KEYS:
        request.session.pop(key, None)


def set_active_portal(request, portal_name):
    request.session["active_portal"] = portal_name
    tenant = getattr(request, "tenant", None)
    if getattr(tenant, "tenant_id", None):
        request.session["tenant_id"] = str(tenant.tenant_id)


def portal_enabled(request, portal_name):
    tenant = getattr(request, "tenant", None)
    if tenant is None:
        return portal_name == "saas_admin"
    if not getattr(tenant, "active", False) or not getattr(tenant, "is_active", False):
        return False
    return True


def is_school_admin_user(user):
    return normalized_role(user) in SCHOOL_ADMIN_ROLES


def is_staff_portal_user(user):
    return normalized_role(user) in STAFF_PORTAL_ROLES


def is_student_user(user):
    return normalized_role(user) == ROLE_STUDENT


def is_saas_admin_user(request):
    role = normalized_role(getattr(request, "user", None))
    return getattr(request, "tenant", None) is None and role in {ROLE_SUPER_ADMIN, ROLE_SAAS_ADMIN}


def safe_next_url(request, next_value, portal_prefix, fallback):
    if not next_value:
        return fallback
    if not url_has_allowed_host_and_scheme(
        url=next_value,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback
    if not next_value.startswith(portal_prefix):
        return fallback
    return next_value


def _redirect_to_login(login_name, request):
    login_url = reverse(login_name)
    next_url = request.get_full_path()
    separator = "&" if "?" in login_url else "?"
    return HttpResponseRedirect(f"{login_url}{separator}{REDIRECT_FIELD_NAME}={next_url}")


def staff_portal_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login("staff_portal:login", request)
        if not portal_enabled(request, "staff_portal"):
            messages.error(request, "This portal is not available for the selected school.")
            return redirect("staff_portal:login")
        if not is_staff_portal_user(request.user):
            messages.error(request, "This account is not allowed to use the Staff Portal.")
            return redirect("staff_portal:login")
        set_active_portal(request, "staff_portal")
        return view_func(request, *args, **kwargs)

    return wrapped


def school_admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login("accounts:login", request)
        if getattr(request, "tenant", None) is None:
            messages.error(request, "Use the SaaS administration portal for this account.")
            return redirect("saas_admin:dashboard")
        if not portal_enabled(request, "school_admin"):
            messages.error(request, "This portal is not available for the selected school.")
            return redirect("accounts:login")
        if not is_school_admin_user(request.user):
            messages.error(request, "This account is not allowed to use the School Administration portal.")
            return redirect("accounts:login")
        set_active_portal(request, "school_admin")
        return view_func(request, *args, **kwargs)

    return wrapped


def saas_admin_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _redirect_to_login("accounts:login", request)
        if not is_saas_admin_user(request):
            messages.error(request, "This account is not allowed to use the SaaS administration portal.")
            return redirect("accounts:dashboard")
        set_active_portal(request, "saas_admin")
        return view_func(request, *args, **kwargs)

    return wrapped
