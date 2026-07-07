from django.urls import path

from . import views

app_name = "staff"

urlpatterns = [
    path("", views.staff, name="staff"),
    path("attendance/", views.attendance, name="attendance"),
    path("attendance/new/", views.attendance_new, name="attendance_new"),
    path("attendance/<int:attendance_id>/edit/", views.attendance_edit, name="attendance_edit"),
    path("attendance/<int:attendance_id>/delete/", views.attendance_delete, name="attendance_delete"),
    path("portal/", views.portal, name="portal"),
    path("portal/profile/", views.portal_profile, name="portal_profile"),
    path("portal/api/<str:module>/", views.portal_api, name="portal_api"),
]
