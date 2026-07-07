from django.contrib import admin

from .models import ClassTimetableEntry, ELearningAssignment, ELearningNote, ELearningSubmission, Subject


class ReadOnlyLegacyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Subject, ReadOnlyLegacyAdmin)
admin.site.register(ClassTimetableEntry, ReadOnlyLegacyAdmin)
admin.site.register(ELearningNote, ReadOnlyLegacyAdmin)
admin.site.register(ELearningAssignment, ReadOnlyLegacyAdmin)
admin.site.register(ELearningSubmission, ReadOnlyLegacyAdmin)

# Register your models here.
