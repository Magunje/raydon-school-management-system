from django.urls import path

from . import views

app_name = "teachers"

urlpatterns = [
    path("", views.profiles, name="profiles"),
    path("new/", views.new, name="new"),
    path("<int:profile_id>/", views.detail, name="detail"),
    path("<int:profile_id>/edit/", views.edit, name="edit"),
    path("<int:profile_id>/delete/", views.delete, name="delete"),
    path("attendance/", views.attendance, name="attendance"),
    path("attendance/new/", views.attendance_new, name="attendance_new"),
    path("attendance/<int:attendance_id>/edit/", views.attendance_edit, name="attendance_edit"),
    path("attendance/<int:attendance_id>/delete/", views.attendance_delete, name="attendance_delete"),
]
