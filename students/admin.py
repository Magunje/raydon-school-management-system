from django.contrib import admin

from .models import Grade, Guardian, Pupil, SchoolClass


class ReadOnlyLegacyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Pupil)
class PupilAdmin(ReadOnlyLegacyAdmin):
    list_display = ("admission_no", "first_name", "surname", "grade", "class_stream", "status")
    list_filter = ("grade", "class_stream", "status")
    search_fields = ("admission_no", "first_name", "surname", "guardian_name")


admin.site.register(Guardian, ReadOnlyLegacyAdmin)
admin.site.register(Grade, ReadOnlyLegacyAdmin)
admin.site.register(SchoolClass, ReadOnlyLegacyAdmin)

# Register your models here.
