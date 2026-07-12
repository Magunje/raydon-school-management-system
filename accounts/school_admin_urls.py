from django.urls import path

from . import views

app_name = "school_admin"

urlpatterns = [
    path("staff/login", views.login_view, name="login"),
    path("logout", views.logout_view, name="logout"),
    path("dashboard", views.dashboard, name="dashboard"),
]
