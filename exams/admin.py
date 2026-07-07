from django.contrib import admin

from .models import ExamSession, ResultEntry, ResultSheet


class ReadOnlyLegacyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(ExamSession, ReadOnlyLegacyAdmin)
admin.site.register(ResultSheet, ReadOnlyLegacyAdmin)
admin.site.register(ResultEntry, ReadOnlyLegacyAdmin)

# Register your models here.
