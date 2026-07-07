import hashlib
import hmac

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from django.db import OperationalError, ProgrammingError

from .models import LegacyUser, UserProfile
from teachers.models import TeacherProfile


STAFF_ADMIN_ROLES = {
    "Super Admin",
    "Administrator",
    "Headmaster",
    "Headmaster / Headmistress",
}


class LegacyUserBackend(BaseBackend):
    """Authenticate existing school users stored in the legacy users table."""

    def find_legacy_user(self, identifier):
        identifier = (identifier or "").strip()
        if not identifier:
            return None
        lookup_errors = (OperationalError, ProgrammingError)
        try:
            user = LegacyUser.objects.filter(username__iexact=identifier).first()
            if user:
                return user
            user = LegacyUser.objects.filter(admission_no__iexact=identifier).first()
            if user:
                return user
            profile = TeacherProfile.objects.filter(email__iexact=identifier).first()
            if profile:
                return LegacyUser.objects.filter(user_id=profile.user_id).first()
        except lookup_errors:
            return None
        return None

    def check_legacy_password(self, stored_hash, password):
        if not stored_hash or not password:
            return False
        if stored_hash.startswith("scrypt:"):
            try:
                method, salt, expected_hex = stored_hash.split("$", 2)
                _name, n, r, p = method.split(":", 3)
                derived = hashlib.scrypt(
                    password.encode("utf-8"),
                    salt=salt.encode("utf-8"),
                    n=int(n),
                    r=int(r),
                    p=int(p),
                    dklen=len(bytes.fromhex(expected_hex)),
                    maxmem=64 * 1024 * 1024,
                )
                return hmac.compare_digest(derived.hex(), expected_hex)
            except (ValueError, TypeError, OSError):
                return False
        return False

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        legacy_user = self.find_legacy_user(username)

        if legacy_user is None or legacy_user.status != "Active":
            return None
        if legacy_user.role in {"Parent", "Student"}:
            return None
        if not self.check_legacy_password(legacy_user.password_hash, password):
            return None

        UserModel = get_user_model()
        user, _created = UserModel.objects.get_or_create(username=legacy_user.username)
        user.is_active = True
        user.is_staff = legacy_user.role in STAFF_ADMIN_ROLES
        user.is_superuser = legacy_user.role == "Super Admin"
        if legacy_user.full_name:
            parts = legacy_user.full_name.split(" ", 1)
            user.first_name = parts[0][:150]
            user.last_name = parts[1][:150] if len(parts) > 1 else ""
        user.set_unusable_password()
        user.save()

        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                "legacy_user_id": legacy_user.user_id,
                "full_name": legacy_user.full_name or legacy_user.username,
                "role": legacy_user.role,
                "status": legacy_user.status,
            },
        )
        return user

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
