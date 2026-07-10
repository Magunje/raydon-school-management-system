from decimal import Decimal
import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.permissions import visible_menu
from human_resources.models import HRAuditLog, LeaveBalance
from human_resources.services import (
    apply_leave,
    approve_leave,
    contract_expiry_alerts,
    create_contract,
    create_employee,
    employee_directory_queryset,
    hr_dashboard_metrics,
    record_attendance,
)
from saas_tenant_management.models import SchoolTenant, set_current_tenant, clear_current_tenant
from teachers.models import TeacherEmployeeProfile


User = get_user_model()


class HumanResourcesWorkflowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username="hr_admin", password="password123")
        self.employee = create_employee(
            employee_number="EMP-HR-001",
            first_name="Nyasha",
            surname="Moyo",
            gender="Female",
            date_of_birth=datetime.date(1990, 5, 4),
            national_id="63-123456A90",
            phone_number="+263771234567",
            employment_date=datetime.date(2026, 1, 1),
            department="Academics",
            position="Teacher",
            employee_category="TEACHER",
            qualification="BEd",
            specialisation="Mathematics",
            next_of_kin="T Moyo",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="+263779999999",
        )

    def tearDown(self):
        clear_current_tenant()

    def test_leave_attendance_contract_alerts_and_audit(self):
        LeaveBalance.objects.create(
            employee=self.employee,
            leave_type="ANNUAL",
            allocated_days=Decimal("20.00"),
        )
        application = apply_leave(
            self.employee,
            "ANNUAL",
            datetime.date(2026, 2, 1),
            datetime.date(2026, 2, 5),
            Decimal("5.00"),
            "Family travel",
        )
        approve_leave(application, "SUPERVISOR", self.user)
        approve_leave(application, "HR", self.user)
        application.refresh_from_db()
        self.assertEqual(application.status, "HR_APPROVED")
        self.assertEqual(
            LeaveBalance.objects.get(employee=self.employee, leave_type="ANNUAL").remaining_days,
            Decimal("15.00"),
        )

        attendance = record_attendance(
            self.employee,
            datetime.date(2026, 2, 10),
            late_minutes=5,
            overtime_hours=Decimal("2.50"),
            biometric_reference="BIO-001",
        )
        self.assertEqual(attendance.overtime_hours, Decimal("2.50"))

        create_contract(
            self.employee,
            "TEMPORARY",
            datetime.date(2026, 1, 1),
            end_date=datetime.date.today() + datetime.timedelta(days=10),
        )
        self.assertEqual(contract_expiry_alerts(days=30).count(), 1)
        self.assertTrue(HRAuditLog.objects.filter(action="Leave approvals").exists())

    def test_premium_menu_gating_hides_hr_and_payroll_for_basic_tenants(self):
        basic = SchoolTenant.objects.create(
            name="Basic School",
            local_testing_port=9101,
            subscription_plan="BASIC",
        )
        premium = SchoolTenant.objects.create(
            name="Premium School",
            local_testing_port=9102,
            subscription_plan="PREMIUM",
        )

        set_current_tenant(basic)
        basic_labels = {item["label"] for item in visible_menu(self.user)}
        self.assertNotIn("Human Resources", basic_labels)
        self.assertNotIn("Payroll", basic_labels)

        set_current_tenant(premium)
        premium_labels = {item["label"] for item in visible_menu(self.user)}
        self.assertIn("Human Resources", premium_labels)
        self.assertIn("Payroll", premium_labels)

    def test_employee_list_view(self):
        self.client.force_login(self.user)
        response = self.client.get('/human-resources/')
        self.assertEqual(response.status_code, 200)

    def test_teacher_employee_linking_directory_and_profile_view(self):
        self.assertTrue(TeacherEmployeeProfile.objects.filter(employee=self.employee).exists())
        self.assertEqual(employee_directory_queryset({"q": "Nyasha"}).count(), 1)
        metrics = hr_dashboard_metrics()
        self.assertEqual(metrics["total_employees"], 1)
        self.client.force_login(self.user)
        response = self.client.get(f"/human-resources/employees/{self.employee.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.employee.employee_number)
