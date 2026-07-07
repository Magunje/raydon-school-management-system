from django.urls import path

from . import views

app_name = "fees"

urlpatterns = [
    path("structure/", views.structure, name="structure"),
    path("structure/generate-bills/", views.generate_term_bills, name="generate_term_bills"),
    path("structure/new/", views.structure_new, name="structure_new"),
    path("structure/<int:fee_id>/", views.structure_detail, name="structure_detail"),
    path("structure/<int:fee_id>/edit/", views.structure_edit, name="structure_edit"),
    path("structure/<int:fee_id>/delete/", views.structure_delete, name="structure_delete"),
    path("payments/", views.payments, name="payments"),
    path("payments/new/", views.record_payment, name="record_payment"),
    path("payments/<str:receipt_no>/edit/", views.payment_edit, name="payment_edit_by_receipt"),
    path("payments/<str:receipt_no>/delete/", views.payment_delete, name="payment_delete_by_receipt"),
    path("payments/<int:payment_id>/", views.payment_detail, name="payment_detail"),
    path("payments/<int:payment_id>/edit/", views.payment_edit, name="payment_edit"),
    path("payments/<int:payment_id>/delete/", views.payment_delete, name="payment_delete"),
    path("receipt/<str:receipt_no>/", views.receipt, name="receipt_by_number"),
    path("receipt/<str:receipt_no>/pdf/", views.receipt, name="receipt_pdf_by_number"),
    path("receipt/<int:payment_id>/", views.receipt, name="receipt"),
    path("receipt/<int:payment_id>/pdf/", views.receipt, name="receipt_pdf"),
    path("receipt/admission/<str:admission_no>/", views.receipt, name="receipt_by_admission_no"),
    path("portal-requests/", views.portal_requests, name="portal_requests"),
    path("portal-requests/<int:request_id>/", views.portal_request_detail, name="portal_request_detail"),
    path("portal-requests/<int:request_id>/edit/", views.portal_request_edit, name="portal_request_edit"),
    path("portal-requests/<int:request_id>/delete/", views.portal_request_delete, name="portal_request_delete"),
    path("portal-requests/<int:request_id>/<str:action>/", views.portal_request_action, name="portal_request_action"),
]

