from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    path("", views.setup, name="setup"),
    path("new/", views.exam_new, name="exam_new"),
    path("<int:exam_id>/", views.exam_detail, name="exam_detail"),
    path("<int:exam_id>/edit/", views.exam_edit, name="exam_edit"),
    path("<int:exam_id>/delete/", views.exam_delete, name="exam_delete"),
    path("results/", views.results, name="results"),
    path("results/new/", views.result_new, name="result_new"),
    path("results/class-entry/", views.result_class_entry, name="result_class_entry"),
    path("results/bulk-publish/", views.result_bulk_publish, name="result_bulk_publish"),
    path("results/export/pdf/", views.results_export_pdf, name="results_export_pdf"),
    path("results/<int:result_id>/", views.result_detail, name="result_detail"),
    path("results/<int:result_id>/pdf/", views.result_detail, name="result_pdf"),
    path("results/<int:result_id>/edit/", views.result_edit, name="result_edit"),
    path("results/<int:result_id>/delete/", views.result_delete, name="result_delete"),
    path("results/<int:result_id>/publish/", views.result_publish, name="result_publish"),
    path("results/verify/<int:result_id>/", views.results_verify, name="results_verify"),
    path("predictions/", views.predictions, name="predictions"),
]
