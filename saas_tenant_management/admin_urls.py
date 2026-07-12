from django.urls import path

from accounts import views as account_views

app_name = "saas_admin"

urlpatterns = [
    path("", account_views.dashboard, name="dashboard"),
]
