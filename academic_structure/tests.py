from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from academic_structure.models import (
    AcademicYear,
    AcademicTerm,
    Form,
    Stream,
    AcademicClass,
    StudentClassAllocation,
)
from academic_structure.services import SCHOOL_HOLIDAY_LABEL, current_calendar, sync_current_term
from students.models import Pupil


class AcademicStructureTestCase(TestCase):
    def setUp(self):
        # Setup base academic entities
        self.year_2026 = AcademicYear.objects.create(year=2026, is_active=True, is_current=True)
        self.year_2027 = AcademicYear.objects.create(year=2027, is_active=False)

        self.term_1 = AcademicTerm.objects.create(
            academic_year=self.year_2026, term_number=1, is_active=True, is_current=True, name="Term 1"
        )
        self.term_2 = AcademicTerm.objects.create(
            academic_year=self.year_2026, term_number=2, is_active=False, name="Term 2"
        )

        # Setup forms
        self.form_1 = Form.objects.create(form_number=1, name="Form 1")
        self.form_2 = Form.objects.create(form_number=2, name="Form 2")
        self.form_5 = Form.objects.create(form_number=5, name="Form 5")
        self.form_6 = Form.objects.create(form_number=6, name="Form 6")

        # Setup streams
        self.stream_a = Stream.objects.create(name="A")
        self.stream_b = Stream.objects.create(name="B")
        self.stream_arts = Stream.objects.create(name="Arts")
        self.stream_sciences = Stream.objects.create(name="Sciences")

    def test_single_active_academic_year_constraint(self):
        # Attempt to mark 2027 as active should fail validation
        self.year_2027.is_active = True
        with self.assertRaises(ValidationError):
            self.year_2027.clean()

    def test_single_active_academic_term_constraint(self):
        # Attempt to mark Term 2 as active should fail validation
        self.term_2.is_active = True
        with self.assertRaises(ValidationError):
            self.term_2.clean()

    def test_valid_zimbabwean_streaming_combinations(self):
        # Form 1 Stream A (O Level) is valid
        cls_1 = AcademicClass(
            academic_year=self.year_2026,
            form=self.form_1,
            stream=self.stream_a,
            max_capacity=40,
        )
        cls_1.clean()  # Should not raise

        # Form 5 Stream Arts (A Level) is valid
        cls_2 = AcademicClass(
            academic_year=self.year_2026,
            form=self.form_5,
            stream=self.stream_arts,
            max_capacity=40,
        )
        cls_2.clean()  # Should not raise

    def test_invalid_zimbabwean_streaming_combinations(self):
        # Form 1 Stream Arts (O Level) is invalid
        cls_invalid_1 = AcademicClass(
            academic_year=self.year_2026,
            form=self.form_1,
            stream=self.stream_arts,
            max_capacity=40,
        )
        with self.assertRaises(ValidationError):
            cls_invalid_1.clean()

        # Form 5 Stream A (A Level) is invalid
        cls_invalid_2 = AcademicClass(
            academic_year=self.year_2026,
            form=self.form_5,
            stream=self.stream_a,
            max_capacity=40,
        )
        with self.assertRaises(ValidationError):
            cls_invalid_2.clean()

    def test_capacity_limitations_and_administrative_overrides(self):
        # Create a small class section
        small_class = AcademicClass.objects.create(
            academic_year=self.year_2026,
            form=self.form_2,
            stream=self.stream_b,
            max_capacity=2,
        )

        # Create three students
        student_1 = Pupil.objects.create(
            admission_no="A26501",
            first_name="Chipo",
            surname="Sibanda",
            gender="Female",
            date_of_birth="2011-04-12",
            grade="Form 2",
            class_stream="B",
            status="Active",
        )
        student_2 = Pupil.objects.create(
            admission_no="A26502",
            first_name="Farai",
            surname="Moyo",
            gender="Male",
            date_of_birth="2011-09-21",
            grade="Form 2",
            class_stream="B",
            status="Active",
        )
        student_3 = Pupil.objects.create(
            admission_no="A26503",
            first_name="Tendai",
            surname="Ndlovu",
            gender="Male",
            date_of_birth="2011-01-15",
            grade="Form 2",
            class_stream="B",
            status="Active",
        )

        # Assign first two students successfully
        small_class.assign_student(student_1)
        small_class.assign_student(student_2)

        self.assertEqual(small_class.student_count, 2)
        self.assertEqual(small_class.remaining_spaces, 0)

        # Third assignment without override should fail
        with self.assertRaises(ValidationError):
            small_class.assign_student(student_3, capacity_override=False)

        # Third assignment with override should succeed
        alloc = small_class.assign_student(student_3, capacity_override=True)
        self.assertIsNotNone(alloc)
        self.assertEqual(small_class.student_count, 3)
        self.assertEqual(small_class.remaining_spaces, -1)

    def test_sync_current_term_marks_zimbabwe_term_2_for_july_2026(self):
        self.term_1.start_date = timezone.datetime(2026, 1, 13).date()
        self.term_1.end_date = timezone.datetime(2026, 4, 1).date()
        self.term_1.save()
        self.term_2.start_date = timezone.datetime(2026, 5, 12).date()
        self.term_2.end_date = timezone.datetime(2026, 8, 6).date()
        self.term_2.save()
        term_3 = AcademicTerm.objects.create(
            academic_year=self.year_2026,
            term_number=3,
            name="Term 3",
            start_date=timezone.datetime(2026, 9, 8).date(),
            end_date=timezone.datetime(2026, 12, 8).date(),
        )
        self.year_2026.start_date = timezone.datetime(2026, 1, 13).date()
        self.year_2026.end_date = timezone.datetime(2026, 12, 8).date()
        self.year_2026.save()

        snapshot = sync_current_term(date=timezone.datetime(2026, 7, 12).date())

        self.term_1.refresh_from_db()
        self.term_2.refresh_from_db()
        term_3.refresh_from_db()
        self.year_2026.refresh_from_db()
        self.assertEqual(snapshot.display_term, "Term 2")
        self.assertEqual(snapshot.display_year, "2026")
        self.assertTrue(self.term_2.is_current)
        self.assertFalse(self.term_1.is_current)
        self.assertFalse(term_3.is_current)
        self.assertTrue(self.year_2026.is_current)

    def test_current_calendar_reports_holiday_between_terms(self):
        self.year_2026.start_date = timezone.datetime(2026, 1, 13).date()
        self.year_2026.end_date = timezone.datetime(2026, 12, 8).date()
        self.year_2026.save()
        self.term_1.start_date = timezone.datetime(2026, 1, 13).date()
        self.term_1.end_date = timezone.datetime(2026, 4, 1).date()
        self.term_1.save()
        self.term_2.start_date = timezone.datetime(2026, 5, 12).date()
        self.term_2.end_date = timezone.datetime(2026, 8, 6).date()
        self.term_2.save()
        AcademicTerm.objects.create(
            academic_year=self.year_2026,
            term_number=3,
            name="Term 3",
            start_date=timezone.datetime(2026, 9, 8).date(),
            end_date=timezone.datetime(2026, 12, 8).date(),
        )

        snapshot = current_calendar(date=timezone.datetime(2026, 8, 20).date(), force_sync=True)

        self.assertEqual(snapshot.display_term, SCHOOL_HOLIDAY_LABEL)
        self.assertEqual(snapshot.display_year, "2026")
        self.assertEqual(snapshot.next_term.name, "Term 3")
