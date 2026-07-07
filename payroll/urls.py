from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("process/", views.process_payroll, name="process"),
    path("profiles/", views.profile_list, name="profile_list"),
    path("profiles/new/", views.profile_create, name="profile_create"),
    path("profiles/<int:profile_id>/edit/", views.profile_edit, name="profile_edit"),
    path("periods/<int:period_id>/", views.period_detail, name="period_detail"),
    path("periods/<int:period_id>/workflow/", views.period_workflow, name="period_workflow"),
    path("periods/<int:period_id>/bank-export/", views.bank_export, name="bank_export"),
    path("periods/<int:period_id>/payslips/pdf/", views.period_payslips_pdf, name="period_payslips_pdf"),
    path("runs/<int:run_id>/edit/", views.run_edit, name="run_edit"),
    path("runs/<int:run_id>/payslip/", views.payslip, name="payslip"),
    path("runs/<int:run_id>/payslip/pdf/", views.payslip_pdf, name="payslip_pdf"),
    path("<int:run_id>/payslip/", views.payslip, name="legacy_payslip"),
    path("<int:run_id>/payslip/pdf/", views.payslip_pdf, name="legacy_payslip_pdf"),
    path("adjustments/<int:adjustment_id>/delete/", views.adjustment_delete, name="adjustment_delete"),
    path("reports/", views.reports, name="reports"),
]
