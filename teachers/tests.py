import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from human_resources.services import create_employee


class TeacherProfileIntegrationTests(TestCase):
    def test_teacher_profiles_render_from_employee_records(self):
        user = get_user_model().objects.create_superuser(username="teacher_admin", password="password123")
        employee = create_employee(
            employee_number="EMP-TCH-001",
            first_name="Tariro",
            surname="Ncube",
            gender="Female",
            date_of_birth=datetime.date(1988, 1, 2),
            national_id="TCH-001",
            phone_number="+263771111111",
            email="tariro@example.com",
            employment_date=datetime.date(2026, 1, 1),
            department="Academics",
            position="Mathematics Teacher",
            employee_category="TEACHER",
            teaching_subjects="Mathematics",
            assigned_classes="Form 4A",
            next_of_kin="N Ncube",
            next_of_kin_relationship="Sibling",
            next_of_kin_phone="+263772222222",
        )

        self.client.force_login(user)
        response = self.client.get("/teachers")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, employee.employee_number)
        self.assertContains(response, "Mathematics")
