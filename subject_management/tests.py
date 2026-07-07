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
    SubjectManagementAuditLog,
)
import datetime

User = get_user_model()


class SubjectManagementTestCase(TestCase):
    def setUp(self):
        # Create academic time structures
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.term = AcademicTerm.objects.create(
            academic_year=self.year, term_number=1, is_active=True
        )

        # Forms and Streams
        self.form_3 = Form.objects.create(form_number=3, name="Form 3")
        self.form_5 = Form.objects.create(form_number=5, name="Form 5")

        self.stream_a = Stream.objects.create(name="A")
        self.stream_arts = Stream.objects.create(name="Arts")

        self.class_olevel = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_3, stream=self.stream_a
        )
        self.class_alevel = AcademicClass.objects.create(
            academic_year=self.year, form=self.form_5, stream=self.stream_arts
        )

        # Create students
        self.student_o = Student.objects.create(
            first_name="Rutendo",
            surname="Zhou",
            gender="Female",
            date_of_birth=datetime.date(2011, 3, 15),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_olevel,
            status="Active Student",
        )
        self.student_a = Student.objects.create(
            first_name="Tinashe",
            surname="Maringe",
            gender="Male",
            date_of_birth=datetime.date(2010, 6, 25),
            admission_date=datetime.date(2026, 1, 15),
            academic_class=self.class_alevel,
            status="Active Student",
        )

        # Create teachers
        self.teacher_x = User.objects.create_user(
            username="teacher_x", password="password123", is_staff=False
        )
        self.teacher_y = User.objects.create_user(
            username="teacher_y", password="password123", is_staff=False
        )

        # Setup baseline O-Level subjects (11 total)
        self.o_subjects = []
        for i in range(11):
            sub = Subject.objects.create(
                code=f"OL_SUB_{i:02d}",
                name=f"O-Level Subject {i}",
                level="O_LEVEL",
            )
            self.o_subjects.append(sub)

        # Setup baseline A-Level subjects (6 total)
        self.a_subjects = []
        for i in range(6):
            sub = Subject.objects.create(
                code=f"AL_SUB_{i:02d}",
                name=f"A-Level Subject {i}",
                level="A_LEVEL",
            )
            self.a_subjects.append(sub)

    def test_subject_caps_ordinary_level(self):
        # Register first 10 subjects successfully
        for i in range(10):
            StudentSubjectRegistration.objects.create(
                student=self.student_o,
                subject=self.o_subjects[i],
                academic_year=self.year,
                academic_term=self.term,
            )

        self.assertEqual(self.student_o.subject_registrations.count(), 10)

        # Registering the 11th subject must fail validation
        with self.assertRaises(ValidationError):
            StudentSubjectRegistration.objects.create(
                student=self.student_o,
                subject=self.o_subjects[10],
                academic_year=self.year,
                academic_term=self.term,
            )

    def test_subject_caps_advanced_level(self):
        # Register first 5 subjects successfully
        for i in range(5):
            StudentSubjectRegistration.objects.create(
                student=self.student_a,
                subject=self.a_subjects[i],
                academic_year=self.year,
                academic_term=self.term,
            )

        self.assertEqual(self.student_a.subject_registrations.count(), 5)

        # Registering the 6th subject must fail validation
        with self.assertRaises(ValidationError):
            StudentSubjectRegistration.objects.create(
                student=self.student_a,
                subject=self.a_subjects[5],
                academic_year=self.year,
                academic_term=self.term,
            )

    def test_level_mismatch_validation(self):
        # Assigning an O-Level subject to an A-Level student should fail
        with self.assertRaises(ValidationError):
            StudentSubjectRegistration.objects.create(
                student=self.student_a,
                subject=self.o_subjects[0],
                academic_year=self.year,
                academic_term=self.term,
            )

    def test_data_level_teacher_isolation(self):
        # Set up allocations
        # Teacher X allocated to O-Level Subject 0 in Form 3 Stream A
        TeacherSubjectAllocation.objects.create(
            teacher=self.teacher_x,
            subject=self.o_subjects[0],
            academic_year=self.year,
            academic_term=self.term,
            form=self.form_3,
            stream=self.stream_a,
        )

        # Teacher Y allocated to O-Level Subject 1 in Form 3 Stream A
        TeacherSubjectAllocation.objects.create(
            teacher=self.teacher_y,
            subject=self.o_subjects[1],
            academic_year=self.year,
            academic_term=self.term,
            form=self.form_3,
            stream=self.stream_a,
        )

        # Student O registered to both Subject 0 and Subject 1
        reg_o0 = StudentSubjectRegistration.objects.create(
            student=self.student_o,
            subject=self.o_subjects[0],
            academic_year=self.year,
            academic_term=self.term,
        )
        reg_o1 = StudentSubjectRegistration.objects.create(
            student=self.student_o,
            subject=self.o_subjects[1],
            academic_year=self.year,
            academic_term=self.term,
        )

        # Teacher X should see Student O's registration for Subject 0
        x_regs = StudentSubjectRegistration.get_assigned_students_for_teacher(
            self.teacher_x
        )
        self.assertIn(reg_o0, x_regs)
        self.assertNotIn(reg_o1, x_regs)

        # Teacher Y should see Student O's registration for Subject 1
        y_regs = StudentSubjectRegistration.get_assigned_students_for_teacher(
            self.teacher_y
        )
        self.assertIn(reg_o1, y_regs)
        self.assertNotIn(reg_o0, y_regs)

    def test_audit_logs_signals(self):
        # Perform modification causing creation
        reg = StudentSubjectRegistration.objects.create(
            student=self.student_o,
            subject=self.o_subjects[0],
            academic_year=self.year,
            academic_term=self.term,
        )

        # Verify CREATE log exists
        log_create = SubjectManagementAuditLog.objects.filter(
            action="CREATE", model_name="StudentSubjectRegistration"
        ).first()
        self.assertIsNotNone(log_create)
        self.assertEqual(log_create.object_id, reg.id)

        # Perform deletion
        reg_id = reg.id
        reg.delete()

        # Verify DELETE log exists
        log_delete = SubjectManagementAuditLog.objects.filter(
            action="DELETE", model_name="StudentSubjectRegistration"
        ).first()
        self.assertIsNotNone(log_delete)
        self.assertEqual(log_delete.object_id, reg_id)
