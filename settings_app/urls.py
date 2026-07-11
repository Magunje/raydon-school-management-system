from django.urls import path

from . import views

app_name = "settings_app"

urlpatterns = [
    path("", views.settings, name="settings"),
    path("audit/", views.audit, name="audit"),
    path("audit/<int:audit_id>/", views.audit_detail, name="audit_detail"),
    path("backups/", views.backups, name="backups"),
    path("backups/create/", views.create_backup, name="create_backup"),
    path("backups/<int:backup_id>/download/", views.download_backup, name="download_backup"),
    path("offline-sync/", views.offline_sync, name="offline_sync"),
    path("offline-sync/<int:event_id>/retry/", views.retry_sync, name="retry_sync"),
]
