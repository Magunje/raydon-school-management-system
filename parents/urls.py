from django.urls import path

from . import views

app_name = "parents"

urlpatterns = [
    path("", views.parents, name="parents"),
    path("new/", views.new, name="new"),
    path("<int:guardian_id>/", views.detail, name="detail"),
    path("<int:guardian_id>/edit/", views.edit, name="edit"),
    path("<int:guardian_id>/delete/", views.delete, name="delete"),
    path("portal/", views.portal, name="portal"),
]
