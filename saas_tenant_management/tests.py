from django.test import TestCase, RequestFactory, override_settings
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpResponse
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from saas_tenant_management.models import (
    ModuleDefinition,
    SubscriptionInvoice,
    SubscriptionPayment,
    SubscriptionPlan,
    SchoolTenant,
    TenantModule,
    TenantModuleActivation,
    TenantBaseModel,
    TenantSubscription,
    get_current_tenant,
    set_current_tenant,
    clear_current_tenant,
)
from saas_tenant_management.services import (
    activate_module,
    capture_usage_snapshot,
    create_school_subscription,
    create_tenant_record,
    create_subscription_invoice,
    deactivate_module,
    record_subscription_payment,
    renew_subscription,
    seed_default_modules,
)
from saas_tenant_management.middleware import TenantMiddleware
from decimal import Decimal
import datetime


# Concrete model subclassing TenantBaseModel to verify strict multi-school data isolation
class MockStudent(TenantBaseModel):
    admission_no = models.CharField(max_length=50)
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "test_saas_mock_students"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "admission_no"],
                name="unique_saas_admission_no_per_tenant"
            )
        ]


@override_settings(ALLOWED_HOSTS=["*"])
class MultiTenantRoutingTestCase(TestCase):
    def setUp(self):
        clear_current_tenant()
        self.factory = RequestFactory()

        # Seed School A on Port 8007
        self.tenant_a = SchoolTenant.objects.create(
            name="School A (Harare Campus)",
            local_testing_port=8007,
            production_domain="harare.raydonsystem.com",
            address="123 Samora Machel Ave, Harare",
            telephone="+263771000001",
            subscription_plan="PREMIUM"
        )

        # Seed School B on Port 8008
        self.tenant_b = SchoolTenant.objects.create(
            name="School B (Masvingo Campus)",
            local_testing_port=8008,
            production_domain="masvingo.raydonsystem.com",
            address="456 Robert Mugabe Way, Masvingo",
            telephone="+263771000002",
            subscription_plan="BASIC"
        )

    def test_local_port_routing_school_a(self):
        # Local development routing by port (8007)
        request = self.factory.get("/", HTTP_HOST="localhost:8007")
        middleware = TenantMiddleware(lambda req: HttpResponse("Success"))
        
        response = middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.tenant, self.tenant_a)

    def test_local_port_routing_school_b(self):
        # Local development routing by port (8008)
        request = self.factory.get("/", HTTP_HOST="localhost:8008")
        middleware = TenantMiddleware(lambda req: HttpResponse("Success"))
        
        response = middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.tenant, self.tenant_b)

    def test_production_domain_routing_school_a(self):
        # Production routing by domain (harare.raydonsystem.com)
        request = self.factory.get("/", HTTP_HOST="harare.raydonsystem.com")
        middleware = TenantMiddleware(lambda req: HttpResponse("Success"))
        
        response = middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.tenant, self.tenant_a)

    def test_raydonsystems_subdomain_routing(self):
        self.tenant_a.subdomain = "school1"
        self.tenant_a.save()
        request = self.factory.get("/", HTTP_HOST="school1.raydonsystems.co.zw")
        middleware = TenantMiddleware(lambda req: HttpResponse("Success"))

        response = middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(request.tenant, self.tenant_a)

    def test_unregistered_tenant_not_found(self):
        # Accessing via unregistered local port should return 404
        request = self.factory.get("/", HTTP_HOST="localhost:9999")
        middleware = TenantMiddleware(lambda req: HttpResponse("Success"))
        
        response = middleware(request)
        self.assertEqual(response.status_code, 404)

    def test_inactive_tenant_blocked(self):
        # Deactivate tenant A
        self.tenant_a.active = False
        self.tenant_a.save()

        request = self.factory.get("/", HTTP_HOST="harare.raydonsystem.com")
        middleware = TenantMiddleware(lambda req: HttpResponse("Success"))
        
        response = middleware(request)
        self.assertEqual(response.status_code, 403)

    def test_strict_port_data_isolation(self):
        # Setup student record in Tenant A (Port 8007)
        set_current_tenant(self.tenant_a)
        student_a = MockStudent.objects.create(
            tenant=self.tenant_a,
            admission_no="A26001",
            name="Alice Zhou"
        )

        # Setup student record with SAME admission number in Tenant B (Port 8008)
        set_current_tenant(self.tenant_b)
        student_b = MockStudent.objects.create(
            tenant=self.tenant_b,
            admission_no="A26001",
            name="Bob Moyo"
        )

        # In context of Tenant B (Port 8008), only student_b is visible
        set_current_tenant(self.tenant_b)
        qs_b = MockStudent.objects.all()
        self.assertIn(student_b, qs_b)
        self.assertNotIn(student_a, qs_b)
        self.assertEqual(qs_b.count(), 1)

        # In context of Tenant A (Port 8007), only student_a is visible
        set_current_tenant(self.tenant_a)
        qs_a = MockStudent.objects.all()
        self.assertIn(student_a, qs_a)
        self.assertNotIn(student_b, qs_a)
        self.assertEqual(qs_a.count(), 1)

    def test_module_activation_dependencies_billing_and_usage(self):
        modules = seed_default_modules()
        plan = SubscriptionPlan.objects.create(
            code="ENTERPRISE",
            name="Enterprise Package",
            monthly_price=Decimal("100.00"),
            annual_price=Decimal("1000.00"),
        )
        subscription = create_school_subscription(
            tenant=self.tenant_a,
            plan=plan,
            start_date=datetime.date(2026, 1, 1),
            expiry_date=datetime.date(2026, 12, 31),
            modules={"payroll", "medical"},
            status="ACTIVE",
        )
        self.tenant_a.refresh_from_db()
        self.assertEqual(self.tenant_a.subscription_plan, "ENTERPRISE")
        self.assertTrue(self.tenant_a.has_module("payroll"))
        self.assertTrue(self.tenant_a.has_module("human_resources"))
        self.assertTrue(TenantModuleActivation.objects.filter(tenant=self.tenant_a, module__code="medical", status="ACTIVE").exists())

        with self.assertRaises(ValidationError):
            deactivate_module(self.tenant_a, "fees_management")
        deactivation = deactivate_module(self.tenant_a, "medical", reason="School downgraded")
        self.assertEqual(deactivation.status, "DISABLED")

        invoice = create_subscription_invoice(
            subscription,
            invoice_date=datetime.date(2026, 1, 1),
            due_date=datetime.date(2026, 1, 31),
            amount=Decimal("100.00"),
        )
        payment = record_subscription_payment(
            invoice,
            payment_date=datetime.date(2026, 1, 10),
            amount=Decimal("100.00"),
            payment_method="BANK_TRANSFER",
            reference_number="BANK-001",
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "PAID")
        self.assertTrue(payment.payment_number.startswith("SPAY-"))

        renew_subscription(subscription, datetime.date(2027, 12, 31))
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "ACTIVE")
        self.assertEqual(subscription.expiry_date, datetime.date(2027, 12, 31))

        snapshot = capture_usage_snapshot(
            self.tenant_a,
            user_count=20,
            student_count=500,
            storage_usage_mb=Decimal("250.50"),
            database_size_mb=Decimal("512.00"),
            api_usage_count=100,
            login_activity_count=300,
            snapshot_date=datetime.date(2026, 1, 15),
        )
        self.assertEqual(snapshot.student_count, 500)

    def test_tenant_list_view(self):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.create_superuser(username="saas_admin", password="password")
        self.client.force_login(user)
        response = self.client.get('/saas-tenants/')
        self.assertEqual(response.status_code, 200)


