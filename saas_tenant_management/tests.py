from django.test import TestCase, RequestFactory, override_settings
from django.core.exceptions import ValidationError
from django.db import models
from django.http import HttpResponse

from saas_tenant_management.models import (
    SchoolTenant,
    TenantBaseModel,
    get_current_tenant,
    set_current_tenant,
    clear_current_tenant,
)
from saas_tenant_management.middleware import TenantMiddleware


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
