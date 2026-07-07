from django.contrib import admin

from .models import AuditLog, DatabaseBackupLog, SchoolSettings


class ReadOnlyLegacyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(SchoolSettings, ReadOnlyLegacyAdmin)
admin.site.register(AuditLog, ReadOnlyLegacyAdmin)
admin.site.register(DatabaseBackupLog, ReadOnlyLegacyAdmin)

# Register your models here.
