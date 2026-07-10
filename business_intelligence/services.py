from decimal import Decimal

from django.apps import apps
from django.db.models import Sum
from django.utils import timezone

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


def log_bi_action(action, user=None, dashboard=None, report_template=None, object_reference=None, parameters=None):
    return BIAuditLog.objects.create(
        action=action,
        user=user,
        dashboard=dashboard,
        report_template=report_template,
        object_reference=object_reference,
        parameters=parameters,
    )


def create_dashboard(name, category, widgets=None, user=None, permission_code="reports.view"):
    dashboard = DashboardDefinition.objects.create(
        name=name,
        category=category,
        permission_code=permission_code,
        created_by=user,
    )
    for index, widget in enumerate(widgets or []):
        DashboardWidget.objects.create(
            dashboard=dashboard,
            title=widget["title"],
            widget_type=widget.get("widget_type", "KPI_CARD"),
            metric_code=widget["metric_code"],
            data_source=widget.get("data_source", "manual"),
            configuration=widget.get("configuration", {}),
            display_order=index,
        )
    log_bi_action("Dashboard created", user=user, dashboard=dashboard)
    return dashboard


def create_report_template(name, module_code, fields, filters=None, user=None, default_format="PDF"):
    template = ReportTemplate.objects.create(
        name=name,
        module_code=module_code,
        fields=fields,
        filters=filters or {},
        created_by=user,
        default_format=default_format,
    )
    log_bi_action("Report customisation", user=user, report_template=template, parameters={"fields": fields})
    return template


def save_report(template, name, owner, filters=None, output_format=None, is_shared=False):
    saved = SavedReport.objects.create(
        template=template,
        name=name,
        owner=owner,
        filters=filters or {},
        output_format=output_format or template.default_format,
        is_shared=is_shared,
    )
    log_bi_action("Saved report created", user=owner, report_template=template, object_reference=name)
    return saved


def schedule_report(saved_report, frequency, next_run_at, delivery_method="DOWNLOAD_CENTRE"):
    schedule = ScheduledReport.objects.create(
        saved_report=saved_report,
        frequency=frequency,
        delivery_method=delivery_method,
        next_run_at=next_run_at,
    )
    log_bi_action("Scheduled reports", user=saved_report.owner, report_template=saved_report.template, object_reference=saved_report.name)
    return schedule


def run_report(template, user=None, parameters=None, saved_report=None):
    execution = ReportExecutionLog.objects.create(
        report_template=template,
        saved_report=saved_report,
        executed_by=user,
        parameters=parameters or {},
        status="RUNNING",
    )
    summary = {
        "module": template.module_code,
        "field_count": len(template.fields),
        "filter_count": len(template.filters),
    }
    execution.status = "COMPLETED"
    execution.completed_at = timezone.now()
    execution.result_summary = summary
    execution.save(update_fields=["status", "completed_at", "result_summary"])
    log_bi_action("Report generation", user=user, report_template=template, parameters=parameters or {})
    return execution


def export_report(execution, export_format, user=None):
    export = ReportExport.objects.create(
        execution=execution,
        export_format=export_format,
        file_name=f"{execution.report_template.module_code}_{execution.id}.{export_format.lower()}",
        exported_by=user,
    )
    log_bi_action("Report export", user=user, report_template=execution.report_template, object_reference=export.file_name)
    return export


def capture_kpi_snapshot(kpi, value, snapshot_date=None, metadata=None):
    snapshot_date = snapshot_date or timezone.localdate()
    status = "ON_TRACK"
    if kpi.alert_threshold is not None and Decimal(value) < kpi.alert_threshold:
        status = "ALERT"
    snapshot, _ = KPISnapshot.objects.update_or_create(
        kpi=kpi,
        snapshot_date=snapshot_date,
        defaults={
            "value": value,
            "target_value": kpi.target_value,
            "status": status,
            "metadata": metadata or {},
        },
    )
    log_bi_action("Analytics execution", object_reference=kpi.code, parameters={"value": str(value), "status": status})
    return snapshot


def capture_executive_snapshot(user=None, snapshot_date=None):
    snapshot_date = snapshot_date or timezone.localdate()
    metrics = {
        "total_students": _count_model("student_registry", "Student"),
        "total_staff": _count_model("human_resources", "EmployeeProfile"),
        "active_schools": _count_model("saas_tenant_management", "SchoolTenant", active=True),
        "security_alerts": _count_model("system_administration", "SecurityIncident", status="OPEN"),
        "subscription_revenue": _sum_model("saas_tenant_management", "SubscriptionPayment", "amount"),
    }
    snapshot, _ = AnalyticsSnapshot.objects.update_or_create(
        category="EXECUTIVE",
        snapshot_date=snapshot_date,
        defaults={"metrics": metrics, "generated_by": user},
    )
    BIDataRefreshLog.objects.create(
        source_module="EXECUTIVE",
        status="COMPLETED",
        records_processed=len(metrics),
        completed_at=timezone.now(),
    )
    log_bi_action("Dashboard access", user=user, object_reference="EXECUTIVE", parameters=metrics)
    return snapshot


def dashboard_summary(category):
    latest = AnalyticsSnapshot.objects.filter(category=category).order_by("-snapshot_date").first()
    return latest.metrics if latest else {}


def generate_predictive_insight(insight_type, prediction, confidence_score, subject_reference=None, recommended_action=None, user=None):
    insight = PredictiveInsight.objects.create(
        insight_type=insight_type,
        prediction=prediction,
        confidence_score=confidence_score,
        subject_reference=subject_reference,
        recommended_action=recommended_action,
        generated_by=user,
    )
    log_bi_action("Analytics execution", user=user, object_reference=insight_type, parameters=prediction)
    return insight


def seed_default_kpis():
    defaults = [
        ("Pass Rate", "pass_rate", "results_centre", "passed_students / total_students * 100", Decimal("75.00"), Decimal("60.00")),
        ("Collection Rate", "collection_rate", "fees_management", "amount_paid / total_charges * 100", Decimal("90.00"), Decimal("70.00")),
        ("Student Retention Rate", "student_retention_rate", "student_registry", "active_students / enrolled_students * 100", Decimal("95.00"), Decimal("85.00")),
        ("Teacher Attendance Rate", "teacher_attendance_rate", "attendance_ledger", "present_teachers / total_teachers * 100", Decimal("95.00"), Decimal("85.00")),
        ("Revenue Growth", "revenue_growth", "fees_management", "current_period_revenue_growth", Decimal("10.00"), Decimal("0.00")),
    ]
    created = []
    for name, code, module_code, formula, target, threshold in defaults:
        kpi, _ = KPIDefinition.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "module_code": module_code,
                "formula": formula,
                "target_value": target,
                "alert_threshold": threshold,
            },
        )
        created.append(kpi)
    return created


def _count_model(app_label, model_name, **filters):
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return 0
    try:
        return model.objects.filter(**filters).count() if filters else model.objects.count()
    except Exception:
        return 0


def _sum_model(app_label, model_name, field_name):
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return "0.00"
    try:
        value = model.objects.aggregate(total=Sum(field_name))["total"] or Decimal("0.00")
        return str(value)
    except Exception:
        return "0.00"
