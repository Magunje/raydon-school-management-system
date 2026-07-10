from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class CustomRole(models.Model):
    ROLE_SCOPE_CHOICES = [
        ("GLOBAL", "Global"),
        ("TENANT", "School Tenant"),
    ]

    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=120)
    description = models.TextField(blank=True, null=True)
    scope = models.CharField(max_length=20, choices=ROLE_SCOPE_CHOICES, default="TENANT")
    tenant = models.ForeignKey(
        "saas_tenant_management.SchoolTenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="custom_roles",
    )
    parent_role = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_roles"
    )
    is_system_role = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custom_roles_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_custom_roles"
        unique_together = ("tenant", "code")
        ordering = ["name"]

    def __str__(self):
        return self.name


class PermissionDefinition(models.Model):
    LEVEL_CHOICES = [
        ("MODULE", "Module"),
        ("MENU", "Menu"),
        ("PAGE", "Page"),
        ("ACTION", "Action"),
        ("RECORD", "Record"),
    ]
    ACTION_CHOICES = [
        ("CREATE", "Create"),
        ("READ", "Read"),
        ("UPDATE", "Update"),
        ("DELETE", "Delete"),
        ("APPROVE", "Approve"),
        ("EXPORT", "Export"),
        ("PRINT", "Print"),
    ]

    code = models.CharField(max_length=160, unique=True)
    name = models.CharField(max_length=160)
    module_code = models.CharField(max_length=80)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default="READ")
    record_filter = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sysadmin_permission_definitions"
        ordering = ["module_code", "level", "action", "name"]

    def __str__(self):
        return self.code


