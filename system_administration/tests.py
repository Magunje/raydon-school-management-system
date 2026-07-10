from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import (
    CustomRole,
    LoginHistory,
    PasswordPolicy,
    PermissionDefinition,
    SecurityIncident,
    SecurityNotification,
    SystemAdminAuditLog,
    UserSecurityProfile,
    UserSessionRecord,
)
from .services import (
    assign_permission,
    clone_role,
    create_api_credential,
    create_session_record,
    create_user_with_security_profile,
    record_login_attempt,
    reinstate_user,
    security_dashboard_summary,
    suspend_user,
    terminate_session,
    validate_password_against_policy,
)


class SystemAdministrationSecurityTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin", email="admin@example.com", password="Admin123!"
        )
        self.policy = PasswordPolicy.objects.create(
            name="Default Security Policy",
            minimum_length=10,
            max_failed_attempts=2,
            lockout_minutes=15,
        )
        self.role = CustomRole.objects.create(name="Security Officer", code="security_officer")
        self.permission = PermissionDefinition.objects.create(
            code="system.security.read",
            name="Read Security",
            module_code="system_administration",
            level="MODULE",
            action="READ",
        )

    def test_user_role_permission_and_password_policy(self):
        user, profile = create_user_with_security_profile(
            "finance1",
            "finance1@example.com",
            "Finance123!",
            "Finance Officer",
            role=self.role,
            created_by=self.admin,
        )

        assignment = assign_permission(self.role, "system.security.read", user=self.admin)
        clone = clone_role(self.role, "Security Officer Clone", "security_officer_clone", user=self.admin)

        self.assertEqual(profile.status, "ACTIVE")
        self.assertEqual(assignment.permission, self.permission)
        self.assertEqual(clone.role_permissions.count(), 1)
        self.assertIn("Password must be at least", validate_password_against_policy("Ab1!")[0])
        self.assertEqual(validate_password_against_policy("LongEnough1!"), [])
        self.assertTrue(SystemAdminAuditLog.objects.filter(action="User creation").exists())

    def test_failed_login_locks_account_and_creates_alerts(self):
        user, profile = create_user_with_security_profile(
            "teacher1",
            "teacher1@example.com",
            "Teacher123!",
            "Teacher One",
            created_by=self.admin,
        )

        record_login_attempt("teacher1", user=user, success=False, ip_address="127.0.0.1")
        record_login_attempt("teacher1", user=user, success=False, ip_address="127.0.0.1")
        profile.refresh_from_db()

        self.assertEqual(profile.status, "LOCKED")
        self.assertTrue(profile.locked_until > timezone.now())
        self.assertEqual(LoginHistory.objects.filter(username="teacher1").count(), 2)
        self.assertTrue(SecurityIncident.objects.exists())
        self.assertTrue(SecurityNotification.objects.filter(user=user).exists())

    def test_sessions_api_credentials_suspension_and_dashboard(self):
        user, profile = create_user_with_security_profile(
            "auditor1",
            "auditor1@example.com",
            "Auditor123!",
            "Auditor One",
            created_by=self.admin,
        )
        session = create_session_record(user, "abc123", ip_address="127.0.0.1", remember_me=True)
        terminate_session(session, user=self.admin, reason="Manual logout")
        credential, raw_key = create_api_credential("Audit API", user, permissions=["audit.read"])
        suspend_user(user, suspended_by=self.admin, reason="Testing")
        reinstate_user(user, reinstated_by=self.admin, reason="Testing complete")
        profile.refresh_from_db()

        self.assertEqual(UserSessionRecord.objects.get(pk=session.pk).status, "TERMINATED")
        self.assertTrue(raw_key.startswith("rsk_"))
        self.assertEqual(credential.key_prefix, raw_key[:12])
        self.assertEqual(profile.status, "ACTIVE")
        self.assertGreaterEqual(security_dashboard_summary()["total_users"], 1)

    def test_duplicate_email_is_rejected(self):
        create_user_with_security_profile(
            "one",
            "same@example.com",
            "Same123!",
            "One",
            created_by=self.admin,
        )
        with self.assertRaises(ValidationError):
            create_user_with_security_profile(
                "two",
                "same@example.com",
                "Same123!",
                "Two",
                created_by=self.admin,
            )

    def test_security_list_view(self):
        self.client.force_login(self.admin)
        response = self.client.get('/security-admin/')
        self.assertEqual(response.status_code, 200)
