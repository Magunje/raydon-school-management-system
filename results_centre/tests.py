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
from subject_management.models import Subject, StudentSubjectRegistration
from results_centre.models import (
    AssessmentComponent,
    Assessment,
    StudentResult,
    ResultCorrectionLog,
)
from results_centre.services import calculate_rankings_for_assessment
import datetime
from decimal import Decimal

User = get_user_model()


class ResultsCentreTestCase(TestCase):
    def setUp(self):
        # Create academic time structures
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.term = AcademicTerm.objects.create(
            academic_year=self.year, term_number=1, is_active=True
        )

        # Forms and Streams
        self.form_3 = Form.objects.create(form_number=3, name="Form 3")
        self.stream_a = Stream.objects.create(name="A")

        self.academic_class = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_3, stream=self.stream_a
        )

        # Create active registered students
        self.student_1 = Student.objects.create(
            first_name="Rutendo",
            surname="Zhou",
            gender="Female",
            date_of_birth=datetime.date(2011, 3, 15),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )
        self.student_2 = Student.objects.create(
            first_name="Tinashe",
            surname="Maringe",
            gender="Male",
            date_of_birth=datetime.date(2010, 6, 25),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )
        self.student_unregistered = Student.objects.create(
            first_name="Farai",
            surname="Moyo",
            gender="Male",
            date_of_birth=datetime.date(2011, 9, 21),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.academic_class,
            status="Active Student",
        )

        # Subject
        self.subject = Subject.objects.create(
            code="OL_MAT", name="Mathematics", level="O_LEVEL"
        )

        # Register students to subject
        StudentSubjectRegistration.objects.create(
            student=self.student_1,
            subject=self.subject,
            academic_year=self.year,
            academic_term=self.term,
        )
        StudentSubjectRegistration.objects.create(
            student=self.student_2,
            subject=self.subject,
            academic_year=self.year,
            academic_term=self.term,
        )

        # Users
        self.admin = User.objects.create_user(
            username="admin", password="password123", is_staff=True
        )

    def test_assessment_component_weight_limit(self):
        # 40% component (Class Test)
        c1 = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="CLASS_TEST",
            weighting_percentage=Decimal("40.00"),
        )
        # 40% component (Assignment)
        c2 = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="ASSIGNMENT",
            weighting_percentage=Decimal("40.00"),
        )

        # Adding a 30% component should fail since total weight would be 110%
        with self.assertRaises(ValidationError):
            AssessmentComponent.objects.create(
                subject=self.subject,
                academic_class=self.academic_class,
                component_type="TERMINAL_EXAM",
                weighting_percentage=Decimal("30.00"),
            )

        # Adding a 20% component should succeed since total weight is exactly 100%
        c3 = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="TERMINAL_EXAM",
            weighting_percentage=Decimal("20.00"),
        )
        self.assertIsNotNone(c3)

    def test_publish_validation_weighting_percentage_sum(self):
        # Create a single 40% component
        c1 = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="CLASS_TEST",
            weighting_percentage=Decimal("40.00"),
        )

        # Create assessment in Draft status
        assessment = Assessment.objects.create(
            component=c1,
            name="Mid-Term Test",
            academic_year=self.year,
            academic_term=self.term,
            status="Draft",
        )

        # Attempt to publish assessment when components do not sum to exactly 100% should fail
        assessment.status = "Published"
        with self.assertRaises(ValidationError):
            assessment.clean()

        # Add remaining 60% weighting components
        AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="TERMINAL_EXAM",
            weighting_percentage=Decimal("60.00"),
        )

        # Now clean should pass
        assessment.clean()  # Should not raise

    def test_alpha_grades_rankings_and_averages(self):
        comp = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="TERMINAL_EXAM",
            weighting_percentage=Decimal("100.00"),
            max_score=100,
        )
        assessment = Assessment.objects.create(
            component=comp,
            name="Term Final Exam",
            academic_year=self.year,
            academic_term=self.term,
            status="Open",
        )

        # Record scores
        res1 = StudentResult.objects.create(
            assessment=assessment, student=self.student_1, score=Decimal("85.00")
        )
        res2 = StudentResult.objects.create(
            assessment=assessment, student=self.student_2, score=Decimal("65.00")
        )

        # Verify automatic conversions and Alpha Grades
        self.assertEqual(res1.percentage, Decimal("85.00"))
        self.assertEqual(res1.alpha_grade, "A")
        self.assertEqual(res2.percentage, Decimal("65.00"))
        self.assertEqual(res2.alpha_grade, "C")

        # Run calculations service
        calculate_rankings_for_assessment(assessment)

        res1.refresh_from_db()
        res2.refresh_from_db()

        # Verify rankings
        self.assertEqual(res1.class_rank, 1)
        self.assertEqual(res2.class_rank, 2)

        # Verify average (85 + 65) / 2 = 75
        self.assertEqual(res1.class_average, Decimal("75.00"))
        self.assertEqual(res2.class_average, Decimal("75.00"))

    def test_write_once_compliance_and_correction_logs(self):
        comp = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="TERMINAL_EXAM",
            weighting_percentage=Decimal("100.00"),
            max_score=100,
        )
        assessment = Assessment.objects.create(
            component=comp,
            name="Term Final Exam",
            academic_year=self.year,
            academic_term=self.term,
            status="Published",  # Marked as Published
        )

        res = StudentResult.objects.create(
            assessment=assessment, student=self.student_1, score=Decimal("85.00")
        )

        # Attempting to edit score on published assessment without override should raise error
        res.score = Decimal("90.00")
        with self.assertRaises(ValidationError):
            res.clean()

        # Reopening correction with override should succeed and create a log
        res.allow_correction = True
        res.corrected_by_user = self.admin
        res.correction_reason = "Identified spelling mistake in marking"
        res.save()

        res.refresh_from_db()
        self.assertEqual(res.score, Decimal("90.00"))

        # Verify audit log entry
        log = ResultCorrectionLog.objects.filter(student_result=res).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.previous_score, Decimal("85.00"))
        self.assertEqual(log.new_score, Decimal("90.00"))
        self.assertEqual(log.corrected_by, self.admin)
        self.assertEqual(log.reason, "Identified spelling mistake in marking")

    def test_integration_rigidity_validation(self):
        comp = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.academic_class,
            component_type="TERMINAL_EXAM",
            weighting_percentage=Decimal("100.00"),
            max_score=100,
        )
        assessment = Assessment.objects.create(
            component=comp,
            name="Term Final Exam",
            academic_year=self.year,
            academic_term=self.term,
            status="Open",
        )

        # Attempt to record score for unregistered student should fail
        with self.assertRaises(ValidationError):
            StudentResult.objects.create(
                assessment=assessment,
                student=self.student_unregistered,
                score=Decimal("70.00"),
            )

        # Attempt to record score for inactive student should fail
        self.student_1.status = "Suspended"
        self.student_1.save()

        with self.assertRaises(ValidationError):
            StudentResult.objects.create(
                assessment=assessment, student=self.student_1, score=Decimal("70.00")
            )


