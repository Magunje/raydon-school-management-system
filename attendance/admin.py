from django.contrib import admin

from .models import AttendanceRecord


class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("pupil_id", "class_id", "attendance_date", "status", "marked_by")
    list_filter = ("status", "attendance_date")
    search_fields = ("pupil_id",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(AttendanceRecord, AttendanceRecordAdmin)

# Register your models here.
