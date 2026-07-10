from django.test import TestCase
from django.db import connection
from django.contrib.auth import get_user_model
from decimal import Decimal
import datetime

from student_registry.models import Student
from academic_structure.models import AcademicYear, AcademicTerm, Form, Stream, AcademicClass
from human_resources.models import EmployeeProfile
from discipline.models import (
    DisciplineCategory,
    DisciplineProfile,
    DisciplinaryIncident,
    DisciplineSanction,
    DisciplineSuspension,
    ParentMeeting,
    BehaviourImprovementPlan
)
from counselling.models import CounsellingCase
from saas_tenant_management.schema import ensure_schema_with_cursor

User = get_user_model()


class StudentDisciplineTests(TestCase):
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
            admission_no="STU-DISC-001",
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

        # Register Staff
        cls.staff = EmployeeProfile.objects.create(
            employee_number="EMP-DISC-01",
            first_name="John",
            surname="Doe",
            gender="Male",
            date_of_birth="1980-01-01",
            national_id="NID-DISC-01",
            phone_number="1234567",
            employment_date="2020-01-01",
            department="Discipline Office",
            position="Head of Discipline",
            employee_category="ADMIN",
            next_of_kin="Mary Doe",
            next_of_kin_relationship="Spouse",
            next_of_kin_phone="7654321",
            status="ACTIVE",
        )

        # Configure Categories
        cls.minor_offence = DisciplineCategory.objects.create(
            name="Late Coming",
            default_points=3,
            severity="Minor"
        )
        cls.major_offence = DisciplineCategory.objects.create(
            name="Fighting",
            default_points=15,
            severity="Major"
        )

    def test_behaviour_points_deduction(self):
        # Initial profile check
        profile, _ = DisciplineProfile.objects.get_or_create(student=self.student)
        self.assertEqual(profile.behaviour_score, 100)

        # Log minor offence
        inc1 = DisciplinaryIncident.objects.create(
            incident_no="INC-2026-00001",
            student=self.student,
            category=self.minor_offence,
            severity=self.minor_offence.severity,
            description="Arrived 15 mins late to assembly",
            reported_by=self.staff,
            status="Under Investigation"
        )

        profile.refresh_from_db()
        self.assertEqual(profile.behaviour_score, 97) # 100 - 3 points
        self.assertEqual(profile.total_incidents, 1)

        # Log major offence
        inc2 = DisciplinaryIncident.objects.create(
            incident_no="INC-2026-00002",
            student=self.student,
            category=self.major_offence,
            severity=self.major_offence.severity,
            description="Participated in physical altercation",
            reported_by=self.staff,
            status="Pending Action"
        )

        profile.refresh_from_db()
        self.assertEqual(profile.behaviour_score, 82) # 97 - 15 points
        self.assertEqual(profile.total_incidents, 2)

    def test_counselling_referral_on_sanction(self):
        inc = DisciplinaryIncident.objects.create(
            incident_no="INC-2026-00003",
            student=self.student,
            category=self.major_offence,
            severity=self.major_offence.severity,
            description="Vandalism of school desk",
            reported_by=self.staff,
        )

        # Assign Sanction of type Counselling Referral
        sanction = DisciplineSanction.objects.create(
            incident=inc,
            student=self.student,
            sanction_type="Counselling Referral",
            reason="Referral to address anger issues",
            approved_by=self.staff,
            is_active=True
        )

        # Verify counselling case auto-created in CounsellingCase model
        cns_cases = CounsellingCase.objects.filter(student=self.student)
        self.assertEqual(cns_cases.count(), 1)
        self.assertEqual(cns_cases.first().category, "Behavioural")

    def test_suspension_management(self):
        inc = DisciplinaryIncident.objects.create(
            incident_no="INC-2026-00004",
            student=self.student,
            category=self.major_offence,
            severity=self.major_offence.severity,
            description="Exam Malpractice",
            reported_by=self.staff,
        )

        sanction = DisciplineSanction.objects.create(
            incident=inc,
            student=self.student,
            sanction_type="Suspension",
            reason="Caught with cheating aids",
            approved_by=self.staff,
        )

        susp = DisciplineSuspension.objects.create(
            sanction=sanction,
            student=self.student,
            suspension_type="External",
            start_date=datetime.date.today(),
            end_date=datetime.date.today() + datetime.timedelta(days=7),
            reason="External suspension rules enforced"
        )

        self.assertEqual(susp.suspension_type, "External")
        profile = DisciplineProfile.objects.get(student=self.student)
        self.assertEqual(profile.suspension_history, 1)

    def test_permanent_record_delete_protection(self):
        inc = DisciplinaryIncident.objects.create(
            incident_no="INC-2026-00005",
            student=self.student,
            category=self.minor_offence,
            severity="Minor",
            description="Incomplete math homework",
        )

        # Call delete
        inc.delete()

        # Verify it still exists in database (delete protection overrides delete function)
        self.assertTrue(DisciplinaryIncident.objects.filter(pk=inc.pk).exists())

    def test_views_access(self):
        # 1. Staff view access check
        staff_user = User.objects.create_user(username="test_staff", password="password")
        from accounts.models import UserProfile
        UserProfile.objects.create(user=staff_user, role="Super Admin", status="Active")
        
        self.client.force_login(staff_user)
        
        # Test dashboard page
        response = self.client.get('/discipline/')
        self.assertEqual(response.status_code, 200)
        
        # Test incident list page
        response = self.client.get('/discipline/incidents/')
        self.assertEqual(response.status_code, 200)

        # Test incident register page
        response = self.client.get('/discipline/incidents/new/')
        self.assertEqual(response.status_code, 200)

        # 2. Student Portal view access check
        session = self.client.session
        session['student_pupil_id'] = self.student.pk
        session['student_tenant_id'] = ""
        session.save()
        
        response = self.client.get('/student-portal/discipline')
        self.assertEqual(response.status_code, 200)