class ResultsCentreRowLevelSecurityTestCase(TestCase):
    def setUp(self):
        # Create academic time structures
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.term = AcademicTerm.objects.create(
            academic_year=self.year, term_number=1, is_active=True
        )

        # Forms and Streams
        self.form_3 = Form.objects.create(form_number=3, name="Form 3")
        self.stream_a = Stream.objects.create(name="A")
        self.stream_b = Stream.objects.create(name="B")

        self.class_a = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_3, stream=self.stream_a
        )
        self.class_b = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_3, stream=self.stream_b
        )

        # Create active registered students
        self.student_a = Student.objects.create(
            first_name="Alice",
            surname="Moyo",
            gender="Female",
            date_of_birth=datetime.date(2011, 3, 15),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_a,
            status="Active Student",
        )
        self.student_b = Student.objects.create(
            first_name="Bob",
            surname="Sibanda",
            gender="Male",
            date_of_birth=datetime.date(2010, 6, 25),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_b,
            status="Active Student",
        )

        # Subject
        self.subject = Subject.objects.create(
            code="OL_MAT", name="Mathematics", level="O_LEVEL"
        )

        # Register students to subject
        StudentSubjectRegistration.objects.create(
            student=self.student_a,
            subject=self.subject,
            academic_year=self.year,
            academic_term=self.term,
        )
        StudentSubjectRegistration.objects.create(
            student=self.student_b,
            subject=self.subject,
            academic_year=self.year,
            academic_term=self.term,
        )

        # Create Assessment Components
        self.comp_a = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.class_a,
            component_type="CLASS_TEST",
            weighting_percentage=Decimal("50.00"),
            max_score=100
        )
        self.comp_b = AssessmentComponent.objects.create(
            subject=self.subject,
            academic_class=self.class_b,
            component_type="CLASS_TEST",
            weighting_percentage=Decimal("50.00"),
            max_score=100
        )

        # Create Assessments
        self.assessment_a = Assessment.objects.create(
            component=self.comp_a,
            name="Form 3A Test",
            academic_year=self.year,
            academic_term=self.term,
            status="Open",
        )
        self.assessment_b = Assessment.objects.create(
            component=self.comp_b,
            name="Form 3B Test",
            academic_year=self.year,
            academic_term=self.term,
            status="Open",
        )

        # Create Teachers
        self.teacher_1 = User.objects.create_user(
            username="teacher1", password="password123"
        )
        self.teacher_2 = User.objects.create_user(
            username="teacher2", password="password123"
        )

        # Allocate Teacher 1 to Class A and Teacher 2 to Class B
        from subject_management.models import TeacherSubjectAllocation
        TeacherSubjectAllocation.objects.create(
            teacher=self.teacher_1,
            subject=self.subject,
            academic_year=self.year,
            academic_term=self.term,
            form=self.form_3,
            stream=self.stream_a
        )
        TeacherSubjectAllocation.objects.create(
            teacher=self.teacher_2,
            subject=self.subject,
            academic_year=self.year,
            academic_term=self.term,
            form=self.form_3,
            stream=self.stream_b
        )

    def test_assessment_query_isolation_for_teacher(self):
        # Teacher 1 should only see assessment_a
        visible_assessments_t1 = Assessment.objects.for_teacher(self.teacher_1)
        self.assertIn(self.assessment_a, visible_assessments_t1)
        self.assertNotIn(self.assessment_b, visible_assessments_t1)

        # Teacher 2 should only see assessment_b
        visible_assessments_t2 = Assessment.objects.for_teacher(self.teacher_2)
        self.assertIn(self.assessment_b, visible_assessments_t2)
        self.assertNotIn(self.assessment_a, visible_assessments_t2)

    def test_student_result_query_isolation_for_teacher(self):
        res_a = StudentResult.objects.create(
            assessment=self.assessment_a, student=self.student_a, score=Decimal("70.00")
        )
        res_b = StudentResult.objects.create(
            assessment=self.assessment_b, student=self.student_b, score=Decimal("80.00")
        )

        # Teacher 1 should only see result res_a
        visible_results_t1 = StudentResult.objects.for_teacher(self.teacher_1)
        self.assertIn(res_a, visible_results_t1)
        self.assertNotIn(res_b, visible_results_t1)

        # Teacher 2 should only see result res_b
        visible_results_t2 = StudentResult.objects.for_teacher(self.teacher_2)
        self.assertIn(res_b, visible_results_t2)
        self.assertNotIn(res_a, visible_results_t2)

    def test_teacher_unallocated_marks_injection_blocked(self):
        # Teacher 1 attempts to record score for Student B (Class B - unallocated)
        res = StudentResult(
            assessment=self.assessment_b,
            student=self.student_b,
            score=Decimal("90.00")
        )
        res.request_user = self.teacher_1

        # This must raise ValidationError since Teacher 1 is not allocated to Class B
        with self.assertRaises(ValidationError):
            res.clean()