class TenantManagementApiTestCase(TestCase):
    def setUp(self):
        self.media_root = Path(tempfile.mkdtemp())
        self.override = override_settings(MEDIA_ROOT=self.media_root, ALLOWED_HOSTS=["*"])
        self.override.enable()
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.super_admin = User.objects.create_superuser(username="super", email="super@example.com", password="password")
        self.school_admin = User.objects.create_user(username="school_admin", password="password")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def create_api_tenant_without_postgres(self, data, logo=None, user=None, provision=True):
        return create_tenant_record(data, logo=logo, user=user, provision=False)

    def test_create_tenant_service_encrypts_credentials_and_modules(self):
        result = create_tenant_record(
            {
                "school_name": "Alpha Academy",
                "school_code": "ALPHA",
                "school_email": "info@alpha.test",
                "school_phone": "+263700000001",
                "school_address": "Harare",
                "subdomain": "alpha",
                "plan_type": "PREMIUM",
                "modules": ["student_registration", "fees_management", "library"],
                "database_password": "PlainPassword123",
            },
            provision=False,
        )

        tenant = result["tenant"]
        self.assertEqual(tenant.name, "Alpha Academy")
        self.assertNotEqual(tenant.database_password, "PlainPassword123")
        self.assertEqual(tenant.get_database_password(), "PlainPassword123")
        self.assertTrue(TenantModule.objects.filter(tenant=tenant, module_name="library", enabled=True).exists())
        self.assertTrue((self.media_root / "tenants" / str(tenant.tenant_id)).exists())

    def test_school_admin_cannot_access_tenant_api(self):
        self.client.force_login(self.school_admin)
        response = self.client.get("/api/tenants/")
        self.assertEqual(response.status_code, 403)

    @patch("saas_tenant_management.views.create_tenant_record")
    def test_create_edit_suspend_delete_tenant_api(self, mocked_create):
        mocked_create.side_effect = self.create_api_tenant_without_postgres
        self.client.force_login(self.super_admin)

        create_response = self.client.post(
            "/api/tenants/create/",
            {
                "school_name": "Beta School",
                "school_code": "BETA",
                "school_email": "admin@beta.test",
                "school_phone": "+263700000002",
                "school_address": "Bulawayo",
                "subdomain": "beta",
                "testing_port": "8101",
                "plan_type": "STARTER",
                "trial_period": "7",
                "modules": ["student_registration", "fees_management"],
            },
        )
        self.assertEqual(create_response.status_code, 201)
        tenant_id = create_response.json()["tenant"]["id"]

        edit_response = self.client.put(
            f"/api/tenants/{tenant_id}/update/",
            data=json.dumps({"school_name": "Beta International School", "plan_type": "PREMIUM"}),
            content_type="application/json",
        )
        self.assertEqual(edit_response.status_code, 200)
        self.assertEqual(edit_response.json()["tenant"]["school_name"], "Beta International School")

        suspend_response = self.client.post(f"/api/tenants/{tenant_id}/suspend/")
        self.assertEqual(suspend_response.status_code, 200)
        self.assertTrue(suspend_response.json()["tenant"]["is_suspended"])

        activate_response = self.client.post(f"/api/tenants/{tenant_id}/activate/")
        self.assertEqual(activate_response.status_code, 200)
        self.assertTrue(activate_response.json()["tenant"]["is_active"])

        delete_response = self.client.post(f"/api/tenants/{tenant_id}/delete/")
        self.assertEqual(delete_response.status_code, 200)
        self.assertFalse(SchoolTenant.objects.filter(tenant_id=tenant_id).exists())
