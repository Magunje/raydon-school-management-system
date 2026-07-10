from django.urls import path
from counselling import views

app_name = "counselling"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cases/", views.case_list, name="case_list"),
    path("cases/new/", views.case_new, name="case_new"),
    path("cases/<int:case_id>/", views.case_detail, name="case_detail"),
    path("cases/<int:case_id>/session/new/", views.session_new, name="session_new"),
    path("cases/<int:case_id>/intervention/new/", views.intervention_new, name="intervention_new"),
    path("appointments/new/", views.appointment_new, name="appointment_new"),
    path("career-guidance/new/", views.career_session_new, name="career_session_new"),
    path("reports/", views.reports_view, name="reports"),
    path("reports/export/csv/", views.export_cases_csv, name="export_csv"),
]
