from django.test import TestCase
from django.db import connection
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
import datetime

from student_registry.models import Student
from academic_structure.models import AcademicYear, AcademicTerm, Form, Stream, AcademicClass
from human_resources.models import EmployeeProfile
from counselling.models import (
    CounsellingCase,
    CounsellingSession,
    CounsellingAppointment,
    CounsellingInterventionPlan,
    CareerGuidanceSession,
    CounsellingParentMeeting
)
from counselling.views import has_counsellor_access
from saas_tenant_management.schema import ensure_schema_with_cursor

User = get_user_model()


class GuidanceCounsellingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Build required SQLite schema in test DB
        with connection.cursor() as cursor:
            ensure_schema_with_cursor(cursor, vendor="sqlite")

        # Set up academic framework
        cls.year = AcademicYear.objects.create(year=2026, is_active=True)
        cls.term = AcademicTerm.objects.create(academic_year=cls.year, term_number=1, is_active=True)
        cls.form = Form.objects.create(form_number=1, name="Form 1")
        cls.stream = Stream.objects.create(name="A")
        cls.aclass = AcademicClass.objects.create(
            form=cls.form,
            stream=cls.stream,
            academic_year=cls.year,
        )

        # Register Student
        cls.student = Student.objects.create(
            admission_no="STU-COUNS-001",
            first_name="Anesu",
            surname="Banda",
            gender="Male",
            date_of_birth="2012-01-15",
            admission_date="2026-01-01",
            academic_class=cls.aclass,
            status="Active Student",
        )
        
        # Raw insert for pupils table to support portals raw SQL queries
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO pupils (pupil_id, admission_no, first_name, surname, gender, date_of_birth, grade, class_stream, guardian_name, guardian_phone, address, admission_date, status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [cls.student.pk, cls.student.admission_no, cls.student.first_name, cls.student.surname, cls.student.gender, "2012-01-15", "Form 1", "A", "Guardian", "123456", "Address", "2026-01-01", "Active"]
            )

        # Create staff user accounts and profiles
        cls.counsellor_user = User.objects.create_user(
            username="counsellor_staff", email="counsellor@school.com", password="pass"
        )
        from accounts.models import UserProfile
        UserProfile.objects.create(
            user=cls.counsellor_user,
            role="Guidance Counsellor",
            status="Active"
        )
        cls.counsellor_profile = EmployeeProfile.objects.create(
            user=cls.counsellor_user,
            employee_number="EMP-COUNS-01",
            first_name="Alice",
            surname="Helper",
            gender="Female",
            date_of_birth="1982-04-10",
            national_id="NID-COUNS-01",
            phone_number="0779988776",
            employment_date="2021-01-01",
            department="Guidance Department",
            position="Guidance Counsellor",
            employee_category="TEACHER",
            next_of_kin="Bob Helper",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="0779988775",
            status="ACTIVE",
        )

        cls.teacher_user = User.objects.create_user(
            username="teacher_staff", email="teacher@school.com", password="pass"
        )
        UserProfile.objects.create(
            user=cls.teacher_user,
            role="Teacher",
            status="Active"
        )
        cls.teacher_profile = EmployeeProfile.objects.create(
            user=cls.teacher_user,
            employee_number="EMP-COUNS-02",
            first_name="Thomas",
            surname="Teacher",
            gender="Male",
            date_of_birth="1985-06-20",
            national_id="NID-COUNS-02",
            phone_number="0771122334",
            employment_date="2020-01-01",
            department="Academic Science",
            position="Teacher",
            employee_category="TEACHER",
            next_of_kin="Sarah Teacher",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="0771122335",
            status="ACTIVE",
        )

    def test_counsellor_confidentiality_checks(self):
        # Counsellor user should have access
        self.assertTrue(has_counsellor_access(self.counsellor_user))

        # Teacher user should NOT have access to counselling files
        self.assertFalse(has_counsellor_access(self.teacher_user))

    def test_counselling_case_and_sessions(self):
        case = CounsellingCase.objects.create(
            case_no="CNS-2026-00001",
            student=self.student,
            category="Academic",
            description="Sudden drop in algebra marks and exam stress symptoms",
            severity_level="Medium",
            status="Open",
            assigned_counsellor=self.counsellor_profile
        )

        self.assertEqual(case.case_no, "CNS-2026-00001")
        self.assertEqual(case.student, self.student)

        # Log session notes
        session = CounsellingSession.objects.create(
            case=case,
            session_number=1,
            session_notes="Student expressed anxiety during test taking",
            recommendations="Introduce breathing techniques and structured review guide",
            status="Completed"
        )

        self.assertEqual(session.session_number, 1)
        self.assertEqual(case.sessions.count(), 1)

    def test_intervention_plans_and_appointments(self):
        case = CounsellingCase.objects.create(
            case_no="CNS-2026-00002",
            student=self.student,
            category="Social",
            description="Conflict resolving with roommate",
            severity_level="Low"
        )

        # Plan
        plan = CounsellingInterventionPlan.objects.create(
            case=case,
            plan_type="Social",
            objectives="Build positive interpersonal relationships",
            activities="Conflict resolution mediation sessions",
            review_date=datetime.date.today() + datetime.timedelta(days=30),
            responsible_person="Guidance Counsellor"
        )

        self.assertEqual(plan.plan_type, "Social")
        self.assertEqual(case.interventions.count(), 1)

        # Appointment
        appt = CounsellingAppointment.objects.create(
            student=self.student,
            counsellor=self.counsellor_profile,
            date=datetime.date.today() + datetime.timedelta(days=2),
            time=datetime.time(10, 30),
            status="Scheduled"
        )

        self.assertEqual(appt.status, "Scheduled")

    def test_views_access(self):
        # 1. Staff / Counsellor view access check
        self.client.force_login(self.counsellor_user)
        
        # Test dashboard page
        response = self.client.get('/counselling/')
        self.assertEqual(response.status_code, 200)
        
        # Test cases list page
        response = self.client.get('/counselling/cases/')
        self.assertEqual(response.status_code, 200)

        # Test case creation page
        response = self.client.get('/counselling/cases/new/')
        self.assertEqual(response.status_code, 200)

        # 2. Student Portal view access check
        session = self.client.session
        session['student_pupil_id'] = self.student.pk
        session['student_tenant_id'] = ""
        session.save()
        
        response = self.client.get('/student-portal/counselling')
        self.assertEqual(response.status_code, 200)
