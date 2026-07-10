from django.conf import settings
from django.db import models


class DashboardDefinition(models.Model):
    CATEGORY_CHOICES = [
        ("EXECUTIVE", "Executive Dashboard"),
        ("ACADEMIC", "Academic Dashboard"),
        ("FINANCIAL", "Financial Dashboard"),
        ("HUMAN_RESOURCES", "Human Resources Dashboard"),
        ("STUDENT", "Student Dashboard"),
        ("PARENT", "Parent Dashboard"),
        ("LIBRARY", "Library Dashboard"),
        ("HOSTEL", "Hostel Dashboard"),
        ("TRANSPORT", "Transport Dashboard"),
        ("MEDICAL", "Medical Dashboard"),
        ("SAAS", "SaaS Administration Dashboard"),
    ]

    name = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True, null=True)
    permission_code = models.CharField(max_length=120, default="reports.view")
    refresh_interval_minutes = models.PositiveIntegerField(default=15)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bi_dashboard_definitions"
        unique_together = ("name", "category")
        ordering = ["category", "name"]

    def __str__(self):
        return self.name


class DashboardWidget(models.Model):
    WIDGET_CHOICES = [
        ("KPI_CARD", "KPI Card"),
        ("BAR_CHART", "Bar Chart"),
        ("PIE_CHART", "Pie Chart"),
        ("LINE_GRAPH", "Line Graph"),
        ("AREA_CHART", "Area Chart"),
        ("HEAT_MAP", "Heat Map"),
        ("TABLE", "Table"),
    ]

    dashboard = models.ForeignKey(DashboardDefinition, on_delete=models.CASCADE, related_name="widgets")
    title = models.CharField(max_length=150)
    widget_type = models.CharField(max_length=30, choices=WIDGET_CHOICES)
    metric_code = models.CharField(max_length=120)
    data_source = models.CharField(max_length=120)
    configuration = models.JSONField(default=dict)
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_dashboard_widgets"
        ordering = ["dashboard", "display_order", "title"]

    def __str__(self):
        return self.title


class ReportTemplate(models.Model):
    FORMAT_CHOICES = [
        ("PDF", "PDF"),
        ("EXCEL", "Excel"),
        ("CSV", "CSV"),
        ("WORD", "Word"),
    ]

    name = models.CharField(max_length=150)
    module_code = models.CharField(max_length=80)
    description = models.TextField(blank=True, null=True)
    fields = models.JSONField(default=list)
    filters = models.JSONField(default=dict)
    default_format = models.CharField(max_length=20, choices=FORMAT_CHOICES, default="PDF")
    permission_code = models.CharField(max_length=120, default="reports.view")
    is_system_template = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bi_report_templates"
        unique_together = ("module_code", "name")
        ordering = ["module_code", "name"]

    def __str__(self):
        return self.name


class SavedReport(models.Model):
    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name="saved_reports")
    name = models.CharField(max_length=150)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_bi_reports")
    filters = models.JSONField(default=dict)
    output_format = models.CharField(max_length=20, choices=ReportTemplate.FORMAT_CHOICES, default="PDF")
    is_shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bi_saved_reports"
        unique_together = ("owner", "name")
        ordering = ["name"]

    def __str__(self):
        return self.name


class ScheduledReport(models.Model):
    FREQUENCY_CHOICES = [
        ("DAILY", "Daily"),
        ("WEEKLY", "Weekly"),
        ("MONTHLY", "Monthly"),
        ("QUARTERLY", "Quarterly"),
        ("ANNUALLY", "Annually"),
    ]
    DELIVERY_CHOICES = [
        ("NOTIFICATION", "System Notification"),
        ("EMAIL", "Email"),
        ("DOWNLOAD_CENTRE", "Download Centre"),
    ]

    saved_report = models.ForeignKey(SavedReport, on_delete=models.CASCADE, related_name="schedules")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    delivery_method = models.CharField(max_length=30, choices=DELIVERY_CHOICES, default="DOWNLOAD_CENTRE")
    next_run_at = models.DateTimeField()
    last_run_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bi_scheduled_reports"
        ordering = ["next_run_at"]


class ReportExecutionLog(models.Model):
    STATUS_CHOICES = [
        ("QUEUED", "Queued"),
        ("RUNNING", "Running"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    ]

    report_template = models.ForeignKey(ReportTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="execution_logs")
    saved_report = models.ForeignKey(SavedReport, on_delete=models.SET_NULL, null=True, blank=True, related_name="execution_logs")
    executed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    parameters = models.JSONField(default=dict)
    result_summary = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="QUEUED")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "bi_report_execution_logs"
        ordering = ["-started_at"]


class ReportExport(models.Model):
    execution = models.ForeignKey(ReportExecutionLog, on_delete=models.CASCADE, related_name="exports")
    export_format = models.CharField(max_length=20, choices=ReportTemplate.FORMAT_CHOICES)
    file_name = models.CharField(max_length=180)
    file_path = models.CharField(max_length=255, blank=True, null=True)
    file_size = models.PositiveIntegerField(default=0)
    exported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    exported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bi_report_exports"
        ordering = ["-exported_at"]


class KPIDefinition(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=120, unique=True)
    module_code = models.CharField(max_length=80)
    formula = models.TextField()
    target_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    alert_threshold = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_kpi_definitions"
        ordering = ["module_code", "name"]

    def __str__(self):
        return self.name


class KPISnapshot(models.Model):
    kpi = models.ForeignKey(KPIDefinition, on_delete=models.CASCADE, related_name="snapshots")
    snapshot_date = models.DateField()
    value = models.DecimalField(max_digits=14, decimal_places=2)
    target_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=30, default="ON_TRACK")
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "bi_kpi_snapshots"
        unique_together = ("kpi", "snapshot_date")
        ordering = ["-snapshot_date"]


class AnalyticsSnapshot(models.Model):
    CATEGORY_CHOICES = DashboardDefinition.CATEGORY_CHOICES

    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    snapshot_date = models.DateField()
    metrics = models.JSONField(default=dict)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bi_analytics_snapshots"
        unique_together = ("category", "snapshot_date")
        ordering = ["-snapshot_date", "category"]


class PredictiveInsight(models.Model):
    INSIGHT_CHOICES = [
        ("STUDENT_PERFORMANCE", "Student Performance Prediction"),
        ("DROPOUT_RISK", "Student Dropout Prediction"),
        ("FEE_COLLECTION", "Fee Collection Forecasting"),
        ("ENROLMENT", "Enrolment Forecasting"),
        ("RESOURCE_UTILISATION", "Resource Utilisation Forecasting"),
        ("SAAS_CHURN", "SaaS Churn Prediction"),
    ]

    insight_type = models.CharField(max_length=40, choices=INSIGHT_CHOICES)
    subject_reference = models.CharField(max_length=160, blank=True, null=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    prediction = models.JSONField(default=dict)
    recommended_action = models.TextField(blank=True, null=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "bi_predictive_insights"
        ordering = ["-generated_at"]


class BIDataRefreshLog(models.Model):
    source_module = models.CharField(max_length=80)
    status = models.CharField(max_length=30, default="COMPLETED")
    records_processed = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "bi_data_refresh_logs"
        ordering = ["-started_at"]


class BIAuditLog(models.Model):
    action = models.CharField(max_length=120)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    dashboard = models.ForeignKey(DashboardDefinition, on_delete=models.SET_NULL, null=True, blank=True)
    report_template = models.ForeignKey(ReportTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    object_reference = models.CharField(max_length=160, blank=True, null=True)
    parameters = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bi_audit_logs"
        ordering = ["-created_at"]
