from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notifications, name="notifications"),
    path("<int:communication_id>/", views.detail, name="detail"),
    path("announcements/", views.announcements, name="announcements"),
    path("announcements/new/", views.announcement_new, name="announcement_new"),
    path("announcements/<int:announcement_id>/delete/", views.announcement_delete, name="announcement_delete"),
]
