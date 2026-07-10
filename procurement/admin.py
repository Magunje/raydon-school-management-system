from django.contrib import admin

from procurement.models import (
    GoodsReceipt,
    GoodsReceiptItem,
    ProcurementApproval,
    ProcurementApprovalRule,
    ProcurementAuditLog,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequisition,
    Supplier,
    SupplierCategory,
    SupplierContract,
    SupplierInvoice,
    SupplierPayment,
    SupplierQuotation,
    Tender,
)


admin.site.register(SupplierCategory)
admin.site.register(Supplier)
admin.site.register(ProcurementApprovalRule)
admin.site.register(PurchaseRequisition)
admin.site.register(ProcurementApproval)
admin.site.register(SupplierQuotation)
admin.site.register(PurchaseOrder)
admin.site.register(PurchaseOrderItem)
admin.site.register(GoodsReceipt)
admin.site.register(GoodsReceiptItem)
admin.site.register(SupplierInvoice)
admin.site.register(SupplierPayment)
admin.site.register(Tender)
admin.site.register(SupplierContract)
admin.site.register(ProcurementAuditLog)
