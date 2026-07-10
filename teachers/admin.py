from django.contrib import admin

from .models import TeacherAttendanceRecord, TeacherEmployeeProfile, TeacherProfile


class ReadOnlyLegacyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(TeacherProfile, ReadOnlyLegacyAdmin)
admin.site.register(TeacherAttendanceRecord, ReadOnlyLegacyAdmin)
admin.site.register(TeacherEmployeeProfile)

# Register your models here.
