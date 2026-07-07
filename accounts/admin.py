from django.contrib import admin

from .models import LegacyUser, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_name", "role", "status", "legacy_user_id")
    list_filter = ("role", "status")
    search_fields = ("user__username", "full_name", "role")


@admin.register(LegacyUser)
class LegacyUserAdmin(admin.ModelAdmin):
    list_display = ("admission_no", "username", "full_name", "role", "status")
    list_filter = ("role", "status")
    search_fields = ("admission_no", "username", "full_name")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

# Register your models here.
