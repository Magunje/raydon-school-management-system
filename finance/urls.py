from django.urls import path

from . import views

app_name = "finance"

urlpatterns = [
    path("", views.payments, name="payments"),
    path("record-payment/", views.record_payment, name="record_payment"),
    path("fees-structure/", views.fees_structure, name="fees_structure"),
    path("master-receipts/", views.master_receipts, name="master_receipts"),
    path("master-receipts/new/", views.master_receipt_new, name="master_receipt_new"),
    path("master-receipts/<int:master_receipt_id>/", views.master_receipt_detail, name="master_receipt_detail"),
    path("master-receipts/<int:master_receipt_id>/pdf/", views.master_receipt_detail, name="master_receipt_pdf"),
    path("expenses/", views.expenses, name="expenses"),
    path("expenses/new/", views.record_expense, name="record_expense"),
    path("expenses/<int:expense_id>/", views.expense_detail, name="expense_detail"),
    path("expenses/<int:expense_id>/edit/", views.expense_edit, name="expense_edit"),
    path("expenses/<int:expense_id>/delete/", views.expense_delete, name="expense_delete"),
    path("inventory/", views.inventory, name="inventory"),
    path("inventory/new/", views.inventory_new, name="inventory_new"),
    path("inventory/<int:item_id>/", views.inventory_detail, name="inventory_detail"),
    path("inventory/<int:item_id>/edit/", views.inventory_edit, name="inventory_edit"),
    path("inventory/<int:item_id>/delete/", views.inventory_delete, name="inventory_delete"),
    path("pos/", views.pos, name="pos"),
    path("pos/new/", views.pos_new, name="pos_new"),
    path("pos/<int:sale_id>/edit/", views.pos_edit, name="pos_edit"),
    path("pos/receipt/<int:sale_id>/", views.pos_receipt, name="pos_receipt"),
    path("pos/receipt/<int:sale_id>/pdf/", views.pos_receipt, name="pos_receipt_pdf"),
]
