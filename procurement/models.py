from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SupplierCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "procurement_supplier_categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Supplier(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("SUSPENDED", "Suspended"),
    ]

    supplier_code = models.CharField(max_length=40, unique=True)
    supplier_name = models.CharField(max_length=180)
    company_registration_number = models.CharField(max_length=80, blank=True, null=True)
    tax_number = models.CharField(max_length=80, blank=True, null=True)
    contact_person = models.CharField(max_length=150, blank=True, null=True)
    mobile_number = models.CharField(max_length=50, blank=True, null=True)
    email_address = models.EmailField(blank=True, null=True)
    physical_address = models.TextField(blank=True, null=True)
    postal_address = models.TextField(blank=True, null=True)
    bank_details = models.TextField(blank=True, null=True)
    payment_terms = models.CharField(max_length=120, default="Due on receipt")
    category = models.ForeignKey(
        SupplierCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="suppliers"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    preferred = models.BooleanField(default=False)
    performance_score = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00")
    )

    class Meta:
        db_table = "procurement_suppliers"
        ordering = ["supplier_name"]

    def __str__(self):
        return f"{self.supplier_code} - {self.supplier_name}"


class ProcurementApprovalRule(models.Model):
    stage = models.CharField(max_length=80)
    minimum_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    maximum_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    required_role = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "procurement_approval_rules"
        ordering = ["minimum_amount", "stage"]


class PurchaseRequisition(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("SUBMITTED", "Submitted"),
        ("DEPARTMENT_APPROVED", "Department Approved"),
        ("FINANCE_VERIFIED", "Finance Verified"),
        ("BUDGET_APPROVED", "Budget Approved"),
        ("ADMIN_APPROVED", "School Administrator Approved"),
        ("REJECTED", "Rejected"),
        ("PO_CREATED", "Purchase Order Created"),
    ]
    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("NORMAL", "Normal"),
        ("HIGH", "High"),
        ("URGENT", "Urgent"),
    ]

    requisition_number = models.CharField(max_length=50, unique=True)
    request_date = models.DateField(auto_now_add=True)
    department = models.CharField(max_length=120)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_requisitions",
    )
    item_description = models.TextField()
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2)
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="NORMAL")
    justification = models.TextField()
    required_date = models.DateField()
    approval_status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="DRAFT")
    budget_checked = models.BooleanField(default=False)
    budget_available = models.BooleanField(default=False)
    budget_override_required = models.BooleanField(default=False)

    class Meta:
        db_table = "procurement_requisitions"
        ordering = ["-request_date", "-id"]

    @property
    def estimated_total(self):
        return (self.quantity * self.estimated_cost).quantize(Decimal("0.01"))

    def __str__(self):
        return self.requisition_number


class ProcurementApproval(models.Model):
    requisition = models.ForeignKey(
        PurchaseRequisition, on_delete=models.CASCADE, related_name="approvals"
    )
    stage = models.CharField(max_length=80)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procurement_approvals",
    )
    status = models.CharField(max_length=20, default="APPROVED")
    comments = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_approvals"
        ordering = ["created_at"]


class SupplierQuotation(models.Model):
    requisition = models.ForeignKey(
        PurchaseRequisition, on_delete=models.CASCADE, related_name="quotations"
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="quotations")
    item = models.CharField(max_length=180)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_period = models.CharField(max_length=120, blank=True, null=True)
    warranty = models.CharField(max_length=120, blank=True, null=True)
    validity_period = models.CharField(max_length=120, blank=True, null=True)
    is_selected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_supplier_quotations"
        ordering = ["total_price"]

    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = (self.unit_price * self.requisition.quantity).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ("ISSUED", "Issued"),
        ("PART_RECEIVED", "Part Received"),
        ("RECEIVED", "Received"),
        ("INVOICED", "Invoiced"),
        ("CLOSED", "Closed"),
        ("CANCELLED", "Cancelled"),
    ]

    purchase_order_number = models.CharField(max_length=50, unique=True)
    requisition = models.OneToOneField(
        PurchaseRequisition, on_delete=models.PROTECT, related_name="purchase_order"
    )
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchase_orders")
    delivery_address = models.TextField()
    delivery_date = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_terms = models.CharField(max_length=120, blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_orders_approved",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ISSUED")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_purchase_orders"
        ordering = ["-created_at"]

    def clean(self):
        super().clean()
        if self.requisition and self.requisition.approval_status != "ADMIN_APPROVED":
            raise ValidationError("Purchase Orders can only be created from approved requisitions.")


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    inventory_item = models.ForeignKey(
        "inventory_management.InventoryItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_order_items",
    )
    description = models.CharField(max_length=180)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "procurement_purchase_order_items"

    def save(self, *args, **kwargs):
        self.total_amount = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class GoodsReceipt(models.Model):
    goods_receipt_number = models.CharField(max_length=50, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts")
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="goods_receipts")
    delivery_date = models.DateField()
    store = models.ForeignKey(
        "inventory_management.Store",
        on_delete=models.PROTECT,
        related_name="goods_receipts",
    )
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    inspection_notes = models.TextField(blank=True, null=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="goods_receipts_recorded",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_goods_receipts"
        ordering = ["-created_at"]


class GoodsReceiptItem(models.Model):
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="items")
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem, on_delete=models.PROTECT, related_name="goods_receipt_items"
    )
    quantity_received = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_rejected = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "procurement_goods_receipt_items"


class SupplierInvoice(models.Model):
    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("MATCHED", "Matched"),
        ("OVERRIDE_APPROVED", "Override Approved"),
        ("APPROVED_FOR_PAYMENT", "Approved for Payment"),
        ("PAID", "Paid"),
    ]

    invoice_number = models.CharField(max_length=80)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="supplier_invoices")
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="supplier_invoices")
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.PROTECT, related_name="supplier_invoices")
    invoice_date = models.DateField()
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="DRAFT")
    override_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_supplier_invoices"
        unique_together = ("supplier", "invoice_number")
        ordering = ["-invoice_date"]


class SupplierPayment(models.Model):
    METHOD_CHOICES = [
        ("BANK_TRANSFER", "Bank Transfer"),
        ("CHEQUE", "Cheque"),
        ("CASH", "Cash"),
        ("MOBILE_MONEY", "Mobile Money"),
    ]

    payment_voucher_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="payments")
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.PROTECT, related_name="payments")
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    bank_account = models.ForeignKey(
        "accounting_erp.BankAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_payments",
    )
    authorised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supplier_payments_authorised",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_supplier_payments"
        ordering = ["-payment_date"]


class Tender(models.Model):
    tender_number = models.CharField(max_length=50, unique=True)
    requisition = models.ForeignKey(PurchaseRequisition, on_delete=models.PROTECT, related_name="tenders")
    title = models.CharField(max_length=180)
    closing_date = models.DateField()
    status = models.CharField(max_length=30, default="OPEN")

    class Meta:
        db_table = "procurement_tenders"


class SupplierContract(models.Model):
    contract_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="contracts")
    start_date = models.DateField()
    end_date = models.DateField()
    renewal_reminder_date = models.DateField()
    contract_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=30, default="ACTIVE")

    class Meta:
        db_table = "procurement_supplier_contracts"


class ProcurementAuditLog(models.Model):
    module = models.CharField(max_length=80, default="Procurement")
    action = models.CharField(max_length=120)
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    previous_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "procurement_audit_logs"
        ordering = ["-created_at"]
