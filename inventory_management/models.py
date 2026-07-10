from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class InventoryCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "inventory_mgt_categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Store(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
    ]

    store_code = models.CharField(max_length=30, unique=True)
    store_name = models.CharField(max_length=150)
    storekeeper = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stores_managed",
    )
    location = models.CharField(max_length=180, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")

    class Meta:
        db_table = "inventory_mgt_stores"
        ordering = ["store_name"]

    def __str__(self):
        return f"{self.store_code} - {self.store_name}"


class InventoryItem(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("DISCONTINUED", "Discontinued"),
    ]
    VALUATION_CHOICES = [
        ("FIFO", "FIFO"),
        ("WEIGHTED_AVERAGE", "Weighted Average Cost"),
    ]

    item_code = models.CharField(max_length=50, unique=True)
    item_name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(
        InventoryCategory, on_delete=models.PROTECT, related_name="items"
    )
    unit_of_measure = models.CharField(max_length=40, default="Each")
    minimum_stock_level = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    maximum_stock_level = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    reorder_level = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    purchase_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    selling_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    current_quantity = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    default_store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_items",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    valuation_method = models.CharField(
        max_length=30, choices=VALUATION_CHOICES, default="WEIGHTED_AVERAGE"
    )
    barcode = models.CharField(max_length=120, blank=True, null=True, unique=True)
    qr_code = models.CharField(max_length=120, blank=True, null=True, unique=True)
    is_capital_asset = models.BooleanField(default=False)

    class Meta:
        db_table = "inventory_mgt_items"
        ordering = ["item_code"]

    def __str__(self):
        return f"{self.item_code} - {self.item_name}"

    def clean(self):
        super().clean()
        if self.current_quantity < Decimal("0.00"):
            raise ValidationError("Negative stock is prohibited.")


class StoreStock(models.Model):
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="stock")
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="store_stock")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    class Meta:
        db_table = "inventory_mgt_store_stock"
        unique_together = ("store", "item")

    def clean(self):
        super().clean()
        if self.quantity < Decimal("0.00"):
            raise ValidationError("Negative store stock is prohibited.")


class StockBatch(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="batches")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="batches")
    batch_number = models.CharField(max_length=80, blank=True, null=True)
    serial_number = models.CharField(max_length=120, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_mgt_stock_batches"
        ordering = ["expiry_date", "received_at"]


class StockMovement(models.Model):
    MOVEMENT_CHOICES = [
        ("RECEIPT", "Receipt"),
        ("ISSUE", "Issue"),
        ("TRANSFER_OUT", "Transfer Out"),
        ("TRANSFER_IN", "Transfer In"),
        ("ADJUSTMENT", "Adjustment"),
        ("COUNT_VARIANCE", "Stock Count Variance"),
        ("WRITE_OFF", "Write-Off"),
    ]

    movement_number = models.CharField(max_length=50, unique=True)
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_CHOICES)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="movements")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reference_number = models.CharField(max_length=120, blank=True, null=True)
    department = models.CharField(max_length=120, blank=True, null=True)
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements_issued",
    )
    received_by = models.CharField(max_length=150, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_mgt_stock_movements"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.total_cost = (self.quantity * self.unit_cost).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class StockTransfer(models.Model):
    transfer_number = models.CharField(max_length=50, unique=True)
    source_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="transfers_out")
    destination_store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="transfers_in")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="transfers")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_transfers_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_mgt_stock_transfers"
        ordering = ["-created_at"]


class StockAdjustment(models.Model):
    ADJUSTMENT_CHOICES = [
        ("DAMAGED", "Damaged Stock"),
        ("LOST", "Lost Stock"),
        ("EXPIRED", "Expired Stock"),
        ("CORRECTION", "Stock Correction"),
        ("WRITE_OFF", "Inventory Write-Off"),
    ]

    adjustment_number = models.CharField(max_length=50, unique=True)
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="adjustments")
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="adjustments")
    adjustment_type = models.CharField(max_length=30, choices=ADJUSTMENT_CHOICES)
    quantity_delta = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    supporting_notes = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="stock_adjustments_approved",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_mgt_stock_adjustments"
        ordering = ["-created_at"]


class StockCount(models.Model):
    COUNT_CHOICES = [
        ("ANNUAL", "Annual Stock Take"),
        ("PERIODIC", "Periodic Stock Count"),
        ("CYCLE", "Cycle Count"),
        ("SPOT", "Spot Check"),
    ]

    count_number = models.CharField(max_length=50, unique=True)
    store = models.ForeignKey(Store, on_delete=models.PROTECT, related_name="stock_counts")
    count_type = models.CharField(max_length=20, choices=COUNT_CHOICES)
    counted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_counts_performed",
    )
    status = models.CharField(max_length=20, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_mgt_stock_counts"
        ordering = ["-created_at"]


class StockCountLine(models.Model):
    stock_count = models.ForeignKey(StockCount, on_delete=models.CASCADE, related_name="lines")
    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT)
    system_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    counted_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    variance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    adjustment_recommended = models.BooleanField(default=False)

    class Meta:
        db_table = "inventory_mgt_stock_count_lines"

    def save(self, *args, **kwargs):
        self.variance = self.counted_quantity - self.system_quantity
        self.adjustment_recommended = self.variance != Decimal("0.00")
        super().save(*args, **kwargs)


class ReorderAlert(models.Model):
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name="reorder_alerts")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="reorder_alerts")
    current_quantity = models.DecimalField(max_digits=12, decimal_places=2)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2)
    purchase_recommendation = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=20, default="OPEN")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "inventory_mgt_reorder_alerts"
        ordering = ["-created_at"]


class InventoryAuditLog(models.Model):
    module = models.CharField(max_length=80, default="Inventory")
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
        db_table = "inventory_mgt_audit_logs"
        ordering = ["-created_at"]
