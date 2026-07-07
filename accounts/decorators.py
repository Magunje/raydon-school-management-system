from .permissions import PAYROLL_ROLES, normalized_role, permission_required


def user_role(user):
    return normalized_role(user)


def user_full_name(user):
    profile = getattr(user, "profile", None)
    if profile and profile.full_name:
        return profile.full_name
    return user.get_full_name() or user.username


def role_required(*roles):
    from .permissions import audit_denied
    from functools import wraps
    from django.contrib import messages
    from django.contrib.auth.decorators import login_required
    from django.shortcuts import redirect

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.is_superuser or user_role(request.user) in roles:
                return view_func(request, *args, **kwargs)
            audit_denied(request, "role:" + ",".join(roles))
            messages.error(request, "Your account is not allowed to open that page.")
            return redirect("accounts:dashboard")

        return wrapped

    return decorator


def payroll_required(view_func):
    return permission_required("payroll.view")(view_func)
