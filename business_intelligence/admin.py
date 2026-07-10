from django.contrib import admin

from .models import (
    AnalyticsSnapshot,
    BIAuditLog,
    BIDataRefreshLog,
    DashboardDefinition,
    DashboardWidget,
    KPIDefinition,
    KPISnapshot,
    PredictiveInsight,
    ReportExecutionLog,
    ReportExport,
    ReportTemplate,
    SavedReport,
    ScheduledReport,
)


class DashboardWidgetInline(admin.TabularInline):
    model = DashboardWidget
    extra = 0


@admin.register(DashboardDefinition)
class DashboardDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "permission_code", "refresh_interval_minutes", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    inlines = [DashboardWidgetInline]


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "module_code", "default_format", "permission_code", "is_system_template")
    list_filter = ("module_code", "default_format", "is_system_template")
    search_fields = ("name", "module_code")


@admin.register(SavedReport)
class SavedReportAdmin(admin.ModelAdmin):
    list_display = ("name", "template", "owner", "output_format", "is_shared", "created_at")
    list_filter = ("output_format", "is_shared")
    search_fields = ("name", "template__name", "owner__username")


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ("saved_report", "frequency", "delivery_method", "next_run_at", "is_active")
    list_filter = ("frequency", "delivery_method", "is_active")


@admin.register(ReportExecutionLog)
class ReportExecutionLogAdmin(admin.ModelAdmin):
    list_display = ("report_template", "saved_report", "executed_by", "status", "started_at", "completed_at")
    list_filter = ("status",)


@admin.register(ReportExport)
class ReportExportAdmin(admin.ModelAdmin):
    list_display = ("file_name", "export_format", "exported_by", "exported_at")
    list_filter = ("export_format",)


@admin.register(KPIDefinition)
class KPIDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "module_code", "target_value", "alert_threshold", "is_active")
    list_filter = ("module_code", "is_active")
    search_fields = ("name", "code")


@admin.register(KPISnapshot)
class KPISnapshotAdmin(admin.ModelAdmin):
    list_display = ("kpi", "snapshot_date", "value", "target_value", "status")
    list_filter = ("status", "snapshot_date")


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ("category", "snapshot_date", "generated_by", "created_at")
    list_filter = ("category", "snapshot_date")


@admin.register(PredictiveInsight)
class PredictiveInsightAdmin(admin.ModelAdmin):
    list_display = ("insight_type", "subject_reference", "confidence_score", "generated_by", "generated_at")
    list_filter = ("insight_type",)


@admin.register(BIDataRefreshLog)
class BIDataRefreshLogAdmin(admin.ModelAdmin):
    list_display = ("source_module", "status", "records_processed", "started_at", "completed_at")
    list_filter = ("source_module", "status")


@admin.register(BIAuditLog)
class BIAuditLogAdmin(admin.ModelAdmin):
    list_display = ("action", "user", "dashboard", "report_template", "object_reference", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "object_reference")
