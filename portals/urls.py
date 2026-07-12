from django.urls import path

from . import views

app_name = "student_portal"

urlpatterns = [
    path("login", views.student_login, name="login"),
    path("logout", views.student_logout, name="logout"),
    path("", views.student, name="dashboard"),
    path("profile", views.student_profile, name="profile"),
    path("attendance", views.student_attendance, name="attendance"),
    path("pay", views.student_pay, name="pay"),
    path("statement", views.student_statement, name="statement"),
    path("statement/pdf", views.student_statement, name="statement_pdf"),
    path("textbooks", views.student_textbooks, name="textbooks"),
    path("timetable", views.student_timetable, name="timetable"),
    path("e-learning", views.student_e_learning, name="e_learning"),
    path("e-learning/submit/<int:assignment_id>", views.student_submit_assignment, name="submit_assignment"),
    path("results", views.student_results, name="results"),
    path("results/pdf", views.student_results, name="results_pdf"),
    path("api/updates", views.student_updates, name="updates"),
    path("api/<str:module>", views.student_api, name="module_api"),
    path("receipt/<str:receipt_no>", views.student_receipt, name="receipt_by_number"),
    path("receipt/<str:receipt_no>/pdf", views.student_receipt, name="receipt_pdf_by_number"),
    path("receipt/<int:payment_id>", views.student_receipt, name="receipt"),
    path("receipt/<int:payment_id>/pdf", views.student_receipt, name="receipt_pdf"),
    path("payment/<str:reference_no>", views.student_pay, name="payment_status"),
    path("payment/<str:reference_no>/poll", views.student_pay, name="payment_poll"),
    path("payment/<str:reference_no>/return", views.student_pay, name="payment_return"),
]
