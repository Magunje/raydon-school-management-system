from django.urls import path

from . import views

app_name = "staff_portal"

urlpatterns = [
    path("login", views.portal_login, name="login"),
    path("logout", views.portal_logout, name="logout"),
    path("", views.portal, name="dashboard"),
    path("profile", views.portal_profile, name="profile"),
    path("api/<str:module>", views.portal_api, name="api"),
]
