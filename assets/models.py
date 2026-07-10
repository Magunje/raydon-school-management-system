from django.db import models
from decimal import Decimal


class AssetCategory(models.Model):
    category_id = models.BigAutoField(primary_key=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "asset_categories"
        verbose_name_plural = "Asset Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Asset(models.Model):
    DEPRECIATION_METHODS = [
        ("Straight-Line", "Straight-Line"),
        ("Reducing Balance", "Reducing Balance"),
        ("None", "None"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("In Use", "In Use"),
        ("In Storage", "In Storage"),
        ("Under Maintenance", "Under Maintenance"),
        ("Damaged", "Damaged"),
        ("Lost", "Lost"),
        ("Disposed", "Disposed"),
        ("Written Off", "Written Off"),
        ("Stolen", "Stolen"),
    ]

    asset_id = models.BigAutoField(primary_key=True)
    asset_code = models.CharField(max_length=50, unique=True)
    asset_name = models.CharField(max_length=150)
    category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE, related_name="assets")
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    qr_code = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    acquisition_date = models.DateField()
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    supplier = models.CharField(max_length=150, blank=True, null=True)
    warranty_start = models.DateField(blank=True, null=True)
    warranty_end = models.DateField(blank=True, null=True)
    useful_life = models.IntegerField(help_text="Useful life in years", default=5)
    depreciation_method = models.CharField(max_length=30, choices=DEPRECIATION_METHODS, default="Straight-Line")
    depreciation_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0.00"), help_text="e.g. 15.00 for 15%")
    salvage_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    current_value = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Active")
    location_name = models.CharField(max_length=150, blank=True, null=True)
    custodian = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="custodian_assets",
    )

    class Meta:
        db_table = "asset_register"
        ordering = ["asset_code"]

    def __str__(self):
        return f"{self.asset_code} - {self.asset_name}"


class AssetAssignment(models.Model):
    assignment_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="assignments")
    assigned_employee = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_assets",
    )
    assigned_department = models.CharField(max_length=120, blank=True, null=True)
    assigned_location = models.CharField(max_length=150, blank=True, null=True)
    date_assigned = models.DateField()
    condition = models.CharField(max_length=50, default="Good")
    approved_by = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="approved_asset_assignments",
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "asset_assignments"
        ordering = ["-date_assigned"]


class AssetTransfer(models.Model):
    transfer_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="transfers")
    previous_location = models.CharField(max_length=150)
    new_location = models.CharField(max_length=150)
    transfer_date = models.DateField()
    approved_by = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="approved_asset_transfers",
    )
    reason = models.TextField()

    class Meta:
        db_table = "asset_transfers"
        ordering = ["-transfer_date"]


class AssetMaintenance(models.Model):
    TYPE_CHOICES = [
        ("Preventive", "Preventive"),
        ("Corrective", "Corrective"),
        ("Emergency", "Emergency"),
    ]

    maintenance_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance_logs")
    maintenance_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    maintenance_date = models.DateField()
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    provider = models.CharField(max_length=150)
    notes = models.TextField(blank=True, null=True)
    next_service_date = models.DateField(blank=True, null=True)

    class Meta:
        db_table = "asset_maintenance"
        ordering = ["-maintenance_date"]


class AssetDepreciationLog(models.Model):
    log_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="depreciation_logs")
    depreciation_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    book_value = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "asset_depreciation_logs"
        ordering = ["-depreciation_date"]


class AssetDisposal(models.Model):
    METHOD_CHOICES = [
        ("Sale", "Sale"),
        ("Donation", "Donation"),
        ("Write-Off", "Write-Off"),
        ("Scrap", "Scrap"),
        ("Loss", "Loss"),
        ("Theft", "Theft"),
    ]

    disposal_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="disposals")
    disposal_date = models.DateField()
    method = models.CharField(max_length=30, choices=METHOD_CHOICES)
    value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    reason = models.TextField()
    approved_by = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="approved_asset_disposals",
    )

    class Meta:
        db_table = "asset_disposals"


class AssetVerification(models.Model):
    STATUS_CHOICES = [
        ("Present", "Present"),
        ("Missing", "Missing"),
        ("Damaged", "Damaged"),
    ]

    verification_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="verifications")
    verification_date = models.DateField()
    verified_by = models.ForeignKey(
        "human_resources.EmployeeProfile",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    status_found = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Present")
    variance_notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "asset_verifications"
        ordering = ["-verification_date"]


class AssetInsurance(models.Model):
    insurance_id = models.BigAutoField(primary_key=True)
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="insurance_policies")
    policy_number = models.CharField(max_length=100)
    company = models.CharField(max_length=150)
    start_date = models.DateField()
    end_date = models.DateField()
    insured_value = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        db_table = "asset_insurance_policies"
        ordering = ["-end_date"]