class RolePermission(models.Model):
    role = models.ForeignKey(CustomRole, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(PermissionDefinition, on_delete=models.CASCADE, related_name="role_permissions")
    granted = models.BooleanField(default=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="role_permissions_assigned",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_role_permissions"
        unique_together = ("role", "permission")


class UserSecurityProfile(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("SUSPENDED", "Suspended"),
        ("DEACTIVATED", "Deactivated"),
        ("LOCKED", "Locked"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_profile")
    tenant = models.ForeignKey(
        "saas_tenant_management.SchoolTenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_security_profiles",
    )
    full_name = models.CharField(max_length=180, blank=True)
    email_address = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=40, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    custom_roles = models.ManyToManyField(CustomRole, blank=True, related_name="users")
    mfa_enabled = models.BooleanField(default=False)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    password_expires_at = models.DateTimeField(null=True, blank=True)
    require_password_change = models.BooleanField(default=False)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    last_login_device = models.CharField(max_length=255, blank=True, null=True)
    reinstated_at = models.DateTimeField(null=True, blank=True)
    suspended_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sysadmin_user_security_profiles"
        ordering = ["user__username"]

    def clean(self):
        super().clean()
        if self.email_address:
            duplicate = UserSecurityProfile.objects.filter(email_address__iexact=self.email_address)
            if self.pk:
                duplicate = duplicate.exclude(pk=self.pk)
            if duplicate.exists():
                raise ValidationError("Email address must be unique.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_locked(self):
        return self.status == "LOCKED" or bool(self.locked_until and self.locked_until > timezone.now())

    def __str__(self):
        return f"{self.user.username} security profile"


class PasswordPolicy(models.Model):
    name = models.CharField(max_length=120, unique=True)
    tenant = models.ForeignKey(
        "saas_tenant_management.SchoolTenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="password_policies",
    )
    minimum_length = models.PositiveIntegerField(default=8)
    require_uppercase = models.BooleanField(default=True)
    require_lowercase = models.BooleanField(default=True)
    require_number = models.BooleanField(default=True)
    require_special_character = models.BooleanField(default=True)
    password_expiry_days = models.PositiveIntegerField(default=90)
    password_history_count = models.PositiveIntegerField(default=5)
    max_failed_attempts = models.PositiveIntegerField(default=5)
    lockout_minutes = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sysadmin_password_policies"

    def __str__(self):
        return self.name


class SecurityPolicy(models.Model):
    name = models.CharField(max_length=120, unique=True)
    tenant = models.ForeignKey(
        "saas_tenant_management.SchoolTenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="security_policies",
    )
    session_timeout_minutes = models.PositiveIntegerField(default=120)
    allow_remember_me = models.BooleanField(default=True)
    allow_concurrent_sessions = models.BooleanField(default=True)
    require_mfa_for_admins = models.BooleanField(default=False)
    data_retention_days = models.PositiveIntegerField(default=2555)
    backup_frequency = models.CharField(max_length=40, default="DAILY")
    audit_retention_days = models.PositiveIntegerField(default=3650)
    rate_limit_per_minute = models.PositiveIntegerField(default=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sysadmin_security_policies"

    def __str__(self):
        return self.name


class MFADevice(models.Model):
    METHOD_CHOICES = [
        ("OTP", "One-Time Password"),
        ("EMAIL", "Email"),
        ("TOTP", "Authenticator App"),
        ("SMS", "SMS"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="mfa_devices")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    label = models.CharField(max_length=120)
    secret_reference = models.CharField(max_length=255)
    confirmed = models.BooleanField(default=False)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_mfa_devices"
        unique_together = ("user", "label")


class UserSessionRecord(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("TERMINATED", "Terminated"),
        ("EXPIRED", "Expired"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_sessions")
    session_key = models.CharField(max_length=120, unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    device_fingerprint = models.CharField(max_length=255, blank=True, null=True)
    remember_me = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    started_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    terminated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sysadmin_user_sessions"
        ordering = ["-last_seen_at"]


class LoginHistory(models.Model):
    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("LOCKED", "Locked"),
        ("SUSPICIOUS", "Suspicious"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_history")
    username = models.CharField(max_length=150)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    device = models.CharField(max_length=255, blank=True, null=True)
    browser = models.CharField(max_length=255, blank=True, null=True)
    geolocation = models.CharField(max_length=255, blank=True, null=True)
    failure_reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_login_history"
        ordering = ["-created_at"]


class SecurityIncident(models.Model):
    SEVERITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]
    STATUS_CHOICES = [
        ("OPEN", "Open"),
        ("INVESTIGATING", "Investigating"),
        ("RESOLVED", "Resolved"),
        ("DISMISSED", "Dismissed"),
    ]

    incident_number = models.CharField(max_length=50, unique=True)
    tenant = models.ForeignKey(
        "saas_tenant_management.SchoolTenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_incidents",
    )
    incident_type = models.CharField(max_length=80)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="LOW")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OPEN")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_incidents")
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="security_incidents_resolved")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_security_incidents"
        ordering = ["-created_at"]

    def __str__(self):
        return self.incident_number


class SecurityNotification(models.Model):
    NOTIFICATION_CHOICES = [
        ("PASSWORD_RESET", "Password Reset"),
        ("FAILED_LOGIN", "Failed Login"),
        ("NEW_DEVICE", "New Device Login"),
        ("PERMISSION_CHANGE", "Permission Change"),
        ("ACCOUNT_SUSPENSION", "Account Suspension"),
        ("SECURITY_INCIDENT", "Security Incident"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security_notifications")
    notification_type = models.CharField(max_length=40, choices=NOTIFICATION_CHOICES)
    title = models.CharField(max_length=180)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_security_notifications"
        ordering = ["-created_at"]


class APICredential(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("REVOKED", "Revoked"),
        ("EXPIRED", "Expired"),
    ]

    name = models.CharField(max_length=120)
    tenant = models.ForeignKey(
        "saas_tenant_management.SchoolTenant",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="api_credentials",
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_credentials")
    key_prefix = models.CharField(max_length=16)
    key_hash = models.CharField(max_length=128, unique=True)
    permissions = models.JSONField(default=list)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_api_credentials"
        ordering = ["name"]


class FileSecurityRule(models.Model):
    name = models.CharField(max_length=120, unique=True)
    allowed_extensions = models.JSONField(default=list)
    max_file_size_mb = models.PositiveIntegerField(default=10)
    require_secure_download = models.BooleanField(default=True)
    virus_scanning_enabled = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "sysadmin_file_security_rules"


class SystemConfigurationChange(models.Model):
    configuration_area = models.CharField(max_length=120)
    key = models.CharField(max_length=160)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_configuration_changes"
        ordering = ["-changed_at"]


class SystemAdminAuditLog(models.Model):
    action = models.CharField(max_length=120)
    module = models.CharField(max_length=80, default="System Administration")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="system_admin_audit_logs")
    tenant = models.ForeignKey(
        "saas_tenant_management.SchoolTenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="system_admin_audit_logs",
    )
    object_reference = models.CharField(max_length=160, blank=True, null=True)
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "sysadmin_audit_logs"
        ordering = ["-created_at"]
