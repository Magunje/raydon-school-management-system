from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from academic_structure.models import (
    AcademicYear,
    AcademicTerm,
    Form,
    Stream,
    AcademicClass,
)
from student_registry.models import Student
from subject_management.models import (
    Subject,
    StudentSubjectRegistration,
    TeacherSubjectAllocation,
)
from zimsec_analytics.models import ZIMSECCandidateResult
from zimsec_analytics.services import (
    calculate_student_analytics,
    calculate_section_analytics,
)
import datetime

User = get_user_model()


class ZimsecAnalyticsTestCase(TestCase):
    def setUp(self):
        # Users
        self.admin = User.objects.create_user(
            username="admin", password="password123", is_staff=True
        )
        self.teacher = User.objects.create_user(
            username="teacher", password="password123", is_staff=False
        )

        # Academic structure
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.term = AcademicTerm.objects.create(
            academic_year=self.year, term_number=1, is_active=True
        )

        self.form_4 = Form.objects.create(form_number=4, name="Form 4")
        self.stream_a = Stream.objects.create(name="A")

        self.academic_class = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_4, stream=self.stream_a
        )

        # Subjects
        self.sub_eng = Subject.objects.create(
            code="OL_ENG",
            name="English Language",
            level="O_LEVEL",
            department="Languages",
        )
        self.sub_mat = Subject.objects.create(
            code="OL_MAT",
            name="Mathematics",
            level="O_LEVEL",
            department="Sciences",
        )
        self.sub_geo = Subject.objects.create(
            code="OL_GEO",
            name="Geography",
            level="O_LEVEL",
            department="Humanities",
        )
        self.sub_his = Subject.objects.create(
            code="OL_HIS",
            name="History",
            level="O_LEVEL",
            department="Humanities",
        )
        self.sub_agr = Subject.objects.create(
            code="OL_AGR",
            name="Agriculture",
            level="O_LEVEL",
            department="Practicals",
        )

        # Teacher allocations
        TeacherSubjectAllocation.objects.create(
            teacher=self.teacher,
            subject=self.sub_mat,
            academic_year=self.year,
            academic_term=self.term,
            form=self.form_4,
            stream=self.stream_a,
        )

        # Create active registered students
        self.student_eligible = Student.objects.create(
            first_name="Rutendo",
            surname="Zhou",
            gender="Female",
            date_of_birth=datetime.date(2010, 3, 15),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )

        # Register student to subjects
        for sub in [
            self.sub_eng,
            self.sub_mat,
            self.sub_geo,
            self.sub_his,
            self.sub_agr,
        ]:
            StudentSubjectRegistration.objects.create(
                student=self.student_eligible,
                subject=sub,
                academic_year=self.year,
                academic_term=self.term,
            )

    def test_zimsec_result_validations(self):
        # 1. Subject registration rigidity block (attempt to record result for unregistered subject should fail)
        sub_unregistered = Subject.objects.create(
            code="OL_SHO", name="Shona", level="O_LEVEL"
        )
        with self.assertRaises(ValidationError):
            ZIMSECCandidateResult.objects.create(
                student=self.student_eligible,
                subject=sub_unregistered,
                grade="A",
                session="NOVEMBER",
                exam_year=2026,
            )

        # 2. Year mismatch validation (exam year earlier than admission year should fail)
        with self.assertRaises(ValidationError):
            ZIMSECCandidateResult.objects.create(
                student=self.student_eligible,
                subject=self.sub_mat,
                grade="A",
                session="NOVEMBER",
                exam_year=2025,  # Admission is 2026
            )

        # 3. Successful registration
        res = ZIMSECCandidateResult.objects.create(
            student=self.student_eligible,
            subject=self.sub_mat,
            grade="A",
            session="NOVEMBER",
            exam_year=2026,
        )
        self.assertIsNotNone(res)

    def test_student_and_section_analytics_aggregations(self):
        # Create full pass results for student (5 passes: English, Math, Geo, His, Agr)
        ZIMSECCandidateResult.objects.create(
            student=self.student_eligible,
            subject=self.sub_eng,
            grade="A",
            session="NOVEMBER",
            exam_year=2026,
        )
        ZIMSECCandidateResult.objects.create(
            student=self.student_eligible,
            subject=self.sub_mat,
            grade="B",
            session="NOVEMBER",
            exam_year=2026,
        )
        ZIMSECCandidateResult.objects.create(
            student=self.student_eligible,
            subject=self.sub_geo,
            grade="C",
            session="NOVEMBER",
            exam_year=2026,
        )
        ZIMSECCandidateResult.objects.create(
            student=self.student_eligible,
            subject=self.sub_his,
            grade="C",
            session="NOVEMBER",
            exam_year=2026,
        )
        ZIMSECCandidateResult.objects.create(
            student=self.student_eligible,
            subject=self.sub_agr,
            grade="A*",
            session="NOVEMBER",
            exam_year=2026,
        )

        # Calculate student analytics
        student_stats = calculate_student_analytics(self.student_eligible)
        self.assertEqual(student_stats["total_passed_subjects"], 5)
        self.assertEqual(student_stats["distinction_count"], 2)  # A (English) and A* (Agriculture)
        self.assertTrue(student_stats["is_eligible_for_a_level"])

        # Calculate section analytics
        section_stats = calculate_section_analytics(2026)

        # Verify subject statistics
        self.assertEqual(
            section_stats["subject"]["Mathematics"]["total_sat"], 1
        )
        self.assertEqual(
            section_stats["subject"]["Mathematics"]["pass_rate_percentage"],
            100.0,
        )

        # Verify teacher statistics
        self.assertEqual(
            section_stats["teacher"][self.teacher.username]["total_sat"], 1
        )

        # Verify department statistics
        self.assertEqual(section_stats["department"]["Sciences"]["total_sat"], 1)

    def test_workflow_coupling_pending_analysis_block(self):
        student = Student.objects.create(
            first_name="Farai",
            surname="Moyo",
            gender="Male",
            date_of_birth=datetime.date(2010, 9, 21),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Pending ZIMSEC Analysis",  # Set status to Pending
        )

        # Attempt to archive student directly without any recorded ZIMSEC results should fail
        with self.assertRaises(ValidationError):
            student.transition_to("Archived", self.admin, "End of high school")

        # Now, register a registered subject and record a result
        StudentSubjectRegistration.objects.create(
            student=student,
            subject=self.sub_mat,
            academic_year=self.year,
            academic_term=self.term,
        )
        ZIMSECCandidateResult.objects.create(
            student=student,
            subject=self.sub_mat,
            grade="B",
            session="NOVEMBER",
            exam_year=2026,
        )

        # Now transition should succeed
        student.transition_to("Archived", self.admin, "End of high school")
        self.assertEqual(student.status, "Archived")
