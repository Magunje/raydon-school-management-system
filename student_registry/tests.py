from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academic_structure.models import (
    AcademicYear,
    Form,
    Stream,
    AcademicClass,
)
from student_registry.models import (
    Student,
    Guardian,
    StudentFeeRecord,
    StudentStatusLog,
)
from student_registry.services import (
    run_yearly_progression,
    reactivate_o_level_to_a_level,
)
import datetime
from decimal import Decimal
from unittest.mock import patch

User = get_user_model()


class StudentRegistryTestCase(TestCase):
    def setUp(self):
        # Create user accounts
        self.admin_user = User.objects.create_user(
            username="admin_user", password="password123", is_staff=True
        )
        self.staff_user = User.objects.create_user(
            username="staff_user", password="password123", is_staff=False
        )

        # Create academic foundations
        self.year_2026 = AcademicYear.objects.create(year=2026, is_active=True)
        self.year_2027 = AcademicYear.objects.create(year=2027, is_active=False)

        self.form_1 = Form.objects.create(form_number=1, name="Form 1")
        self.form_2 = Form.objects.create(form_number=2, name="Form 2")
        self.form_4 = Form.objects.create(form_number=4, name="Form 4")
        self.form_5 = Form.objects.create(form_number=5, name="Form 5")

        self.stream_a = Stream.objects.create(name="A")
        self.stream_arts = Stream.objects.create(name="Arts")

        self.class_form1 = AcademicClass.objects.create(
            academic_year=self.year_2026, form=self.form_1, stream=self.stream_a
        )
        self.class_form2_2027 = AcademicClass.objects.create(
            academic_year=self.year_2027, form=self.form_2, stream=self.stream_a
        )
        self.class_form4 = AcademicClass.objects.create(
            academic_year=self.year_2026, form=self.form_4, stream=self.stream_a
        )
        self.class_form5_arts_2027 = AcademicClass.objects.create(
            academic_year=self.year_2027, form=self.form_5, stream=self.stream_arts
        )

    def test_lifecycle_allowed_transitions(self):
        student = Student.objects.create(
            first_name="Ranga",
            surname="Chiri",
            gender="Male",
            date_of_birth=datetime.date(2012, 10, 5),
            admission_date=datetime.date(2026, 1, 15),
            status="Applicant",
        )

        # Applicant -> Pending Registration (Allowed)
        student.transition_to(
            "Pending Registration", self.staff_user, "Moving to registration step"
        )
        self.assertEqual(student.status, "Pending Registration")

        # Pending Registration -> Active Student (Allowed)
        student.transition_to(
            "Active Student", self.staff_user, "Registration finalized"
        )
        self.assertEqual(student.status, "Active Student")

        # Active Student -> Suspended (Allowed)
        student.transition_to("Suspended", self.admin_user, "Disciplinary action")
        self.assertEqual(student.status, "Suspended")

    def test_lifecycle_invalid_transitions(self):
        student = Student.objects.create(
            first_name="Rutendo",
            surname="Zhou",
            gender="Female",
            date_of_birth=datetime.date(2012, 3, 15),
            admission_date=datetime.date(2026, 1, 15),
            status="Applicant",
        )

        # Applicant -> Suspended (Invalid transition)
        with self.assertRaises(ValidationError):
            student.transition_to("Suspended", self.staff_user, "Direct suspension")

    def test_duplicate_registration_block(self):
        Student.objects.create(
            first_name="Tatenda",
            surname="Moyo",
            gender="Male",
            date_of_birth=datetime.date(2012, 5, 20),
            admission_date=datetime.date(2026, 1, 15),
        )

        # Attempt to register duplicate Tatenda Moyo should fail validation
        with self.assertRaises(ValidationError):
            Student.objects.create(
                first_name="Tatenda",
                surname="Moyo",
                gender="Male",
                date_of_birth=datetime.date(2012, 5, 20),
                admission_date=datetime.date(2026, 1, 15),
            )

    def test_automatic_promotion_block_form4(self):
        student = Student.objects.create(
            first_name="Kuda",
            surname="Dube",
            gender="Male",
            date_of_birth=datetime.date(2010, 11, 2),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form4,
            status="Active Student",
        )

        # Run year-end progression to year 2027
        run_yearly_progression(self.year_2027, self.admin_user)

        student.refresh_from_db()
        # Verify student is in Pending ZIMSEC Analysis, not promoted to Form 5
        self.assertEqual(student.status, "Pending ZIMSEC Analysis")
        self.assertEqual(student.academic_class, self.class_form4)

    def test_normal_promotion_flow(self):
        student = Student.objects.create(
            first_name="Shelter",
            surname="Maposa",
            gender="Female",
            date_of_birth=datetime.date(2012, 7, 7),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form1,
            status="Active Student",
        )

        # Run year-end progression to year 2027
        run_yearly_progression(self.year_2027, self.admin_user)

        student.refresh_from_db()
        # Verify Form 1 is promoted to Form 2
        self.assertEqual(student.academic_class, self.class_form2_2027)

    def test_zimsec_analysis_freeze_rules(self):
        import student_registry.models
        original_datetime = student_registry.models.datetime

        self.mocked_today = datetime.date(2026, 11, 30)
        test_self = self

        class MockDate(datetime.date):
            @classmethod
            def today(cls):
                return test_self.mocked_today

        class MockDatetime:
            date = MockDate

        student_registry.models.datetime = MockDatetime

        try:
            student = Student.objects.create(
                first_name="Sipho",
                surname="Nxumalo",
                gender="Male",
                date_of_birth=datetime.date(2010, 1, 12),
                admission_date=datetime.date(2026, 1, 15),
                academic_class=self.class_form4,
                status="Pending ZIMSEC Analysis",
            )

            # Create status log entry for Pending ZIMSEC Analysis in Nov 2026
            StudentStatusLog.objects.create(
                student=student,
                previous_status="Active Student",
                new_status="Pending ZIMSEC Analysis",
                changed_by=self.admin_user,
            )

            # Non-admin attempting transition before March 1, 2027 (e.g. Feb 15) should fail
            self.mocked_today = datetime.date(2027, 2, 15)
            with self.assertRaises(ValidationError):
                student.transition_to("Reactivated", self.staff_user, "Reactivating early")

            # Admin attempting transition before March 1, 2027 (e.g. Feb 15) should succeed
            student.transition_to("Reactivated", self.admin_user, "Admin override reactivation")
            self.assertEqual(student.status, "Reactivated")
        finally:
            student_registry.models.datetime = original_datetime

    def test_a_level_reactivation_and_fee_update(self):
        student = Student.objects.create(
            first_name="Tinashe",
            surname="Maringe",
            gender="Male",
            date_of_birth=datetime.date(2010, 6, 25),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_form4,
            status="Pending ZIMSEC Analysis",
        )

        # Reactivate returning student to Form 5 Arts
        reactivate_o_level_to_a_level(
            student, self.class_form5_arts_2027, self.admin_user
        )

        student.refresh_from_db()
        # Verify status is Active Student, class is Form 5 Arts
        self.assertEqual(student.status, "Active Student")
        self.assertEqual(student.academic_class, self.class_form5_arts_2027)

        # Verify A-Level fee structure is now bound
        rec = student.fee_records.get(fee_structure__name="A-Level Fee Structure")
        self.assertEqual(rec.amount, Decimal("150.00"))

    def test_audit_log_telemetry(self):
        student = Student.objects.create(
            first_name="Vusumuzi",
            surname="Ncube",
            gender="Male",
            date_of_birth=datetime.date(2012, 12, 12),
            admission_date=datetime.date(2026, 1, 15),
            status="Applicant",
        )

        student.transition_to("Pending Registration", self.staff_user, "Ready to pay")

        # Verify audit log entry
        log = StudentStatusLog.objects.filter(student=student).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.previous_status, "Applicant")
        self.assertEqual(log.new_status, "Pending Registration")
        self.assertEqual(log.changed_by, self.staff_user)
        self.assertEqual(log.reason, "Ready to pay")
