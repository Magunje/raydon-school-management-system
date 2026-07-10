from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import BIAuditLog, KPISnapshot, ReportExport, ScheduledReport
from .services import (
    capture_executive_snapshot,
    capture_kpi_snapshot,
    create_dashboard,
    create_report_template,
    dashboard_summary,
    export_report,
    generate_predictive_insight,
    run_report,
    save_report,
    schedule_report,
    seed_default_kpis,
)


class BusinessIntelligenceWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="reporter", email="reporter@example.com", password="Reporter123!"
        )

    def test_dashboard_report_schedule_export_and_audit(self):
        dashboard = create_dashboard(
            "Executive Overview",
            "EXECUTIVE",
            widgets=[
                {
                    "title": "Total Students",
                    "widget_type": "KPI_CARD",
                    "metric_code": "total_students",
                    "data_source": "student_registry",
                }
            ],
            user=self.user,
        )
        template = create_report_template(
            "Executive Summary",
            "executive",
            fields=["total_students", "revenue_collected"],
            user=self.user,
            default_format="PDF",
        )
        saved = save_report(template, "Monthly Executive Summary", self.user, filters={"period": "monthly"})
        schedule = schedule_report(saved, "MONTHLY", timezone.now())
        execution = run_report(template, user=self.user, parameters={"period": "monthly"}, saved_report=saved)
        export = export_report(execution, "PDF", user=self.user)

        self.assertEqual(dashboard.widgets.count(), 1)
        self.assertEqual(execution.status, "COMPLETED")
        self.assertEqual(schedule.frequency, "MONTHLY")
        self.assertTrue(ScheduledReport.objects.exists())
        self.assertEqual(ReportExport.objects.get(pk=export.pk).export_format, "PDF")
        self.assertTrue(BIAuditLog.objects.filter(action="Report export").exists())

    def test_kpi_snapshot_executive_snapshot_and_predictive_insight(self):
        kpis = seed_default_kpis()
        snapshot = capture_kpi_snapshot(kpis[0], Decimal("58.50"))
        executive = capture_executive_snapshot(user=self.user)
        insight = generate_predictive_insight(
            "FEE_COLLECTION",
            {"forecast": "Improving", "next_month_collection_rate": 82},
            Decimal("88.50"),
            recommended_action="Continue payment reminder campaigns.",
            user=self.user,
        )

        self.assertEqual(snapshot.status, "ALERT")
        self.assertTrue(KPISnapshot.objects.filter(kpi=kpis[0]).exists())
        self.assertIn("total_students", executive.metrics)
        self.assertEqual(dashboard_summary("EXECUTIVE"), executive.metrics)
        self.assertEqual(insight.insight_type, "FEE_COLLECTION")

    def test_bi_dashboard_list_view(self):
        self.client.force_login(self.user)
        response = self.client.get('/business-intelligence/')
        self.assertEqual(response.status_code, 200)
