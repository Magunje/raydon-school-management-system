from django.urls import path
from discipline import views

app_name = "discipline"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("incidents/", views.incident_list, name="incident_list"),
    path("incidents/new/", views.incident_new, name="incident_new"),
    path("incidents/<int:incident_id>/sanction/new/", views.sanction_new, name="sanction_new"),
    path("parent-meetings/new/", views.parent_meeting_new, name="parent_meeting_new"),
    path("behaviour-plans/new/", views.behaviour_plan_new, name="behaviour_plan_new"),
    path("reports/", views.reports_view, name="reports"),
    path("reports/export/csv/", views.export_discipline_csv, name="export_csv"),
]
