from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import resolve, reverse

from accounts.models import UserProfile
from saas_tenant_management.models import SchoolTenant
from school_system_django.native import now_text


@override_settings(ALLOWED_HOSTS=["*"])
class PortalIsolationTests(TestCase):
    def setUp(self):
        self.tenant = SchoolTenant.objects.create(
            name="Raydon High School",
            subdomain="raydonhigh",
            production_domain="raydonhigh.raydonsystems.co.zw",
            active=True,
            is_active=True,
            is_suspended=False,
        )
        self.host = "raydonhigh.raydonsystems.co.zw"
        User = get_user_model()
        self.school_admin = User.objects.create_user(username="schooladmin", password="Admin12345")
        UserProfile.objects.create(
            user=self.school_admin,
            full_name="School Admin",
            role="Administrator",
            status="Active",
            created_at=now_text(),
            updated_at=now_text(),
        )
        self.staff_user = User.objects.create_user(username="teacher", password="Teacher12345")
        UserProfile.objects.create(
            user=self.staff_user,
            full_name="Teacher One",
            role="Teacher",
            status="Active",
            created_at=now_text(),
            updated_at=now_text(),
        )
        self.student_user = User.objects.create_user(username="studentuser", password="Student12345")
        UserProfile.objects.create(
            user=self.student_user,
            full_name="Student User",
            role="Student",
            status="Active",
            created_at=now_text(),
            updated_at=now_text(),
        )

    def client_for(self):
        return Client(HTTP_HOST=self.host)

    def test_student_login_anonymous_uses_dedicated_template(self):
        response = self.client_for().get("/student-portal/login")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "student_portal/login.html")
        self.assertNotContains(response, "Super Admin")
        self.assertNotContains(response, "Register Student")

    def test_staff_login_anonymous_returns_200(self):
        response = self.client_for().get("/staff-portal/login")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "staff_portal/login.html")
        self.assertNotContains(response, "Register Student")

    def test_school_admin_session_does_not_leak_admin_shell_into_student_login(self):
        client = self.client_for()
        client.force_login(self.school_admin)
        response = client.get("/student-portal/login")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "student_portal/login.html")
        self.assertNotContains(response, "Dashboard")
        self.assertNotContains(response, "Register Student")

    def test_school_admin_cannot_enter_student_dashboard(self):
        client = self.client_for()
        client.force_login(self.school_admin)
        response = client.get("/student-portal/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/student-portal/login", response["Location"])

    def test_staff_user_cannot_enter_student_dashboard(self):
        client = self.client_for()
        client.force_login(self.staff_user)
        response = client.get("/student-portal/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/student-portal/login", response["Location"])

    def test_student_user_cannot_enter_staff_dashboard(self):
        client = self.client_for()
        client.force_login(self.student_user)
        response = client.get("/staff-portal/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("staff_portal:login"))

    def test_staff_login_redirects_only_to_staff_dashboard(self):
        response = self.client_for().post(
            "/staff-portal/login",
            {"username": "teacher", "password": "Teacher12345"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("staff_portal:dashboard"))

    def test_invalid_staff_next_redirect_is_rejected(self):
        response = self.client_for().post(
            "/staff-portal/login?next=https://evil.example/boom",
            {"username": "teacher", "password": "Teacher12345"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("staff_portal:dashboard"))

    def test_staff_portal_uses_tenant_host(self):
        response = self.client_for().get("/staff-portal/login")
        self.assertEqual(response.wsgi_request.tenant.production_domain, self.host)

    def test_student_portal_uses_tenant_host(self):
        response = self.client_for().get("/student-portal/login")
        self.assertEqual(response.wsgi_request.tenant.production_domain, self.host)

    def test_missing_staff_profile_does_not_raise_500(self):
        User = get_user_model()
        user = User.objects.create_user(username="noprof", password="NoProf12345")
        client = self.client_for()
        client.force_login(user)
        response = client.get("/staff-portal/login")
        self.assertEqual(response.status_code, 200)

    def test_staff_logout_returns_to_staff_login(self):
        client = self.client_for()
        client.force_login(self.staff_user)
        response = client.get("/staff-portal/logout")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("staff_portal:login"))

    def test_student_and_staff_routes_resolve_to_namespaced_views(self):
        self.assertEqual(resolve("/student-portal/login").view_name, "student_portal:login")
        self.assertEqual(resolve("/staff-portal/login").view_name, "staff_portal:login")
