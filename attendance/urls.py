from django.urls import path

from . import views

app_name = "attendance"

urlpatterns = [
    path("", views.student_attendance, name="student_attendance"),
    path("register/", views.class_attendance_register, name="class_attendance_register"),
    path("new/", views.new, name="new"),
    path("<int:attendance_id>/edit/", views.edit, name="edit"),
    path("<int:attendance_id>/delete/", views.delete, name="delete"),
    path("monthly/", views.monthly, name="monthly"),
]
