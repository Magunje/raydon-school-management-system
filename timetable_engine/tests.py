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
from subject_management.models import Subject
from timetable_engine.models import Classroom, TimetableVersion, TimetableEntry
import datetime

User = get_user_model()


class TimetableEngineTestCase(TestCase):
    def setUp(self):
        # Users (teachers)
        self.teacher_1 = User.objects.create_user(
            username="teacher1", password="password123"
        )
        self.teacher_2 = User.objects.create_user(
            username="teacher2", password="password123"
        )

        # Academic context
        self.year = AcademicYear.objects.create(year=2026, is_active=True)
        self.term = AcademicTerm.objects.create(
            academic_year=self.year, term_number=1, is_active=True
        )

        self.form_1 = Form.objects.create(form_number=1, name="Form 1")
        self.form_2 = Form.objects.create(form_number=2, name="Form 2")
        self.stream_a = Stream.objects.create(name="A")

        # Classrooms
        self.room_101 = Classroom.objects.create(name="Room 101", capacity=30)
        self.room_102 = Classroom.objects.create(name="Room 102", capacity=40)

        # Subjects
        self.sub_eng = Subject.objects.create(
            code="OL_ENG", name="English", level="O_LEVEL"
        )
        self.sub_mat = Subject.objects.create(
            code="OL_MAT", name="Maths", level="O_LEVEL"
        )

        # Timetable Version
        self.version = TimetableVersion.objects.create(
            academic_year=self.year,
            academic_term=self.term,
            version_no=1,
            status="DRAFT",
        )

    def test_timetable_clash_preventions(self):
        # 1. Successful Entry
        entry_1 = TimetableEntry.objects.create(
            version=self.version,
            day_of_week=1,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(8, 40),
            period_no=1,
            subject=self.sub_eng,
            teacher=self.teacher_1,
            classroom=self.room_101,
            form=self.form_1,
            stream=self.stream_a,
        )
        self.assertIsNotNone(entry_1)

        # 2. Teacher Clash: Same day/period, same teacher, different room & form
        with self.assertRaises(ValidationError):
            TimetableEntry.objects.create(
                version=self.version,
                day_of_week=1,
                start_time=datetime.time(8, 0),
                end_time=datetime.time(8, 40),
                period_no=1,
                subject=self.sub_mat,
                teacher=self.teacher_1,  # Same teacher
                classroom=self.room_102,
                form=self.form_2,
                stream=self.stream_a,
            )

        # 3. Classroom Clash: Same day/period, same classroom, different teacher & form
        with self.assertRaises(ValidationError):
            TimetableEntry.objects.create(
                version=self.version,
                day_of_week=1,
                start_time=datetime.time(8, 0),
                end_time=datetime.time(8, 40),
                period_no=1,
                subject=self.sub_mat,
                teacher=self.teacher_2,
                classroom=self.room_101,  # Same classroom
                form=self.form_2,
                stream=self.stream_a,
            )

        # 4. Student Group Clash: Same day/period, same Form+Stream (section), different teacher/room
        with self.assertRaises(ValidationError):
            TimetableEntry.objects.create(
                version=self.version,
                day_of_week=1,
                start_time=datetime.time(8, 0),
                end_time=datetime.time(8, 40),
                period_no=1,
                subject=self.sub_mat,
                teacher=self.teacher_2,
                classroom=self.room_102,
                form=self.form_1,  # Same section
                stream=self.stream_a,  # Same section
            )

    def test_published_version_revision_locks(self):
        entry = TimetableEntry.objects.create(
            version=self.version,
            day_of_week=2,
            start_time=datetime.time(9, 0),
            end_time=datetime.time(9, 40),
            period_no=2,
            subject=self.sub_eng,
            teacher=self.teacher_1,
            classroom=self.room_101,
            form=self.form_1,
            stream=self.stream_a,
        )

        # Publish the version
        self.version.status = "PUBLISHED"
        self.version.save()

        # Attempt to edit entry in published version must raise ValidationError
        entry.start_time = datetime.time(9, 10)
        with self.assertRaises(ValidationError):
            entry.save()

        # Attempt to create new entry directly in published version must raise ValidationError
        with self.assertRaises(ValidationError):
            TimetableEntry.objects.create(
                version=self.version,
                day_of_week=2,
                start_time=datetime.time(10, 0),
                end_time=datetime.time(10, 40),
                period_no=3,
                subject=self.sub_mat,
                teacher=self.teacher_2,
                classroom=self.room_102,
                form=self.form_1,
                stream=self.stream_a,
            )
