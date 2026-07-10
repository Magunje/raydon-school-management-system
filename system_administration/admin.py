from django.contrib import admin

from .models import (
    APICredential,
    CustomRole,
    FileSecurityRule,
    LoginHistory,
    MFADevice,
    PasswordPolicy,
    PermissionDefinition,
    RolePermission,
    SecurityIncident,
    SecurityNotification,
    SecurityPolicy,
    SystemAdminAuditLog,
    SystemConfigurationChange,
    UserSecurityProfile,
    UserSessionRecord,
)


@admin.register(CustomRole)
class CustomRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "scope", "tenant", "is_system_role", "is_active")
    list_filter = ("scope", "is_system_role", "is_active")
    search_fields = ("name", "code")


@admin.register(PermissionDefinition)
class PermissionDefinitionAdmin(admin.ModelAdmin):
    list_display = ("code", "module_code", "level", "action", "is_active")
    list_filter = ("module_code", "level", "action", "is_active")
    search_fields = ("code", "name")


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ("role", "permission", "granted", "assigned_by", "assigned_at")
    list_filter = ("granted",)


@admin.register(UserSecurityProfile)
class UserSecurityProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "email_address", "status", "mfa_enabled", "failed_login_count", "locked_until")
    list_filter = ("status", "mfa_enabled")
    search_fields = ("user__username", "full_name", "email_address", "phone_number")


@admin.register(PasswordPolicy)
class PasswordPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "minimum_length", "password_expiry_days", "max_failed_attempts", "is_active")
    list_filter = ("is_active",)


@admin.register(SecurityPolicy)
class SecurityPolicyAdmin(admin.ModelAdmin):
    list_display = ("name", "session_timeout_minutes", "allow_concurrent_sessions", "require_mfa_for_admins", "is_active")
    list_filter = ("is_active", "require_mfa_for_admins")


@admin.register(MFADevice)
class MFADeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "method", "label", "confirmed", "last_used_at")
    list_filter = ("method", "confirmed")


@admin.register(UserSessionRecord)
class UserSessionRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "session_key", "status", "ip_address", "remember_me", "last_seen_at")
    list_filter = ("status", "remember_me")
    search_fields = ("user__username", "session_key", "device_fingerprint")


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ("username", "user", "status", "ip_address", "device", "created_at")
    list_filter = ("status",)
    search_fields = ("username", "ip_address", "device")


@admin.register(SecurityIncident)
class SecurityIncidentAdmin(admin.ModelAdmin):
    list_display = ("incident_number", "incident_type", "severity", "status", "user", "created_at")
    list_filter = ("severity", "status", "incident_type")
    search_fields = ("incident_number", "description", "user__username")


@admin.register(SecurityNotification)
class SecurityNotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "notification_type", "title", "is_read", "created_at")
    list_filter = ("notification_type", "is_read")


@admin.register(APICredential)
class APICredentialAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "tenant", "key_prefix", "status", "rate_limit_per_minute", "expires_at")
    list_filter = ("status",)
    search_fields = ("name", "owner__username", "key_prefix")


@admin.register(FileSecurityRule)
class FileSecurityRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "max_file_size_mb", "require_secure_download", "virus_scanning_enabled", "is_active")
    list_filter = ("require_secure_download", "virus_scanning_enabled", "is_active")


@admin.register(SystemConfigurationChange)
class SystemConfigurationChangeAdmin(admin.ModelAdmin):
    list_display = ("configuration_area", "key", "changed_by", "changed_at")
    search_fields = ("configuration_area", "key", "reason")


@admin.register(SystemAdminAuditLog)
class SystemAdminAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "module", "user", "tenant", "object_reference", "created_at")
    list_filter = ("module", "action")
    search_fields = ("action", "object_reference", "reason")
